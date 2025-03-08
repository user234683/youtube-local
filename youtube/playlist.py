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

    continuation_info = proto.string(3, proto.percent_b64encode(offset))

    playlist_id = proto.string(2, 'VL' + playlist_id)
    pointless_nest = proto.string(80226972, playlist_id + continuation_info)

    return base64.urlsafe_b64encode(pointless_nest).decode('ascii')


def playlist_first_page(playlist_id, report_text="Retrieved playlist",
                        use_mobile=False):
    if use_mobile:
        url = 'https://m.youtube.com/playlist?list=' + playlist_id + '&pbj=1'
        content = util.fetch_url(
            url, util.mobile_xhr_headers,
            report_text=report_text, debug_name='playlist_first_page'
        )
        content = json.loads(content.decode('utf-8'))
    else:
        url = 'https://www.youtube.com/playlist?list=' + playlist_id + '&pbj=1'
        content = util.fetch_url(
            url, util.desktop_xhr_headers,
            report_text=report_text, debug_name='playlist_first_page'
        )
        content = json.loads(content.decode('utf-8'))

    return content


def get_videos(playlist_id, page, include_shorts=True, use_mobile=False,
               report_text='Retrieved playlist'):
    # mobile requests return 20 videos per page
    if use_mobile:
        page_size = 20
        headers = util.mobile_xhr_headers
    # desktop requests return 100 videos per page
    else:
        page_size = 100
        headers = util.desktop_xhr_headers

    url = "https://m.youtube.com/playlist?ctoken="
    url += playlist_ctoken(playlist_id, (int(page)-1)*page_size,
                           include_shorts=include_shorts)
    url += "&pbj=1"
    content = util.fetch_url(
        url, headers, report_text=report_text,
        debug_name='playlist_videos'
    )

    info = json.loads(content.decode('utf-8'))
    return info


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
                report_text="Retrieved playlist info", use_mobile=True
            ),
            gevent.spawn(get_videos, playlist_id, page)
        )
        gevent.joinall(tasks)
        util.check_gevent_exceptions(*tasks)
        first_page_json, this_page_json = tasks[0].value, tasks[1].value

    info = yt_data_extract.extract_playlist_info(this_page_json)
    if info['error']:
        return flask.render_template('error.html', error_message=info['error'])

    if page != '1':
        info['metadata'] = yt_data_extract.extract_playlist_metadata(first_page_json)

    util.prefix_urls(info['metadata'])
    for item in info.get('items', ()):
        util.prefix_urls(item)
        util.add_extra_html_info(item)
        if 'id' in item:
            item['thumbnail'] = f"{settings.img_prefix}https://i.ytimg.com/vi/{item['id']}/hqdefault.jpg"

        item['url'] += '&list=' + playlist_id
        if item['index']:
            item['url'] += '&index=' + str(item['index'])

    video_count = yt_data_extract.deep_get(info, 'metadata', 'video_count')
    if video_count is None:
        video_count = 1000

    return flask.render_template(
        'playlist.html',
        header_playlist_names=local_playlist.get_playlist_names(),
        video_list=info.get('items', []),
        num_pages=math.ceil(video_count/100),
        parameters_dictionary=request.args,

        **info['metadata']
    ).encode('utf-8')
