import socks, sockshandler
import gzip
import brotli
import urllib.parse
import re
import time
import settings


URL_ORIGIN = "/https://www.youtube.com"


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

def fetch_url(url, headers=(), timeout=15, report_text=None, data=None, cookiejar_send=None, cookiejar_receive=None, use_tor=True):
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

    if data is not None:
        if isinstance(data, str):
            data = data.encode('ascii')
        elif not isinstance(data, bytes):
            data = urllib.parse.urlencode(data).encode('ascii')

    start_time = time.time()


    req = urllib.request.Request(url, data=data, headers=headers)

    cookie_processor = HTTPAsymmetricCookieProcessor(cookiejar_send=cookiejar_send, cookiejar_receive=cookiejar_receive)

    if use_tor and settings.route_tor:
        opener = urllib.request.build_opener(sockshandler.SocksiPyHandler(socks.PROXY_TYPE_SOCKS5, "127.0.0.1", 9150), cookie_processor)
    else:
        opener = urllib.request.build_opener(cookie_processor)

    response = opener.open(req, timeout=timeout)
    response_time = time.time()


    content = response.read()
    read_finish = time.time()
    if report_text:
        print(report_text, '    Latency:', round(response_time - start_time,3), '    Read time:', round(read_finish - response_time,3))
    content = decode_content(content, response.getheader('Content-Encoding', default='identity'))
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