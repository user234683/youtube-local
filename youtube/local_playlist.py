import os
import json
from youtube.template import Template
from youtube import common
import html
import gevent
import urllib
import settings

playlists_directory = os.path.join(settings.data_dir, "playlists")
thumbnails_directory = os.path.join(settings.data_dir, "playlist_thumbnails")

with open('yt_local_playlist_template.html', 'r', encoding='utf-8') as file:
    local_playlist_template = Template(file.read())

def video_ids_in_playlist(name):
    try:
        with open(os.path.join(playlists_directory, name + ".txt"), 'r', encoding='utf-8') as file:
            videos = file.read()
        return set(json.loads(video)['id'] for video in videos.splitlines())
    except FileNotFoundError:
        return set()

def add_to_playlist(name, video_info_list):
    if not os.path.exists(playlists_directory):
        os.makedirs(playlists_directory)
    ids = video_ids_in_playlist(name)
    missing_thumbnails = []
    with open(os.path.join(playlists_directory, name + ".txt"), "a", encoding='utf-8') as file:
        for info in video_info_list:
            id = json.loads(info)['id']
            if id not in ids:
                file.write(info + "\n")
                missing_thumbnails.append(id)
    gevent.spawn(download_thumbnails, name, missing_thumbnails)

def download_thumbnail(playlist_name, video_id):
    url = "https://i.ytimg.com/vi/" + video_id + "/mqdefault.jpg"
    save_location = os.path.join(thumbnails_directory, playlist_name, video_id + ".jpg")
    try:
        thumbnail = common.fetch_url(url, report_text="Saved local playlist thumbnail: " + video_id)
    except urllib.error.HTTPError as e:
        print("Failed to download thumbnail for " + video_id + ": " + str(e))
        return
    try:
        f = open(save_location, 'wb')
    except FileNotFoundError:
        os.makedirs(os.path.join(thumbnails_directory, playlist_name))
        f = open(save_location, 'wb')
    f.write(thumbnail)
    f.close()

def download_thumbnails(playlist_name, ids):
    # only do 5 at a time
    # do the n where n is divisible by 5
    i = -1
    for i in range(0, int(len(ids)/5) - 1 ):
        gevent.joinall([gevent.spawn(download_thumbnail, playlist_name, ids[j]) for j in range(i*5, i*5 + 5)])
    # do the remainders (< 5)
    gevent.joinall([gevent.spawn(download_thumbnail, playlist_name, ids[j]) for j in range(i*5 + 5, len(ids))])
            
        

def get_local_playlist_page(name):
    try:
        thumbnails = set(os.listdir(os.path.join(thumbnails_directory, name)))
    except FileNotFoundError:
        thumbnails = set()
    missing_thumbnails = []

    videos_html = ''
    with open(os.path.join(playlists_directory, name + ".txt"), 'r', encoding='utf-8') as file:
        videos = file.read()
    videos = videos.splitlines()
    for video in videos:
        try:
            info = json.loads(video)
            if info['id'] + ".jpg" in thumbnails:
                info['thumbnail'] = "/youtube.com/data/playlist_thumbnails/" + name + "/" + info['id'] + ".jpg"
            else:
                info['thumbnail'] = common.get_thumbnail_url(info['id'])
                missing_thumbnails.append(info['id'])
            videos_html += common.video_item_html(info, common.small_video_item_template)
        except json.decoder.JSONDecodeError:
            pass
    gevent.spawn(download_thumbnails, name, missing_thumbnails)
    return local_playlist_template.substitute(
        page_title = name + ' - Local playlist',
        header = common.get_header(),
        videos = videos_html,
        title = name,
        page_buttons = ''
    )

def get_playlist_names():
    try:
        items = os.listdir(playlists_directory)
    except FileNotFoundError:
        return
    for item in items:
        name, ext = os.path.splitext(item)
        if ext == '.txt':
            yield name

def remove_from_playlist(name, video_info_list):
    ids = [json.loads(video)['id'] for video in video_info_list]
    with open(os.path.join(playlists_directory, name + ".txt"), 'r', encoding='utf-8') as file:
        videos = file.read()
    videos_in = videos.splitlines()
    videos_out = []
    for video in videos_in:
        if json.loads(video)['id'] not in ids:
            videos_out.append(video)
    with open(os.path.join(playlists_directory, name + ".txt"), 'w', encoding='utf-8') as file:
        file.write("\n".join(videos_out) + "\n")

    try:
        thumbnails = set(os.listdir(os.path.join(thumbnails_directory, name)))
    except FileNotFoundError:
        pass
    else:
        to_delete = thumbnails & set(id + ".jpg" for id in ids)
        for file in to_delete:
            os.remove(os.path.join(thumbnails_directory, name, file))

def get_playlists_list_page():
    page = '''<ul>\n'''
    list_item_template = Template('''    <li><a href="$url">$name</a></li>\n''')
    for name in get_playlist_names():
        page += list_item_template.substitute(url = html.escape(common.URL_ORIGIN + '/playlists/' + name), name = html.escape(name))
    page += '''</ul>\n'''
    return common.yt_basic_template.substitute(
        page_title = "Local playlists",
        header = common.get_header(),
        style = '',
        page = page,
    )


def get_playlist_page(env, start_response):
    start_response('200 OK', [('Content-type','text/html'),])
    path_parts = env['path_parts']
    if len(path_parts) == 1:
        return get_playlists_list_page().encode('utf-8')
    else:
        return get_local_playlist_page(path_parts[1]).encode('utf-8')

def path_edit_playlist(env, start_response):
    '''Called when making changes to the playlist from that playlist's page'''
    parameters = env['parameters']
    if parameters['action'][0] == 'remove':
        playlist_name = env['path_parts'][1]
        remove_from_playlist(playlist_name, parameters['video_info_list'])
        start_response('303 See Other', [('Location', common.URL_ORIGIN + env['PATH_INFO']),] )
        return b''

    else:
        start_response('400 Bad Request', ())
        return b'400 Bad Request'

def edit_playlist(env, start_response):
    '''Called when adding videos to a playlist from elsewhere'''
    parameters = env['parameters']
    if parameters['action'][0] == 'add':
        add_to_playlist(parameters['playlist_name'][0], parameters['video_info_list'])
        start_response('204 No Content', ())
    else:
        start_response('400 Bad Request', ())
        return b'400 Bad Request'
