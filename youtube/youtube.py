import mimetypes
import urllib.parse
import os
from youtube import local_playlist, watch, search, playlist, channel, comments, common, account_functions
import settings
YOUTUBE_FILES = (
    "/shared.css",
    '/comments.css',
    '/favicon.ico',
)

def youtube(env, start_response):
    path, method, query_string = env['PATH_INFO'], env['REQUEST_METHOD'], env['QUERY_STRING']
    if method == "GET":
        if path in YOUTUBE_FILES:
            with open("youtube" + path, 'rb') as f:
                mime_type = mimetypes.guess_type(path)[0] or 'application/octet-stream'
                start_response('200 OK',  (('Content-type',mime_type),) )
                return f.read()
        elif path.lstrip('/') == "":
            start_response('200 OK',  (('Content-type','text/html'),) )
            return search.get_search_page(query_string).encode()

        elif path == "/comments":
            start_response('200 OK',  (('Content-type','text/html'),) )
            return comments.get_comments_page(query_string).encode()

        elif path == "/watch":
            start_response('200 OK',  (('Content-type','text/html'),) )
            return watch.get_watch_page(query_string).encode()
        
        elif path == "/search":
            start_response('200 OK',  (('Content-type','text/html'),) )
            return search.get_search_page(query_string).encode()
        
        elif path == "/playlist":
            start_response('200 OK',  (('Content-type','text/html'),) )
            return playlist.get_playlist_page(query_string).encode()
        
        elif path.startswith("/channel/"):
            start_response('200 OK',  (('Content-type','text/html'),) )
            return channel.get_channel_page(path[9:], query_string=query_string).encode()

        elif path.startswith("/user/"):
            start_response('200 OK',  (('Content-type','text/html'),) )
            return channel.get_user_page(path[6:], query_string=query_string).encode()

        elif path.startswith("/playlists"):
            start_response('200 OK',  (('Content-type','text/html'),) )
            return local_playlist.get_playlist_page(path[10:], query_string=query_string).encode()

        elif path.startswith("/data/playlist_thumbnails/"):
            with open(os.path.join(settings.data_dir, os.path.normpath(path[6:])), 'rb') as f:
                start_response('200 OK',  (('Content-type', "image/jpeg"),) )
                return f.read()

        elif path.startswith("/api/"):
            start_response('200 OK',  () )
            result = common.fetch_url('https://www.youtube.com' + path + ('?' + query_string if query_string else ''))
            result = result.replace(b"align:start position:0%", b"")
            return result

        elif path == "/post_comment":
            start_response('200 OK',  () )
            return account_functions.get_post_comment_page(query_string).encode()

        elif path == "/opensearch.xml":
            with open("youtube" + path, 'rb') as f:
                mime_type = mimetypes.guess_type(path)[0] or 'application/octet-stream'
                start_response('200 OK',  (('Content-type',mime_type),) )
                return f.read().replace(b'$port_number', str(settings.port_number).encode())

        else:
            start_response('404 Not Found',  () )
            return b'404 Not Found'

    elif method == "POST":
        fields = urllib.parse.parse_qs(env['wsgi.input'].read().decode())
        if path == "/edit_playlist":
            if fields['action'][0] == 'add':
                local_playlist.add_to_playlist(fields['playlist_name'][0], fields['video_info_list'])
                start_response('204 No Content', ())
            else:
                start_response('400 Bad Request', ())
                return b'400 Bad Request'

        elif path.startswith("/playlists"):
            if fields['action'][0] == 'remove':
                playlist_name = path[11:]
                local_playlist.remove_from_playlist(playlist_name, fields['video_info_list'])
                start_response('303 See Other', (('Location', common.URL_ORIGIN + path),) )
                return local_playlist.get_playlist_page(playlist_name).encode() 

            else:
                start_response('400 Bad Request', ())
                return b'400 Bad Request'

        elif path in ("/post_comment", "/comments"):
            parameters = urllib.parse.parse_qs(query_string)
            account_functions.post_comment(parameters, fields)
            if 'parent_id' in parameters:
                start_response('303 See Other',  (('Location', common.URL_ORIGIN + '/comments?' + query_string),) )
            else:
                try:
                    video_id = fields['video_id'][0]
                except KeyError:
                    video_id = parameters['video_id'][0]
                start_response('303 See Other',  (('Location', common.URL_ORIGIN + '/comments?ctoken=' + comments.make_comment_ctoken(video_id, sort=1)),) )
            return ''

        else:
            start_response('404 Not Found', ())
            return b'404 Not Found' 

    else:
        start_response('501 Not Implemented', ())
        return b'501 Not Implemented'