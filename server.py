#!/usr/bin/env python3
from gevent import monkey
monkey.patch_all()
import gevent.socket

from youtube import yt_app
from youtube import util

# these are just so the files get run - they import yt_app and add routes to it
from youtube import watch, search, playlist, channel, local_playlist, comments, subscriptions

import settings

from gevent.pywsgi import WSGIServer
import urllib
import urllib3
import socket
import socks, sockshandler
import subprocess
import re
import sys
import time




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

        response_headers = response.getheaders()
        if isinstance(response_headers, urllib3._collections.HTTPHeaderDict):
            response_headers = response_headers.items()
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

site_handlers = {
    'youtube.com':yt_app,
    'youtube-nocookie.com':yt_app,
    'youtu.be':youtu_be,
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
                            yt3[.]ggpht[.]com/|
                            www[.]youtube[.]com/api/timedtext|
                            [-\w]+[.]googlevideo[.]com/).*"\ (200|206)
                            ''')
    def __init__(self):
        pass
    def write(self, s):
        if not self.filter_re.search(s):
            sys.stderr.write(s)

if __name__ == '__main__':
    if settings.allow_foreign_addresses:
        server = WSGIServer(('0.0.0.0', settings.port_number), site_dispatch,
                            log=FilteredRequestLog())
    else:
        server = WSGIServer(('127.0.0.1', settings.port_number), site_dispatch,
                            log=FilteredRequestLog())
    print('Started httpserver on port' , settings.port_number)
    server.serve_forever()

# for uwsgi, gunicorn, etc.
application = site_dispatch
