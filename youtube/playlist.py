from youtube import util, yt_data_extract, proto
from youtube import yt_app

import base64
import urllib
import json
import string
import gevent
import math
from flask import request
import flask





def playlist_ctoken(playlist_id, offset):  
    
    offset = proto.uint(1, offset)
    # this is just obfuscation as far as I can tell. It doesn't even follow protobuf
    offset = b'PT:' + proto.unpadded_b64encode(offset)
    offset = proto.string(15, offset)

    continuation_info = proto.string( 3, proto.percent_b64encode(offset) )
    
    playlist_id = proto.string(2, 'VL' + playlist_id )
    pointless_nest = proto.string(80226972, playlist_id + continuation_info)

    return base64.urlsafe_b64encode(pointless_nest).decode('ascii')

# initial request types:
#   polymer_json: https://m.youtube.com/playlist?list=PLv3TTBr1W_9tppikBxAE_G6qjWdBljBHJ&pbj=1&lact=0
#   ajax json:    https://m.youtube.com/playlist?list=PLv3TTBr1W_9tppikBxAE_G6qjWdBljBHJ&pbj=1&lact=0 with header X-YouTube-Client-Version: 1.20180418


# continuation request types:
#   polymer_json: https://m.youtube.com/playlist?&ctoken=[...]&pbj=1
#   ajax json:    https://m.youtube.com/playlist?action_continuation=1&ajax=1&ctoken=[...]


headers_1 = (
    ('Accept', '*/*'),
    ('Accept-Language', 'en-US,en;q=0.5'),
    ('X-YouTube-Client-Name', '2'),
    ('X-YouTube-Client-Version', '2.20180614'),
)

def playlist_first_page(playlist_id, report_text = "Retrieved playlist"):
    url = 'https://m.youtube.com/playlist?list=' + playlist_id + '&pbj=1'
    content = util.fetch_url(url, util.mobile_ua + headers_1, report_text=report_text, debug_name='playlist_first_page')
    content = json.loads(util.uppercase_escape(content.decode('utf-8')))

    return content
    

#https://m.youtube.com/playlist?itct=CBMQybcCIhMIptj9xJaJ2wIV2JKcCh3Idwu-&ctoken=4qmFsgI2EiRWTFBMT3kwajlBdmxWWlB0bzZJa2pLZnB1MFNjeC0tN1BHVEMaDmVnWlFWRHBEUWxFJTNE&pbj=1
def get_videos(playlist_id, page):

    url = "https://m.youtube.com/playlist?ctoken=" + playlist_ctoken(playlist_id, (int(page)-1)*20) + "&pbj=1"
    headers = {
        'User-Agent': '  Mozilla/5.0 (iPhone; CPU iPhone OS 10_3_1 like Mac OS X) AppleWebKit/603.1.30 (KHTML, like Gecko) Version/10.0 Mobile/14E304 Safari/602.1',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'X-YouTube-Client-Name': '2',
        'X-YouTube-Client-Version': '2.20180508',
    }

    content = util.fetch_url(url, headers, report_text="Retrieved playlist", debug_name='playlist_videos')

    info = json.loads(util.uppercase_escape(content.decode('utf-8')))
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
            gevent.spawn(playlist_first_page, playlist_id, report_text="Retrieved playlist info" ), 
            gevent.spawn(get_videos, playlist_id, page)
        )
        gevent.joinall(tasks)
        first_page_json, this_page_json = tasks[0].value, tasks[1].value
    
    try:    # first page
        video_list = this_page_json['response']['contents']['singleColumnBrowseResultsRenderer']['tabs'][0]['tabRenderer']['content']['sectionListRenderer']['contents'][0]['itemSectionRenderer']['contents'][0]['playlistVideoListRenderer']['contents']
    except KeyError:    # other pages
        video_list = this_page_json['response']['continuationContents']['playlistVideoListContinuation']['contents']

    parsed_video_list = [yt_data_extract.parse_info_prepare_for_html(video_json) for video_json in video_list]


    metadata = yt_data_extract.renderer_info(first_page_json['response']['header'])
    yt_data_extract.prefix_urls(metadata)

    if 'description' not in metadata:
        metadata['description'] = ''

    video_count = int(metadata['size'].replace(',', ''))
    metadata['size'] += ' videos'

    return flask.render_template('playlist.html',
        video_list = parsed_video_list,
        num_pages = math.ceil(video_count/20),
        parameters_dictionary = request.args,

        **metadata
    ).encode('utf-8')
