from gevent import monkey
monkey.patch_all()
import gevent.socket

from gevent.pywsgi import WSGIServer
from youtube.youtube import youtube
import http_errors
import urllib
import socket
import socks
import subprocess
import re

import settings


BAN_FILE = "banned_addresses.txt"
try:
    with open(BAN_FILE, 'r') as f:
        banned_addresses = f.read().splitlines()
except FileNotFoundError:
    banned_addresses = ()

def ban_address(address):
    banned_addresses.append(address)
    with open(BAN_FILE, 'a') as f:
        f.write(address + "\n")
        

def youtu_be(env, start_response):
    id = env['PATH_INFO'][1:]
    env['PATH_INFO'] = '/watch'
    env['QUERY_STRING'] = 'v=' + id
    return youtube(env, start_response)

def proxy_site(env, start_response):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64)',
        'Accept': '*/*',
    }
    url = "https://" + env['SERVER_NAME'] + env['PATH_INFO']
    if env['QUERY_STRING']:
        url += '?' + env['QUERY_STRING']
    req = urllib.request.Request(url, headers=headers)
    response = urllib.request.urlopen(req, timeout = 10)
    start_response('200 OK', response.getheaders() )
    return response.read()

site_handlers = {
    'youtube.com':youtube,
    'youtu.be':youtu_be,
    'ytimg.com': proxy_site,
    'yt3.ggpht.com': proxy_site,
    'lh3.googleusercontent.com': proxy_site,

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
        method = env['REQUEST_METHOD']
        path = env['PATH_INFO']
        if client_address in banned_addresses:
            yield error_code('403 Fuck Off', start_response)
            return
        if method=="POST" and client_address not in ('127.0.0.1', '::1'):
            yield error_code('403 Forbidden', start_response)
            return
        if "phpmyadmin" in path or (path == "/" and method == "HEAD"):
            #ban_address(client_address)
            start_response('403 Fuck Off', ())
            yield b'403 Fuck Off'
            return

        '''if env['QUERY_STRING']:
            path += '?' + env['QUERY_STRING']'''
        #path_parts = urllib.parse.urlparse(path)
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
                yield handler(env, start_response)
                break
        else:   # did not break
            yield error_code('404 Not Found', start_response)
            return

    except http_errors.Code200 as e:    # Raised in scenarios where a simple status message is to be returned, such as a terminated channel
        start_response('200 OK', ())
        yield str(e).encode('utf-8')

    except http_errors.Error404 as e:
        start_response('404 Not Found', ())
        yield str(e).encode('utf-8')

    except urllib.error.HTTPError as e:
        start_response(str(e.code) + ' ' + e.reason, ())
        yield b'While fetching url, the following error occured:\n' + str(e).encode('utf-8')

    except socket.error as e:
        start_response('502 Bad Gateway', ())
        print(str(e))
        yield b'502 Bad Gateway'
        
    except Exception:
        start_response('500 Internal Server Error', ())
        yield b'500 Internal Server Error'
        raise
    return




if settings.route_tor:
    #subprocess.Popen(TOR_PATH)
    socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, '127.0.0.1', 9150)
    socket.socket = socks.socksocket
    gevent.socket.socket = socks.socksocket

if settings.allow_foreign_addresses:
    server = WSGIServer(('0.0.0.0', settings.port_number), site_dispatch)
else:
    server = WSGIServer(('127.0.0.1', settings.port_number), site_dispatch)
print('Started httpserver on port ' , settings.port_number)
server.serve_forever()
