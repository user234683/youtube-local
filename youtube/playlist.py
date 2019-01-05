import base64
import youtube.common as common
import urllib
import json
from string import Template
import youtube.proto as proto
import gevent
import math

with open("yt_playlist_template.html", "r") as file:
    yt_playlist_template = Template(file.read())






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
    ('X-YouTube-Client-Name', '1'),
    ('X-YouTube-Client-Version', '2.20180614'),
)

def playlist_first_page(playlist_id, report_text = "Retrieved playlist"):
    url = 'https://m.youtube.com/playlist?list=' + playlist_id + '&ajax=1&disable_polymer=true'
    content = common.fetch_url(url, common.mobile_ua + headers_1, report_text=report_text)
    if content[0:4] == b")]}'":
        content = content[4:]
    content = json.loads(common.uppercase_escape(content.decode('utf-8')))
    return content
    

#https://m.youtube.com/playlist?itct=CBMQybcCIhMIptj9xJaJ2wIV2JKcCh3Idwu-&ctoken=4qmFsgI2EiRWTFBMT3kwajlBdmxWWlB0bzZJa2pLZnB1MFNjeC0tN1BHVEMaDmVnWlFWRHBEUWxFJTNE&pbj=1
def get_videos_ajax(playlist_id, page):

    url = "https://m.youtube.com/playlist?action_continuation=1&ajax=1&ctoken=" + playlist_ctoken(playlist_id, (int(page)-1)*20)
    headers = {
        'User-Agent': '  Mozilla/5.0 (iPhone; CPU iPhone OS 10_3_1 like Mac OS X) AppleWebKit/603.1.30 (KHTML, like Gecko) Version/10.0 Mobile/14E304 Safari/602.1',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'X-YouTube-Client-Name': '2',
        'X-YouTube-Client-Version': '1.20180508',
    }

    content = common.fetch_url(url, headers, report_text="Retrieved playlist")
    '''with open('debug/playlist_debug', 'wb') as f:
        f.write(content)'''
    content = content[4:]

    info = json.loads(common.uppercase_escape(content.decode('utf-8')))
    return info


playlist_stat_template = Template('''
<div>$stat</div>''')
def get_playlist_page(env, start_response):
    start_response('200 OK', [('Content-type','text/html'),])
    parameters = env['fields']
    playlist_id = parameters['list'][0]
    page = parameters.get("page", "1")[0]
    if page == "1":
        first_page_json = playlist_first_page(playlist_id)
        this_page_json = first_page_json
    else:
        tasks = (
            gevent.spawn(playlist_first_page, playlist_id, report_text="Retrieved playlist info" ), 
            gevent.spawn(get_videos_ajax, playlist_id, page)
        )
        gevent.joinall(tasks)
        first_page_json, this_page_json = tasks[0].value, tasks[1].value
    
    try:
        video_list = this_page_json['content']['section_list']['contents'][0]['contents'][0]['contents']
    except KeyError:
        video_list = this_page_json['content']['continuation_contents']['contents']
    videos_html = ''
    for video_json in video_list:
        info = common.ajax_info(video_json)
        videos_html += common.video_item_html(info, common.small_video_item_template)


    metadata = common.ajax_info(first_page_json['content']['playlist_header'])
    video_count = int(metadata['size'].replace(',', ''))
    page_buttons = common.page_buttons_html(int(page), math.ceil(video_count/20), common.URL_ORIGIN + "/playlist", env['QUERY_STRING'])

    html_ready = common.get_html_ready(metadata)
    html_ready['page_title'] = html_ready['title'] + ' - Page ' + str(page)

    stats = ''
    stats += playlist_stat_template.substitute(stat=html_ready['size'] + ' videos')
    stats += playlist_stat_template.substitute(stat=html_ready['views'])
    return yt_playlist_template.substitute(
        header          = common.get_header(),
        videos          = videos_html,
        page_buttons    = page_buttons,
        stats = stats,
        **html_ready
    ).encode('utf-8')