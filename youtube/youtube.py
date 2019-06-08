import mimetypes
import urllib.parse
import os
import re
from youtube import local_playlist, watch, search, playlist, channel, comments, post_comment, accounts, util, subscriptions
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

    'subscriptions':            subscriptions.get_subscriptions_page,
    'subscription_manager':     subscriptions.get_subscription_manager_page,
}
post_handlers = {
    'edit_playlist':    local_playlist.edit_playlist,
    'playlists':        local_playlist.path_edit_playlist,

    'login':            accounts.add_account,
    'comments':         post_comment.post_comment,
    'post_comment':     post_comment.post_comment,
    'delete_comment':   post_comment.delete_comment,

    'subscriptions':    subscriptions.post_subscriptions_page,
    'subscription_manager':     subscriptions.post_subscription_manager_page,
    'import_subscriptions':     subscriptions.import_subscriptions,
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

        elif path.startswith('/data/playlist_thumbnails/') or path.startswith('/data/subscription_thumbnails/'):
            with open(os.path.join(settings.data_dir, os.path.normpath(path[6:])), 'rb') as f:
                start_response('200 OK',  (('Content-type', "image/jpeg"),) )
                return f.read()

        elif path.startswith("/api/"):
            start_response('200 OK',  [('Content-type', 'text/vtt'),] )
            result = util.fetch_url('https://www.youtube.com' + path + ('?' + query_string if query_string else ''))
            result = result.replace(b"align:start position:0%", b"")
            return result

        elif path == "/opensearch.xml":
            with open("youtube" + path, 'rb') as f:
                mime_type = mimetypes.guess_type(path)[0] or 'application/octet-stream'
                start_response('200 OK',  (('Content-type',mime_type),) )
                return f.read().replace(b'$port_number', str(settings.port_number).encode())

        elif path == "/comment_delete_success":
            start_response('200 OK', [('Content-type', 'text/plain'),] )
            return b'Successfully deleted comment'

        elif path == "/comment_delete_fail":
            start_response('200 OK',  [('Content-type', 'text/plain'),] )
            return b'Failed to deleted comment'

        else:
            return channel.get_channel_page_general_url(env, start_response)

    elif method == "POST":
        content_type = env['CONTENT_TYPE']
        if content_type == 'application/x-www-form-urlencoded':
            post_parameters = urllib.parse.parse_qs(env['wsgi.input'].read().decode())
            env['post_parameters'] = post_parameters
            env['parameters'].update(post_parameters)

        # Ugly hack that will be removed once I clean up this trainwreck and switch to a microframework
        # Only supports a single file with no other fields
        elif content_type.startswith('multipart/form-data'):
            content = env['wsgi.input'].read()

            # find double line break
            file_start = content.find(b'\r\n\r\n')
            if file_start == -1:
                start_response('400 Bad Request', ())
                return b'400 Bad Request'

            file_start += 4

            lines = content[0:file_start].splitlines()
            boundary = lines[0]

            file_end = content.find(boundary, file_start)
            if file_end == -1:
                start_response('400 Bad Request', ())
                return b'400 Bad Request'
            file_end -= 2  # Subtract newlines
            file = content[file_start:file_end]

            properties = dict()
            for line in lines[1:]:
                line = line.decode('utf-8')
                colon = line.find(':')
                if colon == -1:
                    continue
                properties[line[0:colon]] = line[colon+2:]

            mime_type = properties['Content-Type']
            field_name = re.search(r'name="([^"]*)"' , properties['Content-Disposition'])
            if field_name is None:
                start_response('400 Bad Request', ())
                return b'400 Bad Request'
            field_name = field_name.group(1)

            env['post_parameters'] = {field_name: (mime_type, file)}
            env['parameters'][field_name] = (mime_type, file)

        else:
            start_response('400 Bad Request', ())
            return b'400 Bad Request'

        try:
            handler = post_handlers[path_parts[0]]
        except KeyError:
            pass
        else:
            return handler(env, start_response)

        start_response('404 Not Found', [('Content-type', 'text/plain'),])
        return b'404 Not Found'

    else:
        start_response('501 Not Implemented', [('Content-type', 'text/plain'),])
        return b'501 Not Implemented'
