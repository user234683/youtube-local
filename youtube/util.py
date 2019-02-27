import settings
import socks, sockshandler
import gzip
import brotli
import urllib.parse
import re
import time

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

old_tor_connection_pool = None
tor_connection_pool = urllib3.contrib.socks.SOCKSProxyManager('socks5://127.0.0.1:9150/', cert_reqs = 'CERT_REQUIRED')

tor_pool_refresh_time = time.monotonic()   # prevent problems due to clock changes

def get_pool(use_tor):
    global old_tor_connection_pool
    global tor_connection_pool
    global tor_pool_refresh_time

    if not use_tor:
        return connection_pool

    # Tor changes circuits after 10 minutes: https://tor.stackexchange.com/questions/262/for-how-long-does-a-circuit-stay-alive
    current_time = time.monotonic()
    if current_time - tor_pool_refresh_time > 300:   # close pool after 5 minutes
        tor_connection_pool.clear()

        # Keep a reference for 5 min to avoid it getting garbage collected while sockets still in use
        old_tor_connection_pool = tor_connection_pool

        tor_connection_pool = urllib3.contrib.socks.SOCKSProxyManager('socks5://127.0.0.1:9150/', cert_reqs = 'CERT_REQUIRED')
        tor_pool_refresh_time = current_time

    return tor_connection_pool



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

def fetch_url(url, headers=(), timeout=15, report_text=None, data=None, cookiejar_send=None, cookiejar_receive=None, use_tor=True, return_response=False):
    '''
    When cookiejar_send is set to a CookieJar object,
     those cookies will be sent in the request (but cookies in response will not be merged into it)
    When cookiejar_receive is set to a CookieJar object,
     cookies received in the response will be merged into the object (nothing will be sent from it)
    When both are set to the same object, cookies will be sent from the object,
     and response cookies will be merged into it.
    '''
    headers = dict(headers)     # Note: Calling dict() on a dict will make a copy
    headers['Accept-Encoding'] = 'gzip, br'

    # prevent python version being leaked by urllib if User-Agent isn't provided
    #  (urllib will use ex. Python-urllib/3.6 otherwise)
    if 'User-Agent' not in headers and 'user-agent' not in headers and 'User-agent' not in headers:
        headers['User-Agent'] = 'Python-urllib'

    method = "GET"
    if data is not None:
        method = "POST"
        if isinstance(data, str):
            data = data.encode('ascii')
        elif not isinstance(data, bytes):
            data = urllib.parse.urlencode(data).encode('ascii')

    start_time = time.time()

    if cookiejar_send is not None or cookiejar_receive is not None:     # Use urllib
        req = urllib.request.Request(url, data=data, headers=headers)

        cookie_processor = HTTPAsymmetricCookieProcessor(cookiejar_send=cookiejar_send, cookiejar_receive=cookiejar_receive)

        if use_tor and settings.route_tor:
            opener = urllib.request.build_opener(sockshandler.SocksiPyHandler(socks.PROXY_TYPE_SOCKS5, "127.0.0.1", 9150), cookie_processor)
        else:
            opener = urllib.request.build_opener(cookie_processor)

        response = opener.open(req, timeout=timeout)
        response_time = time.time()


        content = response.read()

    else:           # Use a urllib3 pool. Cookies can't be used since urllib3 doesn't have easy support for them.
        pool = get_pool(use_tor and settings.route_tor)

        response = pool.request(method, url, headers=headers, timeout=timeout, preload_content=False, decode_content=False)
        response_time = time.time()

        content = response.read()
        response.release_conn()

    read_finish = time.time()
    if report_text:
        print(report_text, '    Latency:', round(response_time - start_time,3), '    Read time:', round(read_finish - response_time,3))
    content = decode_content(content, response.getheader('Content-Encoding', default='identity'))

    if return_response:
        return content, response
    return content

mobile_user_agent = 'Mozilla/5.0 (iPhone; CPU iPhone OS 10_3_1 like Mac OS X) AppleWebKit/603.1.30 (KHTML, like Gecko) Version/10.0 Mobile/14E304 Safari/602.1'
mobile_ua = (('User-Agent', mobile_user_agent),)
desktop_user_agent = 'Mozilla/5.0 (Windows NT 6.1; rv:52.0) Gecko/20100101 Firefox/52.0'
desktop_ua = (('User-Agent', desktop_user_agent),)










def dict_add(*dicts):
    for dictionary in dicts[1:]:
        dicts[0].update(dictionary)
    return dicts[0]

def video_id(url):
    url_parts = urllib.parse.urlparse(url)
    return urllib.parse.parse_qs(url_parts.query)['v'][0]

def default_multi_get(object, *keys, default):
    ''' Like dict.get(), but for nested dictionaries/sequences, supporting keys or indices. Last argument is the default value to use in case of any IndexErrors or KeyErrors '''
    try:
        for key in keys:
            object = object[key]
        return object
    except (IndexError, KeyError):
        return default


# default, sddefault, mqdefault, hqdefault, hq720
def get_thumbnail_url(video_id):
    return "/i.ytimg.com/vi/" + video_id + "/mqdefault.jpg"
    
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



def uppercase_escape(s):
     return re.sub(
         r'\\U([0-9a-fA-F]{8})',
         lambda m: chr(int(m.group(1), base=16)), s)