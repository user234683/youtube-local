import settings
import socks, sockshandler
import gzip
try:
    import brotli
    have_brotli = True
except ImportError:
    have_brotli = False
import urllib.parse
import re
import time
import os
import json
import gevent
import gevent.queue
import gevent.lock
import collections
import stem
import stem.control
import traceback

# The trouble with the requests library: It ships its own certificate bundle via certifi
#  instead of using the system certificate store, meaning self-signed certificates
#  configured by the user will not work. Some draconian networks block TLS unless a corporate
#  certificate is installed on the system. Additionally, some users install a self signed cert
#  in order to use programs to modify or monitor requests made by programs on the system.

# Finally, certificates expire and need to be updated, or are sometimes revoked. Sometimes
#  certificate authorites go rogue and need to be untrusted. Since we are going through Tor exit nodes,
#  this becomes all the more important. A rogue CA could issue a fake certificate for accounts.google.com, and a
#  malicious exit node could use this to decrypt traffic when logging in and retrieve passwords. Examples:
#   https://www.engadget.com/2015/10/29/google-warns-symantec-over-certificates/
#   https://nakedsecurity.sophos.com/2013/12/09/serious-security-google-finds-fake-but-trusted-ssl-certificates-for-its-domains-made-in-france/

# In the requests documentation it says:
#    "Before version 2.16, Requests bundled a set of root CAs that it trusted, sourced from the Mozilla trust store.
#     The certificates were only updated once for each Requests version. When certifi was not installed,
#     this led to extremely out-of-date certificate bundles when using significantly older versions of Requests.
#     For the sake of security we recommend upgrading certifi frequently!"
#   (http://docs.python-requests.org/en/master/user/advanced/#ca-certificates)

# Expecting users to remember to manually update certifi on Linux isn't reasonable in my view.
#  On windows, this is even worse since I am distributing all dependencies. This program is not
#  updated frequently, and using requests would lead to outdated certificates. Certificates
#  should be updated with OS updates, instead of thousands of developers of different programs
#  being expected to do this correctly 100% of the time.

# There is hope that this might be fixed eventually:
#   https://github.com/kennethreitz/requests/issues/2966

# Until then, I will use a mix of urllib3 and urllib.
import urllib3
import urllib3.contrib.socks

URL_ORIGIN = "/https://www.youtube.com"

connection_pool = urllib3.PoolManager(cert_reqs = 'CERT_REQUIRED')

class TorManager:
    MAX_TRIES = 3
    # Remember the 7-sec wait times, so make cooldown be two of those
    # (otherwise it will retry forever if 429s never end)
    COOLDOWN_TIME = 14
    def __init__(self):
        self.old_tor_connection_pool = None
        self.tor_connection_pool = urllib3.contrib.socks.SOCKSProxyManager(
            'socks5h://127.0.0.1:' + str(settings.tor_port) + '/',
            cert_reqs = 'CERT_REQUIRED')
        self.tor_pool_refresh_time = time.monotonic()
        settings.add_setting_changed_hook(
            'tor_port',
            lambda old_val, new_val: self.refresh_tor_connection_pool(),
        )

        self.new_identity_lock = gevent.lock.BoundedSemaphore(1)
        self.last_new_identity_time = time.monotonic() - 20
        self.try_num = 1

    def refresh_tor_connection_pool(self):
        self.tor_connection_pool.clear()

        # Keep a reference for 5 min to avoid it getting garbage collected
        # while sockets still in use
        self.old_tor_connection_pool = self.tor_connection_pool

        self.tor_connection_pool = urllib3.contrib.socks.SOCKSProxyManager(
            'socks5h://127.0.0.1:' + str(settings.tor_port) + '/',
            cert_reqs = 'CERT_REQUIRED')
        self.tor_pool_refresh_time = time.monotonic()

    def get_tor_connection_pool(self):
        # Tor changes circuits after 10 minutes:
        # https://tor.stackexchange.com/questions/262/for-how-long-does-a-circuit-stay-alive
        current_time = time.monotonic()

        # close pool after 5 minutes
        if current_time - self.tor_pool_refresh_time > 300:
            self.refresh_tor_connection_pool()

        return self.tor_connection_pool

    def new_identity(self, time_failed_request_started):
        '''return error, or None if no error and the identity is fresh'''

        # The overall pattern at maximum (always returning 429) will be
        # R N (0) R N (6) R N (6) R | (12) R N (0) R N (6) ...
        # where R is a request, N is a new identity, (x) is a wait time of
        # x sec, and | is where we give up and display an error to the user.

        print('new_identity: new_identity called')
        # blocks if another greenlet currently has the lock
        self.new_identity_lock.acquire()
        print('new_identity: New identity lock acquired')

        try:
            # This was caused by a request that failed within a previous,
            # stale identity
            if time_failed_request_started <= self.last_new_identity_time:
                print('new_identity: Cancelling; request was from stale identity')
                return None

            delta = time.monotonic() - self.last_new_identity_time
            if delta < self.COOLDOWN_TIME and self.try_num == 1:
                err = ('Retried with new circuit %d times (max) within last '
                       '%d seconds.' % (self.MAX_TRIES, self.COOLDOWN_TIME))
                print('new_identity:', err)
                return err
            elif delta >= self.COOLDOWN_TIME:
                self.try_num = 1

            try:
                port = settings.tor_control_port
                with stem.control.Controller.from_port(port=port) as controller:
                    controller.authenticate('')
                    print('new_identity: Getting new identity')
                    controller.signal(stem.Signal.NEWNYM)
                    print('new_identity: NEWNYM signal sent')
                    self.last_new_identity_time = time.monotonic()
                self.refresh_tor_connection_pool()
            except stem.SocketError:
                traceback.print_exc()
                return 'Failed to connect to Tor control port.'
            finally:
                original_try_num = self.try_num
                self.try_num += 1
                if self.try_num > self.MAX_TRIES:
                    self.try_num = 1

            # If we do the request right after second new identity it won't
            # be a new IP, based on experiments.
            # Not necessary after first new identity
            if original_try_num > 1:
                print('Sleeping for 7 seconds before retrying request')
                time.sleep(7)   # experimentally determined minimum

            return None
        finally:
            self.new_identity_lock.release()

tor_manager = TorManager()


def get_pool(use_tor):
    if not use_tor:
        return connection_pool
    return tor_manager.get_tor_connection_pool()


class HTTPAsymmetricCookieProcessor(urllib.request.BaseHandler):
    '''Separate cookiejars for receiving and sending'''
    def __init__(self, cookiejar_send=None, cookiejar_receive=None):
        import http.cookiejar
        self.cookiejar_send = cookiejar_send
        self.cookiejar_receive = cookiejar_receive

    def http_request(self, request):
        if self.cookiejar_send is not None:
            self.cookiejar_send.add_cookie_header(request)
        return request

    def http_response(self, request, response):
        if self.cookiejar_receive is not None:
            self.cookiejar_receive.extract_cookies(response, request)
        return response

    https_request = http_request
    https_response = http_response

class FetchError(Exception):
    def __init__(self, code, reason='', ip=None, error_message=None):
        if error_message:
            string = code + ' ' + reason + ': ' + error_message
        else:
            string = 'HTTP error during request: ' + code + ' ' + reason
        Exception.__init__(self, string)
        self.code = code
        self.reason = reason
        self.ip = ip
        self.error_message = error_message



def decode_content(content, encoding_header):
    encodings = encoding_header.replace(' ', '').split(',')
    for encoding in reversed(encodings):
        if encoding == 'identity':
            continue
        if encoding == 'br':
            content = brotli.decompress(content)
        elif encoding == 'gzip':
            content = gzip.decompress(content)
    return content

def fetch_url_response(url, headers=(), timeout=15, data=None,
                       cookiejar_send=None, cookiejar_receive=None,
                       use_tor=True, max_redirects=None):
    '''
    returns response, cleanup_function
    When cookiejar_send is set to a CookieJar object,
     those cookies will be sent in the request (but cookies in response will not be merged into it)
    When cookiejar_receive is set to a CookieJar object,
     cookies received in the response will be merged into the object (nothing will be sent from it)
    When both are set to the same object, cookies will be sent from the object,
     and response cookies will be merged into it.
    '''
    headers = dict(headers)     # Note: Calling dict() on a dict will make a copy
    if have_brotli:
        headers['Accept-Encoding'] = 'gzip, br'
    else:
        headers['Accept-Encoding'] = 'gzip'

    # prevent python version being leaked by urllib if User-Agent isn't provided
    #  (urllib will use ex. Python-urllib/3.6 otherwise)
    if 'User-Agent' not in headers and 'user-agent' not in headers and 'User-agent' not in headers:
        headers['User-Agent'] = 'Python-urllib'

    method = "GET"
    if data is not None:
        method = "POST"
        if isinstance(data, str):
            data = data.encode('utf-8')
        elif not isinstance(data, bytes):
            data = urllib.parse.urlencode(data).encode('utf-8')


    if cookiejar_send is not None or cookiejar_receive is not None:     # Use urllib
        req = urllib.request.Request(url, data=data, headers=headers)

        cookie_processor = HTTPAsymmetricCookieProcessor(cookiejar_send=cookiejar_send, cookiejar_receive=cookiejar_receive)

        if use_tor and settings.route_tor:
            opener = urllib.request.build_opener(sockshandler.SocksiPyHandler(socks.PROXY_TYPE_SOCKS5, "127.0.0.1", settings.tor_port), cookie_processor)
        else:
            opener = urllib.request.build_opener(cookie_processor)

        response = opener.open(req, timeout=timeout)
        cleanup_func = (lambda r: None)

    else:           # Use a urllib3 pool. Cookies can't be used since urllib3 doesn't have easy support for them.
        # default: Retry.DEFAULT = Retry(3)
        # (in connectionpool.py in urllib3)
        # According to the documentation for urlopen, a redirect counts as a
        # retry. So there are 3 redirects max by default.
        if max_redirects:
            retries = urllib3.Retry(3+max_redirects, redirect=max_redirects, raise_on_redirect=False)
        else:
            retries = urllib3.Retry(3, raise_on_redirect=False)
        pool = get_pool(use_tor and settings.route_tor)
        try:
            response = pool.request(method, url, headers=headers, body=data,
                                    timeout=timeout, preload_content=False,
                                    decode_content=False, retries=retries)
            response.retries = retries
        except urllib3.exceptions.MaxRetryError as e:
            exception_cause = e.__context__.__context__
            if (isinstance(exception_cause, socks.ProxyConnectionError)
                    and settings.route_tor):
                msg = ('Failed to connect to Tor. Check that Tor is open and '
                       'that your internet connection is working.\n\n'
                       + str(e))
                raise FetchError('502', reason='Bad Gateway',
                                 error_message=msg)
            elif isinstance(e.__context__,
                            urllib3.exceptions.NewConnectionError):
                msg = 'Failed to establish a connection.\n\n' + str(e)
                raise FetchError(
                    '502', reason='Bad Gateway',
                     error_message=msg)
            else:
                raise
        cleanup_func = (lambda r: r.release_conn())

    return response, cleanup_func

def fetch_url(url, headers=(), timeout=15, report_text=None, data=None,
              cookiejar_send=None, cookiejar_receive=None, use_tor=True,
              debug_name=None):
    while True:
        start_time = time.monotonic()

        response, cleanup_func = fetch_url_response(
            url, headers, timeout=timeout, data=data,
            cookiejar_send=cookiejar_send, cookiejar_receive=cookiejar_receive,
            use_tor=use_tor)
        response_time = time.monotonic()

        content = response.read()

        read_finish = time.monotonic()

        cleanup_func(response)  # release_connection for urllib3
        content = decode_content(
            content,
            response.getheader('Content-Encoding', default='identity'))

        if (settings.debugging_save_responses
                and debug_name is not None
                and content):
            save_dir = os.path.join(settings.data_dir, 'debug')
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)

            with open(os.path.join(save_dir, debug_name), 'wb') as f:
                f.write(content)

        if response.status == 429 or (
            response.status == 302 and (response.getheader('Location') == url
                or response.getheader('Location').startswith(
                       'https://www.google.com/sorry/index'
                   )
            )
        ):
            print(response.status, response.reason, response.headers)
            ip = re.search(
                br'IP address: ((?:[\da-f]*:)+[\da-f]+|(?:\d+\.)+\d+)',
                content)
            ip = ip.group(1).decode('ascii') if ip else None
            if not ip:
                ip = re.search(r'IP=((?:\d+\.)+\d+)',
                               response.getheader('Set-Cookie') or '')
                ip = ip.group(1) if ip else None

            # don't get new identity if we're not using Tor
            if not use_tor:
                raise FetchError('429', reason=response.reason, ip=ip)

            print('Error: Youtube blocked the request because the Tor exit node is overutilized. Exit node IP address: %s' % ip)

            # get new identity
            error = tor_manager.new_identity(start_time)
            if error:
                raise FetchError(
                    '429', reason=response.reason, ip=ip,
                    error_message='Automatic circuit change: ' + error)
            else:
                continue # retry now that we have new identity

        elif response.status >= 400:
            raise FetchError(str(response.status), reason=response.reason,
                             ip=None)
        break

    if report_text:
        print(report_text, '    Latency:', round(response_time - start_time,3), '    Read time:', round(read_finish - response_time,3))



    return content

def head(url, use_tor=False, report_text=None, max_redirects=10):
    pool = get_pool(use_tor and settings.route_tor)
    start_time = time.monotonic()

    # default: Retry.DEFAULT = Retry(3)
    # (in connectionpool.py in urllib3)
    # According to the documentation for urlopen, a redirect counts as a retry
    # So there are 3 redirects max by default. Let's change that
    # to 10 since googlevideo redirects a lot.
    retries = urllib3.Retry(3+max_redirects, redirect=max_redirects,
        raise_on_redirect=False)
    headers = {'User-Agent': 'Python-urllib'}
    response = pool.request('HEAD', url, headers=headers, retries=retries)
    if report_text:
        print(
            report_text,
            '    Latency:',
            round(time.monotonic() - start_time,3))
    return response

mobile_user_agent = 'Mozilla/5.0 (Linux; Android 7.0; Redmi Note 4 Build/NRD90M) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Mobile Safari/537.36'
mobile_ua = (('User-Agent', mobile_user_agent),)
desktop_user_agent = 'Mozilla/5.0 (Windows NT 6.1; rv:52.0) Gecko/20100101 Firefox/52.0'
desktop_ua = (('User-Agent', desktop_user_agent),)
json_header = (('Content-Type', 'application/json'),)
desktop_xhr_headers = (
    ('Accept', '*/*'),
    ('Accept-Language', 'en-US,en;q=0.5'),
    ('X-YouTube-Client-Name', '1'),
    ('X-YouTube-Client-Version', '2.20180830'),
) + desktop_ua
mobile_xhr_headers = (
    ('Accept', '*/*'),
    ('Accept-Language', 'en-US,en;q=0.5'),
    ('X-YouTube-Client-Name', '2'),
    ('X-YouTube-Client-Version', '2.20180830'),
) + mobile_ua






class RateLimitedQueue(gevent.queue.Queue):
    ''' Does initial_burst (def. 30) at first, then alternates between waiting waiting_period (def. 5) seconds and doing subsequent_bursts (def. 10) queries. After 5 seconds with nothing left in the queue, resets rate limiting. '''

    def __init__(self, initial_burst=30, waiting_period=5, subsequent_bursts=10):
        self.initial_burst = initial_burst
        self.waiting_period = waiting_period
        self.subsequent_bursts = subsequent_bursts

        self.count_since_last_wait = 0
        self.surpassed_initial = False

        self.lock = gevent.lock.BoundedSemaphore(1)
        self.currently_empty = False
        self.empty_start = 0
        gevent.queue.Queue.__init__(self)


    def get(self):
        self.lock.acquire()     # blocks if another greenlet currently has the lock
        if self.count_since_last_wait >= self.subsequent_bursts and self.surpassed_initial:
            gevent.sleep(self.waiting_period)
            self.count_since_last_wait = 0

        elif self.count_since_last_wait >= self.initial_burst and not self.surpassed_initial:
            self.surpassed_initial = True
            gevent.sleep(self.waiting_period)
            self.count_since_last_wait = 0

        self.count_since_last_wait += 1

        if not self.currently_empty and self.empty():
            self.currently_empty = True
            self.empty_start = time.monotonic()

        item = gevent.queue.Queue.get(self)     # blocks when nothing left

        if self.currently_empty:
            if time.monotonic() - self.empty_start >= self.waiting_period:
                self.count_since_last_wait = 0
                self.surpassed_initial = False

            self.currently_empty = False

        self.lock.release()

        return item



def download_thumbnail(save_directory, video_id):
    url = "https://i.ytimg.com/vi/" + video_id + "/mqdefault.jpg"
    save_location = os.path.join(save_directory, video_id + ".jpg")
    try:
        thumbnail = fetch_url(url, report_text="Saved thumbnail: " + video_id)
    except urllib.error.HTTPError as e:
        print("Failed to download thumbnail for " + video_id + ": " + str(e))
        return False
    try:
        f = open(save_location, 'wb')
    except FileNotFoundError:
        os.makedirs(save_directory, exist_ok = True)
        f = open(save_location, 'wb')
    f.write(thumbnail)
    f.close()
    return True

def download_thumbnails(save_directory, ids):
    if not isinstance(ids, (list, tuple)):
        ids = list(ids)
    # only do 5 at a time
    # do the n where n is divisible by 5
    i = -1
    for i in range(0, int(len(ids)/5) - 1 ):
        gevent.joinall([gevent.spawn(download_thumbnail, save_directory, ids[j]) for j in range(i*5, i*5 + 5)])
    # do the remainders (< 5)
    gevent.joinall([gevent.spawn(download_thumbnail, save_directory, ids[j]) for j in range(i*5 + 5, len(ids))])






def dict_add(*dicts):
    for dictionary in dicts[1:]:
        dicts[0].update(dictionary)
    return dicts[0]

def video_id(url):
    url_parts = urllib.parse.urlparse(url)
    return urllib.parse.parse_qs(url_parts.query)['v'][0]


# default, sddefault, mqdefault, hqdefault, hq720
def get_thumbnail_url(video_id):
    return settings.img_prefix + "https://i.ytimg.com/vi/" + video_id + "/mqdefault.jpg"

def seconds_to_timestamp(seconds):
    seconds = int(seconds)
    hours, seconds = divmod(seconds,3600)
    minutes, seconds = divmod(seconds,60)
    if hours != 0:
        timestamp = str(hours) + ":"
        timestamp += str(minutes).zfill(2)  # zfill pads with zeros
    else:
        timestamp = str(minutes)

    timestamp += ":" + str(seconds).zfill(2)
    return timestamp



def update_query_string(query_string, items):
    parameters = urllib.parse.parse_qs(query_string)
    parameters.update(items)
    return urllib.parse.urlencode(parameters, doseq=True)


YOUTUBE_DOMAINS = ('youtube.com', 'youtu.be', 'youtube-nocookie.com')
YOUTUBE_URL_RE_STR = r'https?://(?:[a-zA-Z0-9_-]*\.)?(?:'
YOUTUBE_URL_RE_STR += r'|'.join(map(re.escape, YOUTUBE_DOMAINS))
YOUTUBE_URL_RE_STR += r')(?:/[^"]*)?'
YOUTUBE_URL_RE = re.compile(YOUTUBE_URL_RE_STR)


def prefix_url(url):
    if url is None:
        return None
    url = url.lstrip('/')     # some urls have // before them, which has a special meaning
    return '/' + url

def left_remove(string, substring):
    '''removes substring from the start of string, if present'''
    if string.startswith(substring):
        return string[len(substring):]
    return string

def concat_or_none(*strings):
    '''Concatenates strings. Returns None if any of the arguments are None'''
    result = ''
    for string in strings:
        if string is None:
            return None
        result += string
    return result


def prefix_urls(item):
    if settings.proxy_images:
        try:
            item['thumbnail'] = prefix_url(item['thumbnail'])
        except KeyError:
            pass

    try:
        item['author_url'] = prefix_url(item['author_url'])
    except KeyError:
        pass

def add_extra_html_info(item):
    if item['type'] == 'video':
        item['url'] = (URL_ORIGIN + '/watch?v=' + item['id']) if item.get('id') else None

        video_info = {}
        for key in ('id', 'title', 'author', 'duration', 'author_id'):
            try:
                video_info[key] = item[key]
            except KeyError:
                video_info[key] = None

        item['video_info'] = json.dumps(video_info)

    elif item['type'] == 'playlist' and item['playlist_type'] == 'radio':
        item['url'] = concat_or_none(
            URL_ORIGIN,
            '/watch?v=', item['first_video_id'],
            '&list=', item['id']
        )
    elif item['type'] == 'playlist':
        item['url'] = concat_or_none(URL_ORIGIN, '/playlist?list=', item['id'])
    elif item['type'] == 'channel':
        item['url'] = concat_or_none(URL_ORIGIN, "/channel/", item['id'])

    if item.get('author_id') and 'author_url' not in item:
        item['author_url'] = URL_ORIGIN + '/channel/' + item['author_id']


def check_gevent_exceptions(*tasks):
    for task in tasks:
        if task.exception:
            raise task.exception


# https://stackoverflow.com/a/62888
replacement_map = collections.OrderedDict([
    ('<', '_'),
    ('>', '_'),
    (': ', ' - '),
    (':', '-'),
    ('"', "'"),
    ('/', '_'),
    ('\\', '_'),
    ('|', '-'),
    ('?', ''),
    ('*', '_'),
    ('\t', ' '),
])
DOS_names = {'con', 'prn', 'aux', 'nul', 'com0', 'com1', 'com2', 'com3', 'com4', 'com5', 'com6', 'com7', 'com8', 'com9', 'lpt0', 'lpt1', 'lpt2', 'lpt3', 'lpt4', 'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9'}
def to_valid_filename(name):
    '''Changes the name so it's valid on Windows, Linux, and Mac'''
    # See https://docs.microsoft.com/en-us/windows/win32/fileio/naming-a-file
    # for Windows specs

    # Additional recommendations for Linux:
    # https://dwheeler.com/essays/fixing-unix-linux-filenames.html#standards

    # remove control characters
    name = re.sub(r'[\x00-\x1f]', '_', name)

    # reserved characters
    for reserved_char, replacement in replacement_map.items():
        name = name.replace(reserved_char, replacement)

    # check for all periods/spaces
    if all(c == '.' or c == ' ' for c in name):
        name = '_'*len(name)

    # remove trailing periods and spaces
    name = name.rstrip('. ')

    # check for reserved DOS names, such as nul or nul.txt
    base_ext_parts = name.rsplit('.', maxsplit=1)
    if base_ext_parts[0].lower() in DOS_names:
        base_ext_parts[0] += '_'
    name = '.'.join(base_ext_parts)

    # check for blank name
    if name == '':
        name = '_'

    # check if name begins with a hyphen, period, or space
    if name[0] in ('-', '.', ' '):
        name = '_' + name

    return name

# https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/youtube.py#L72
INNERTUBE_CLIENTS = {
    'android': {
        'INNERTUBE_API_KEY': 'AIzaSyA8eiZmM1FaDVjRy-df2KTyQ_vz_yYM39w',
        'INNERTUBE_CONTEXT': {
            'client': {
                'hl': 'en',
                'gl': 'US',
                'clientName': 'ANDROID',
                'clientVersion': '18.11.34',
                'osName': 'Android',
                'osVersion': '12',
                'androidSdkVersion': 30,
                'userAgent': 'com.google.android.youtube/18.11.34 (Linux; U; Android 12) gzip'
            },
            # https://github.com/yt-dlp/yt-dlp/pull/575#issuecomment-887739287
            #'thirdParty': {
            #    'embedUrl': 'https://google.com',  # Can be any valid URL
            #}
        },
        'INNERTUBE_CONTEXT_CLIENT_NAME': 3,
        'REQUIRE_JS_PLAYER': False,
    },

    # This client can access age restricted videos (unless the uploader has disabled the 'allow embedding' option)
    # See: https://github.com/zerodytrash/YouTube-Internal-Clients
    'tv_embedded': {
        'INNERTUBE_API_KEY': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
        'INNERTUBE_CONTEXT': {
            'client': {
                'hl': 'en',
                'gl': 'US',
                'clientName': 'TVHTML5_SIMPLY_EMBEDDED_PLAYER',
                'clientVersion': '2.0',
            },
            # https://github.com/yt-dlp/yt-dlp/pull/575#issuecomment-887739287
            'thirdParty': {
                'embedUrl': 'https://google.com',  # Can be any valid URL
            }

        },
        'INNERTUBE_CONTEXT_CLIENT_NAME': 85,
        'REQUIRE_JS_PLAYER': True,
    },

    'web': {
        'INNERTUBE_API_KEY': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
        'INNERTUBE_CONTEXT': {
            'client': {
                'clientName': 'WEB',
                'clientVersion': '2.20220801.00.00',
                'userAgent': desktop_user_agent,
            }
        },
        'INNERTUBE_CONTEXT_CLIENT_NAME': 1
    },
}

def call_youtube_api(client, api, data):
    client_params = INNERTUBE_CLIENTS[client]
    context = client_params['INNERTUBE_CONTEXT']
    key = client_params['INNERTUBE_API_KEY']
    host = client_params.get('INNERTUBE_HOST') or 'www.youtube.com'
    user_agent = context['client'].get('userAgent') or mobile_user_agent

    url = 'https://' + host + '/youtubei/v1/' + api + '?key=' + key
    data['context'] = context

    data = json.dumps(data)
    headers = (('Content-Type', 'application/json'),('User-Agent', user_agent))
    response = fetch_url(
        url, data=data, headers=headers,
        debug_name='youtubei_' + api + '_' + client,
        report_text='Fetched ' + client + ' youtubei ' + api
    ).decode('utf-8')
    return response
