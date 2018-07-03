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






def youtube_obfuscated_endian(offset):
    if offset < 128:
        return bytes((offset,))
    first_byte = 255 & offset
    second_byte = 255 & (offset >> 7)
    second_byte = second_byte | 1
    
    # The next 2 bytes encode the offset in little endian order,
    #  BUT, it's done in a strange way. The least significant bit (LSB) of the second byte is not part
    #  of the offset. Instead, to get the number which the two bytes encode, that LSB
    #  of the second byte is combined with the most significant bit (MSB) of the first byte
    #  in a logical AND. Replace the two bits with the result of the AND to get the two little endian
    #  bytes that represent the offset.

    return bytes((first_byte, second_byte))

    
    
# just some garbage that's required, don't know what it means, if it means anything.
ctoken_header = b'\xe2\xa9\x85\xb2\x02'    # e2 a9 85 b2 02

def byte(x):
    return bytes((x,))

# TL;DR: the offset is hidden inside 3 nested base 64 encodes with random junk data added on the side periodically
def create_ctoken(playlist_id, offset):
    obfuscated_offset = b'\x08' + youtube_obfuscated_endian(offset) # 0x08 slapped on for no apparent reason
    obfuscated_offset = b'PT:' + base64.urlsafe_b64encode(obfuscated_offset).replace(b'=', b'')
    obfuscated_offset = b'z' + byte(len(obfuscated_offset)) + obfuscated_offset
    obfuscated_offset = base64.urlsafe_b64encode(obfuscated_offset).replace(b'=', b'%3D')

    playlist_bytes = b'VL' + bytes(playlist_id, 'ascii')
    main_info = b'\x12' + byte(len(playlist_bytes)) + playlist_bytes + b'\x1a' + byte(len(obfuscated_offset)) + obfuscated_offset
    
    ctoken = base64.urlsafe_b64encode(ctoken_header + byte(len(main_info)) + main_info)

    return ctoken.decode('ascii')

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

def playlist_first_page(playlist_id):
    url = 'https://m.youtube.com/playlist?list=' + playlist_id + '&ajax=1&disable_polymer=true'
    content = common.fetch_url(url, common.mobile_ua + headers_1)
    if content[0:4] == b")]}'":
        content = content[4:]
    content = json.loads(common.uppercase_escape(content.decode('utf-8')))
    return content

ajax_info_dispatch = {
    'view_count_text':  ('views',       common.get_text),
    'num_videos_text':  ('size',        lambda node: common.get_text(node).split(' ')[0]),
    'thumbnail':        ('thumbnail',   lambda node: node.url),
    'title':            ('title',       common.get_text),
    'owner_text':       ('author',      common.get_text),
    'owner_endpoint':   ('author_url',  lambda node: node.url),
    'description':      ('description', common.get_formatted_text),

}
def metadata_info(ajax_json):
    info = {}
    try:
        for key, node in ajax_json.items():
            try:
                simple_key, function = dispatch[key]
            except KeyError:
                continue
            info[simple_key] = function(node)
        return info
    except (KeyError,IndexError):
        print(ajax_json)
        raise


    

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
    print("Sending playlist ajax request")
    content = common.fetch_url(url, headers)
    with open('playlist_debug', 'wb') as f:
        f.write(content)
    content = content[4:]
    print("Finished recieving playlist response")

    info = json.loads(common.uppercase_escape(content.decode('utf-8')))
    return info

def get_playlist_videos(ajax_json):
    videos = []
    #info = get_bloated_playlist_videos(playlist_id, page)
    #print(info)
    video_list = ajax_json['content']['continuation_contents']['contents']
    
    
    for video_json_crap in video_list:
        try:
            videos.append({
                "title": video_json_crap["title"]['runs'][0]['text'],
                "id": video_json_crap["video_id"],
                "views": "",
                "duration": common.default_multi_get(video_json_crap, 'length', 'runs', 0, 'text', default=''), # livestreams dont have a length
                "author": video_json_crap['short_byline']['runs'][0]['text'],
                "author_url": '',
                "published": '',
                'playlist_index': '',
                
            })
        except (KeyError, IndexError):
            print(video_json_crap)
            raise
    return videos

def get_playlist_videos_format2(playlist_id, page):
    videos = []
    info = get_bloated_playlist_videos(playlist_id, page)
    video_list = info['response']['continuationContents']['playlistVideoListContinuation']['contents']
    
    for video_json_crap in video_list:
        
        video_json_crap = video_json_crap['videoRenderer']

        try:
            videos.append({
                "title": video_json_crap["title"]['runs'][0]['text'],
                "video_id": video_json_crap["videoId"],
                "views": "",
                "duration": common.default_multi_get(video_json_crap, 'lengthText', 'runs', 0, 'text', default=''), # livestreams dont have a length
                "uploader": video_json_crap['shortBylineText']['runs'][0]['text'],
                "uploader_url": common.ORIGIN_URL + video_json_crap['shortBylineText']['runs'][0]['navigationEndpoint']['commandMetadata']['webCommandMetadata']['url'],
                "published": common.default_multi_get(video_json_crap, 'publishedTimeText', 'simpleText', default=''),
                'playlist_index': video_json_crap['index']['runs'][0]['text'],
                
            })
        except (KeyError, IndexError):
            print(video_json_crap)
            raise
    return videos
    
    
def playlist_videos_html(ajax_json):
    result = ''
    for info in get_playlist_videos(ajax_json):
        result += common.small_video_item_html(info)
    return result

playlist_stat_template = Template('''
<div>$stat</div>''')
def get_playlist_page(query_string):
    parameters = urllib.parse.parse_qs(query_string)
    playlist_id = parameters['list'][0]
    page = parameters.get("page", "1")[0]
    if page == "1":
        first_page_json = playlist_first_page(playlist_id)
        this_page_json = first_page_json
    else:
        tasks = (
            gevent.spawn(playlist_first_page, playlist_id ), 
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
    page_buttons = common.page_buttons_html(int(page), math.ceil(video_count/20), common.URL_ORIGIN + "/playlist", query_string)

    html_ready = common.get_html_ready(metadata)
    html_ready['page_title'] = html_ready['title'] + ' - Page ' + str(page)

    stats = ''
    stats += playlist_stat_template.substitute(stat=html_ready['size'] + ' videos')
    stats += playlist_stat_template.substitute(stat=html_ready['views'])
    return yt_playlist_template.substitute(
        videos          = videos_html,
        page_buttons    = page_buttons,
        stats = stats,
        **html_ready
    )