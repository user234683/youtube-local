from youtube import util, yt_data_extract
from youtube import yt_app
import settings

import os
import json
import html
import gevent
import urllib
import math

import flask
from flask import request

playlists_directory = os.path.join(settings.data_dir, "playlists")
thumbnails_directory = os.path.join(settings.data_dir, "playlist_thumbnails")

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
    gevent.spawn(util.download_thumbnails, os.path.join(thumbnails_directory, name), missing_thumbnails)


def get_local_playlist_videos(name, offset=0, amount=50):
    try:
        thumbnails = set(os.listdir(os.path.join(thumbnails_directory, name)))
    except FileNotFoundError:
        thumbnails = set()
    missing_thumbnails = []

    videos = []
    with open(os.path.join(playlists_directory, name + ".txt"), 'r', encoding='utf-8') as file:
        data = file.read()
    videos_json = data.splitlines()
    for video_json in videos_json:
        try:
            info = json.loads(video_json)
            if info['id'] + ".jpg" in thumbnails:
                info['thumbnail'] = "https://youtube.com/data/playlist_thumbnails/" + name + "/" + info['id'] + ".jpg"
            else:
                info['thumbnail'] = util.get_thumbnail_url(info['id'])
                missing_thumbnails.append(info['id'])
            info['type'] = 'video'
            util.add_extra_html_info(info)
            videos.append(info)
        except json.decoder.JSONDecodeError:
            if not video_json.strip() == '':
                print('Corrupt playlist video entry: ' + video_json)
    gevent.spawn(util.download_thumbnails, os.path.join(thumbnails_directory, name), missing_thumbnails)
    return videos[offset:offset+amount], len(videos)

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

    return len(videos_out)


@yt_app.route('/playlists', methods=['GET'])
@yt_app.route('/playlists/<playlist_name>', methods=['GET'])
def get_local_playlist_page(playlist_name=None):
    if playlist_name is None:
        playlists = [(name, util.URL_ORIGIN + '/playlists/' + name) for name in get_playlist_names()]
        return flask.render_template('local_playlists_list.html', playlists=playlists)
    else:
        page = int(request.args.get('page', 1))
        offset = 50*(page - 1)
        videos, num_videos = get_local_playlist_videos(playlist_name, offset=offset, amount=50)
        return flask.render_template('local_playlist.html',
            header_playlist_names = get_playlist_names(),
            playlist_name = playlist_name,
            videos = videos,
            num_pages = math.ceil(num_videos/50),
            parameters_dictionary = request.args,
        )

@yt_app.route('/playlists/<playlist_name>', methods=['POST'])
def path_edit_playlist(playlist_name):
    '''Called when making changes to the playlist from that playlist's page'''
    if request.values['action'] == 'remove':
        videos_to_remove = request.values.getlist('video_info_list')
        number_of_videos_remaining = remove_from_playlist(playlist_name, videos_to_remove)
        redirect_page_number = min(int(request.values.get('page', 1)), math.ceil(number_of_videos_remaining/50))
        return flask.redirect(util.URL_ORIGIN + request.path + '?page=' + str(redirect_page_number))
    else:
        flask.abort(400)

@yt_app.route('/edit_playlist', methods=['POST'])
def edit_playlist():
    '''Called when adding videos to a playlist from elsewhere'''
    if request.values['action'] == 'add':
        add_to_playlist(request.values['playlist_name'], request.values.getlist('video_info_list'))
        return '', 204
    else:
        flask.abort(400)

@yt_app.route('/data/playlist_thumbnails/<playlist_name>/<thumbnail>')
def serve_thumbnail(playlist_name, thumbnail):
    # .. is necessary because flask always uses the application directory at ./youtube, not the working directory
    return flask.send_from_directory(os.path.join('..', thumbnails_directory, playlist_name), thumbnail)
