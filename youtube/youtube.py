import mimetypes
import urllib.parse
import os
from youtube import local_playlist, watch, search, playlist, channel, comments, common, post_comment, accounts
import settings
YOUTUBE_FILES = (
    "/shared.css",
    '/comments.css',
    '/favicon.ico',
)
get_handlers = {
    'search':           search.get_search_page,
    '':                 search.get_search_page,
    'watch':            watch.get_watch_page,
    'playlist':         playlist.get_playlist_page,

    'channel':          channel.get_channel_page,
    'user':             channel.get_channel_page_general_url,
    'c':                channel.get_channel_page_general_url,

    'playlists':        local_playlist.get_playlist_page,

    'comments':         comments.get_comments_page,
    'post_comment':     post_comment.get_post_comment_page,
    'delete_comment':   post_comment.get_delete_comment_page,
    'login':            accounts.get_account_login_page,
}
post_handlers = {
    'edit_playlist':    local_playlist.edit_playlist,
    'playlists':        local_playlist.path_edit_playlist,

    'login':            accounts.add_account,
    'comments':         post_comment.post_comment,
    'post_comment':     post_comment.post_comment,
    'delete_comment':   post_comment.delete_comment,
}

def youtube(env, start_response):
    path, method, query_string = env['PATH_INFO'], env['REQUEST_METHOD'], env['QUERY_STRING']
    env['qs_parameters'] = urllib.parse.parse_qs(query_string)
    env['parameters'] = dict(env['qs_parameters'])

    path_parts = path.rstrip('/').lstrip('/').split('/')
    env['path_parts'] = path_parts

    if method == "GET":
        try:
            handler = get_handlers[path_parts[0]]
        except KeyError:
            pass
        else:
            return handler(env, start_response)

        if path in YOUTUBE_FILES:
            with open("youtube" + path, 'rb') as f:
                mime_type = mimetypes.guess_type(path)[0] or 'application/octet-stream'
                start_response('200 OK',  (('Content-type',mime_type),) )
                return f.read()

        elif path.startswith("/data/playlist_thumbnails/"):
            with open(os.path.join(settings.data_dir, os.path.normpath(path[6:])), 'rb') as f:
                start_response('200 OK',  (('Content-type', "image/jpeg"),) )
                return f.read()

        elif path.startswith("/api/"):
            start_response('200 OK',  () )
            result = common.fetch_url('https://www.youtube.com' + path + ('?' + query_string if query_string else ''))
            result = result.replace(b"align:start position:0%", b"")
            return result

        elif path == "/opensearch.xml":
            with open("youtube" + path, 'rb') as f:
                mime_type = mimetypes.guess_type(path)[0] or 'application/octet-stream'
                start_response('200 OK',  (('Content-type',mime_type),) )
                return f.read().replace(b'$port_number', str(settings.port_number).encode())

        elif path == "/comment_delete_success":
            start_response('200 OK',  () )
            return b'Successfully deleted comment'

        elif path == "/comment_delete_fail":
            start_response('200 OK',  () )
            return b'Failed to deleted comment'

        else:
            return channel.get_channel_page_general_url(env, start_response)

    elif method == "POST":
        post_parameters = urllib.parse.parse_qs(env['wsgi.input'].read().decode())
        env['post_parameters'] = post_parameters
        env['parameters'].update(post_parameters)

        try:
            handler = post_handlers[path_parts[0]]
        except KeyError:
            pass
        else:
            return handler(env, start_response)

        start_response('404 Not Found', ())
        return b'404 Not Found'

    else:
        start_response('501 Not Implemented', ())
        return b'501 Not Implemented'