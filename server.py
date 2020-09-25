#!/usr/bin/env python3
from gevent import monkey
monkey.patch_all()
import gevent.socket

from youtube import yt_app
from youtube import util

# these are just so the files get run - they import yt_app and add routes to it
from youtube import watch, search, playlist, channel, local_playlist, comments, post_comment, subscriptions

import settings

from gevent.pywsgi import WSGIServer
import urllib
import urllib3
import socket
import socks, sockshandler
import subprocess
import re
import sys




def youtu_be(env, start_response):
    id = env['PATH_INFO'][1:]
    env['PATH_INFO'] = '/watch'
    if not env['QUERY_STRING']:
        env['QUERY_STRING'] = 'v=' + id
    else:
        env['QUERY_STRING'] += '&v=' + id
    yield from yt_app(env, start_response)

def proxy_site(env, start_response, video=False):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64)',
        'Accept': '*/*',
    }
    if 'HTTP_RANGE' in env:
        headers['Range'] = env['HTTP_RANGE']

    url = "https://" + env['SERVER_NAME'] + env['PATH_INFO']
    if env['QUERY_STRING']:
        url += '?' + env['QUERY_STRING']

    if video:
        params = urllib.parse.parse_qs(env['QUERY_STRING'])
        params_use_tor = int(params.get('use_tor', '0')[0])
        use_tor = (settings.route_tor == 2) or params_use_tor
        response, cleanup_func = util.fetch_url_response(url, headers,
                                                         use_tor=use_tor,
                                                         max_redirects=10)
    else:
        response, cleanup_func = util.fetch_url_response(url, headers)

    headers = response.getheaders()
    if isinstance(headers, urllib3._collections.HTTPHeaderDict):
        headers = headers.items()

    start_response(str(response.status) + ' ' + response.reason, headers)
    while True:
        # a bit over 3 seconds of 360p video
        # we want each TCP packet to transmit in large multiples,
        # such as 65,536, so we shouldn't read in small chunks
        # such as 8192 lest that causes the socket library to limit the
        # TCP window size
        # Might need fine-tuning, since this gives us 4*65536
        # The tradeoff is that larger values (such as 6 seconds) only 
        # allows video to buffer in those increments, meaning user must wait
        # until the entire chunk is downloaded before video starts playing
        content_part = response.read(32*8192)
        if not content_part:
            break
        yield content_part

    cleanup_func(response)

def proxy_video(env, start_response):
    yield from proxy_site(env, start_response, video=True)

site_handlers = {
    'youtube.com':yt_app,
    'youtu.be':youtu_be,
    'ytimg.com': proxy_site,
    'yt3.ggpht.com': proxy_site,
    'lh3.googleusercontent.com': proxy_site,
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

        method = env['REQUEST_METHOD']
        path = env['PATH_INFO']

        if method=="POST" and client_address not in ('127.0.0.1', '::1'):
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
    filter_re = re.compile(r'"GET /https://(i\.ytimg\.com/|www\.youtube\.com/data/subscription_thumbnails/|yt3\.ggpht\.com/|www\.youtube\.com/api/timedtext).*" 200')
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
