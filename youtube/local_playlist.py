import os
import json
from youtube.template import Template
from youtube import common
import html

playlists_directory = os.path.normpath("data/playlists")
with open('yt_local_playlist_template.html', 'r', encoding='utf-8') as file:
    local_playlist_template = Template(file.read())

def add_to_playlist(name, video_info_list):
    if not os.path.exists(playlists_directory):
        os.makedirs(playlists_directory)
    with open(os.path.join(playlists_directory, name + ".txt"), "a", encoding='utf-8') as file:
        for info in video_info_list:
            file.write(info + "\n")
        
        
def get_local_playlist_page(name):
    videos_html = ''
    with open(os.path.join(playlists_directory, name + ".txt"), 'r', encoding='utf-8') as file:
        videos = file.read()
    videos = videos.splitlines()
    for video in videos:
        try:
            info = json.loads(video)
            info['thumbnail'] = common.get_thumbnail_url(info['id'])
            videos_html += common.video_item_html(info, common.small_video_item_template)
        except json.decoder.JSONDecodeError:
            pass
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


def get_playlist_page(url, query_string=''):
    url = url.rstrip('/').lstrip('/')
    if url == '':
        return get_playlists_list_page()
    else:
        return get_local_playlist_page(url)

