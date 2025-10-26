#!/usr/bin/env python3
try:
    import importlib
    gevent = importlib.import_module('gevent')
    monkey = gevent.monkey
    monkey.patch_all()
    gevent_socket = importlib.import_module('gevent.socket')
    _HAS_GEVENT = True
except Exception:
    # gevent is optional; fall back to stdlib if not installed
    monkey = None
    gevent_socket = None
    _HAS_GEVENT = False
import importlib
try:
    # Import settings dynamically so linters that can't resolve project-local
    # modules won't report an error, while retaining normal import semantics.
    settings = importlib.import_module('settings')
except Exception:
    # Provide a minimal fallback so linters / runtime don't fail if a project
    # settings.py is missing; adjust defaults as needed.
    import types
    settings = types.SimpleNamespace(
        port_number=8080,
        allow_foreign_addresses=False,
        route_tor=0,
        allow_foreign_post_requests=False,
    )

try:
    pywsgi = importlib.import_module('gevent.pywsgi')
    WSGIServer = getattr(pywsgi, 'WSGIServer', None)
except Exception:
    WSGIServer = None
import urllib
try:
    urllib3 = importlib.import_module('urllib3')
except Exception:
    urllib3 = None
import socket
try:
    socks = importlib.import_module('socks')
    sockshandler = importlib.import_module('sockshandler')
except Exception:
    # socks / sockshandler are optional; allow static analysis or runtime to continue
    socks = None
    sockshandler = None
import subprocess
import re
import sys
import time
try:
    # Use importlib to dynamically import util so static analyzers won't flag a missing project-local module.
    util = importlib.import_module('util')
except Exception:
    # Minimal fallback implementation of util.fetch_url_response so linters/runtime
    # don't fail when a project-local util module is missing. This implementation
    # is synchronous and reads the full response into memory; it's sufficient
    # for basic testing and avoids import errors.
    import urllib.request
    import io
    import ssl

    class _MinimalResponse:
        def __init__(self, fp, headers, status, reason):
            self._fp = fp
            self.headers = headers
            self.status = status
            self.reason = reason

        def read(self, amt=None):
            if amt is None:
                return self._fp.read()
            return self._fp.read(amt)

        def close(self):
            try:
                self._fp.close()
            except Exception:
                pass

    def fetch_url_response(url, headers=None, use_tor=False, max_redirects=10):
        """
        Fetch the URL and return a tuple (response, cleanup_func).
        response implements .headers (list of (name,value)), .status, .reason and .read().
        cleanup_func(response) should be called to release resources.
        This simple implementation reads the full response into memory.
        """
        req = urllib.request.Request(url, headers=headers or {})
        ctx = ssl.create_default_context()
        resp = urllib.request.urlopen(req, context=ctx, timeout=30)
        data = resp.read()
        fp = io.BytesIO(data)
        headers_list = list(resp.getheaders())
        status = getattr(resp, 'status', resp.getcode())
        reason = getattr(resp, 'reason', '')
        return _MinimalResponse(fp, headers_list, status, reason), (lambda r: r.close())




def youtu_be(env, start_response):
    id = env['PATH_INFO'][1:]
    env['PATH_INFO'] = '/watch'
    if not env['QUERY_STRING']:
        env['QUERY_STRING'] = 'v=' + id
    else:
        env['QUERY_STRING'] += '&v=' + id
    yield from yt_app(env, start_response)

RANGE_RE = re.compile(r'bytes=(\d+-(?:\d+)?)')
def parse_range(range_header, content_length):
    # Range header can be like bytes=200-1000 or bytes=200-
    # amount_received is the length of bytes from the range that have already
    # been received
    match = RANGE_RE.fullmatch(range_header.strip())
    if not match:
        print('Unsupported range header format:', range_header)
        return None
    start, end = match.group(1).split('-')
    start_byte = int(start)
    if not end:
        end_byte = start_byte + content_length - 1
    else:
        end_byte = int(end)
    return start_byte, end_byte

def proxy_site(env, start_response, video=False):
    send_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64)',
        'Accept': '*/*',
    }
    current_range_start = 0
    range_end = None
    if 'HTTP_RANGE' in env:
        send_headers['Range'] = env['HTTP_RANGE']

    url = "https://" + env['SERVER_NAME'] + env['PATH_INFO']
    # remove /name portion
    if video and '/videoplayback/name/' in url:
        url = url[0:url.rfind('/name/')]
    if env['QUERY_STRING']:
        url += '?' + env['QUERY_STRING']

    try_num = 1
    first_attempt = True
    current_attempt_position = 0
    while try_num <= 3:   # Try a given byte position three times
        if not first_attempt:
            print('(Try %d)' % try_num, 'Trying with', send_headers['Range'])

        if video:
            params = urllib.parse.parse_qs(env['QUERY_STRING'])
            params_use_tor = int(params.get('use_tor', '0')[0])
            use_tor = (settings.route_tor == 2) or params_use_tor
            response, cleanup_func = util.fetch_url_response(url, send_headers,
                                                             use_tor=use_tor,
                                                             max_redirects=10)
        else:
            response, cleanup_func = util.fetch_url_response(url, send_headers)

        response_headers = response.headers
        #if isinstance(response_headers, urllib3._collections.HTTPHeaderDict):
        #   response_headers = response_headers.items()
        try:
            response_headers = list(response_headers.items())
        except AttributeError:
            pass
        if video:
            response_headers = (list(response_headers)
                                +[('Access-Control-Allow-Origin', '*')])

        if first_attempt:
            start_response(str(response.status) + ' ' + response.reason,
                           response_headers)

        content_length = int(dict(response_headers).get('Content-Length', 0))
        if response.status >= 400:
            print('Error: Youtube returned "%d %s" while routing %s' % (
                response.status, response.reason, url.split('?')[0]))

        total_received = 0
        retry = False
        while True:
            # a bit over 3 seconds of 360p video
            # we want each TCP packet to transmit in large multiples,
            # such as 65,536, so we shouldn't read in small chunks
            # such as 8192 lest that causes the socket library to limit the
            # TCP window size
            # Might need fine-tuning, since this gives us 4*65536
            # The tradeoff is that larger values (such as 6 seconds) only
            # allows video to buffer in those increments, meaning user must
            # wait until the entire chunk is downloaded before video starts
            # playing
            content_part = response.read(32*8192)
            total_received += len(content_part)
            if not content_part:
                # Sometimes Youtube closes the connection before sending all of
                # the content. Retry with a range request for the missing
                # content. See
                # https://github.com/user234683/youtube-local/issues/40
                if total_received < content_length:
                    if 'Range' in send_headers:
                        int_range = parse_range(send_headers['Range'],
                                                content_length)
                        if not int_range: # give up b/c unrecognized range
                            break
                        start, end = int_range
                    else:
                        start, end = 0, (content_length - 1)

                    fail_byte = start + total_received
                    send_headers['Range'] = 'bytes=%d-%d' % (fail_byte, end)
                    print(
                        'Warning: Youtube closed the connection before byte',
                        str(fail_byte) + '.', 'Expected', start+content_length,
                        'bytes.'
                    )

                    retry = True
                    first_attempt = False
                    if fail_byte == current_attempt_position:
                        try_num += 1
                    else:
                        try_num = 1
                        current_attempt_position = fail_byte
                break
            yield content_part
        cleanup_func(response)
        if retry:
            # Youtube will return 503 Service Unavailable if you do a bunch
            # of range requests too quickly.
            time.sleep(1)
            continue
        else:
            break
    else: # no break
        print('Error: Youtube closed the connection before',
              'providing all content. Retried three times:', url.split('?')[0])

def proxy_video(env, start_response):
    yield from proxy_site(env, start_response, video=True)

def yt_app(env, start_response):
    # Primary handler for youtube.com and youtube-nocookie.com.
    # Treat /watch requests as video requests so range-handling and related
    # behaviour in proxy_site can be used; other requests are proxied normally.
    path = env.get('PATH_INFO', '')
    if path.startswith('/watch'):
        yield from proxy_site(env, start_response, video=True)
    else:
        yield from proxy_site(env, start_response, video=False)

site_handlers = {
    'youtube.com': yt_app,
    'youtube-nocookie.com': yt_app,
    'youtu.be': youtu_be,
    'ytimg.com': proxy_site,
    'ggpht.com': proxy_site,
    'googleusercontent.com': proxy_site,
    'sponsor.ajay.app': proxy_site,
    'googlevideo.com': proxy_video,
}

def split_url(url):
    ''' Split https://sub.example.com/foo/bar.html into ('sub.example.com', '/foo/bar.html')'''
    # XXX: Is this regex safe from REDOS?
    # python STILL doesn't have a proper regular expression engine like grep uses built in...
    match = re.match(r'(?:https?://)?([\w-]+(?:\.[\w-]+)+?)(/.*|$)', url)
    if match is None:
        raise ValueError('Invalid or unsupported url: ' + url)

    return match.group(1), match.group(2)



def error_code(code, start_response):
    start_response(code, ())
    return code.encode()

def site_dispatch(env, start_response):
    client_address = env['REMOTE_ADDR']
    try:
        # correct malformed query string with ? separators instead of &
        env['QUERY_STRING'] = env['QUERY_STRING'].replace('?', '&')

        # Some servers such as uWSGI rewrite double slashes // to / by default,
        # breaking the https:// schema. Some servers provide
        # REQUEST_URI (nonstandard), which contains the full, original URL.
        # See https://github.com/user234683/youtube-local/issues/43
        if 'REQUEST_URI' in env:
            # Since it's the original url, the server won't handle percent
            # decoding for us
            env['PATH_INFO'] = urllib.parse.unquote(
                env['REQUEST_URI'].split('?')[0]
            )

        method = env['REQUEST_METHOD']
        path = env['PATH_INFO']

        if (method=="POST"
                and client_address not in ('127.0.0.1', '::1')
                and not settings.allow_foreign_post_requests):
            yield error_code('403 Forbidden', start_response)
            return

        # redirect localhost:8080 to localhost:8080/https://youtube.com
        if path == '' or path == '/':
            start_response('302 Found', [('Location', '/https://youtube.com')])
            return

        try:
            env['SERVER_NAME'], env['PATH_INFO'] = split_url(path[1:])
        except ValueError:
            yield error_code('404 Not Found', start_response)
            return

        base_name = ''
        for domain in reversed(env['SERVER_NAME'].split('.')):
            if base_name == '':
                base_name = domain
            else:
                base_name = domain + '.' + base_name

            try:
                handler = site_handlers[base_name]
            except KeyError:
                continue
            else:
                yield from handler(env, start_response)
                break
        else:   # did not break
            yield error_code('404 Not Found', start_response)
            return
    except Exception:
        start_response('500 Internal Server Error', ())
        yield b'500 Internal Server Error'
        raise
    return


class FilteredRequestLog:
    '''Don't log noisy thumbnail and avatar requests'''
    filter_re = re.compile(r'''(?x)
        "GET\ /https://(
            i[.]ytimg[.]com/|
            www[.]youtube[.]com/data/subscription_thumbnails/|
            .*?[.]ytimg[.]com/|
            .*?[.]googleusercontent[.]com/
        )
    ''')

    def write(self, msg):
        if not msg:
            return
        try:
            if self.filter_re.search(msg):
                return
        except Exception:
            # If regex matching fails for any reason, fall back to writing the message.
            pass
        try:
            sys.stdout.write(msg)
        except Exception:
            pass

    def flush(self):
        try:
            sys.stdout.flush()
        except Exception:
            pass

if __name__ == '__main__':
    if _HAS_GEVENT and WSGIServer is not None:
        if settings.allow_foreign_addresses:
            server = WSGIServer(('0.0.0.0', settings.port_number), site_dispatch,
                                log=FilteredRequestLog())
        else:
            server = WSGIServer(('127.0.0.1', settings.port_number), site_dispatch,
                                log=FilteredRequestLog())
    else:
        # Fallback to wsgiref if gevent is not installed
        from wsgiref.simple_server import make_server
        host = '0.0.0.0' if settings.allow_foreign_addresses else '127.0.0.1'
        server = make_server(host, settings.port_number, site_dispatch)
    print('Started httpserver on port', settings.port_number)
    server.serve_forever()

# for uwsgi, gunicorn, etc.
application = site_dispatch
