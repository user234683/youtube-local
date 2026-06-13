from youtube import util, yt_data_extract, proto, local_playlist
from youtube import yt_app
import settings

import base64
import urllib
import json
import string
import gevent
import math
from flask import request
import flask


def playlist_ctoken(playlist_id, offset, include_shorts=True):

    offset = proto.uint(1, offset)
    offset = b'PT:' + proto.unpadded_b64encode(offset)
    offset = proto.string(15, offset)
    if not include_shorts:
        offset += proto.string(104, proto.uint(2, 1))

    continuation_info = proto.string( 3, proto.percent_b64encode(offset) )

    playlist_id = proto.string(2, 'VL' + playlist_id )
    pointless_nest = proto.string(80226972,
        playlist_id + continuation_info + proto.string(35, playlist_id)
    )

    return base64.urlsafe_b64encode(pointless_nest).decode('ascii')


def playlist_first_page(playlist_id, report_text='Retrieved playlist'):
    # Use innertube API (pbj=1 no longer works for many playlists)
    key = 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8'
    url = 'https://www.youtube.com/youtubei/v1/browse?key=' + key

    data = {
        'context': {
            'client': {
                'hl': 'en',
                'gl': 'US',
                'clientName': 'WEB',
                'clientVersion': '2.20240327.00.00',
            },
        },
        'browseId': 'VL' + playlist_id,
    }

    content_type_header = (('Content-Type', 'application/json'),)
    content = util.fetch_url(
        url, util.desktop_xhr_headers + content_type_header,
        data=json.dumps(data),
        report_text=report_text, debug_name='playlist_first_page'
    )
    return json.loads(content.decode('utf-8'))


def get_videos(playlist_id, page, include_shorts=True, page_size=100,
               report_text='Retrieved playlist'):
    key = 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8'
    url = 'https://www.youtube.com/youtubei/v1/browse?key=' + key

    ctoken = playlist_ctoken(playlist_id, (int(page)-1)*page_size,
                             include_shorts=include_shorts)

    data = {
        'context': {
            'client': {
                'hl': 'en',
                'gl': 'US',
                'clientName': 'WEB',
                'clientVersion': '2.20240327.00.00',
            },
        },
        'continuation': ctoken,
    }

    content_type_header = (('Content-Type', 'application/json'),)
    content = util.fetch_url(
        url, util.desktop_xhr_headers + content_type_header,
        data=json.dumps(data),
        report_text=report_text, debug_name='playlist_videos'
    )
    return json.loads(content.decode('utf-8'))


@yt_app.route('/playlist')
def get_playlist_page():
    if 'list' not in request.args:
        abort(400)

    playlist_id = request.args.get('list')
    page = request.args.get('page', '1')

    if page == '1':
        first_page_json = playlist_first_page(playlist_id)
        this_page_json = first_page_json
    else:
        tasks = (
            gevent.spawn(
                playlist_first_page, playlist_id,
                report_text='Retrieved playlist info'
            ),
            gevent.spawn(get_videos, playlist_id, page)
        )
        gevent.joinall(tasks)
        util.check_gevent_exceptions(*tasks)
        first_page_json, this_page_json = tasks[0].value, tasks[1].value

    info = yt_data_extract.extract_playlist_info(this_page_json)
    if info['error']:
        return flask.render_template('error.html', error_message = info['error'])

    if page != '1':
        info['metadata'] = yt_data_extract.extract_playlist_metadata(first_page_json)

    util.prefix_urls(info['metadata'])
    for item in info['items']:
        if item['error']:
            continue
        util.prefix_urls(item)
        util.add_extra_html_info(item)
        if item['id']:
            item['thumbnail'] = settings.img_prefix + 'https://i.ytimg.com/vi/' + item['id'] + '/default.jpg'
        if item['url']:
            item['url'] += '&list=' + playlist_id
            if item['index']:
                item['url'] += '&index=' + str(item['index'])

    video_count = yt_data_extract.deep_get(info, 'metadata', 'video_count')
    if video_count is None:
        video_count = 1000

    return flask.render_template('playlist.html',
        header_playlist_names = local_playlist.get_playlist_names(),
        video_list = info.get('items', []),
        num_pages = math.ceil(video_count/100),
        parameters_dictionary = request.args,

        **info['metadata']
    ).encode('utf-8')
