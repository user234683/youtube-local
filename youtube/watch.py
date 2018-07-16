from youtube_dl.YoutubeDL import YoutubeDL
import json
import urllib
from string import Template
import html
import youtube.common as common
from youtube.common import default_multi_get, get_thumbnail_url, video_id, URL_ORIGIN
import youtube.comments as comments
import gevent
import settings

video_height_priority = (360, 480, 240, 720, 1080)


_formats = {
    '5': {'ext': 'flv', 'width': 400, 'height': 240, 'acodec': 'mp3', 'abr': 64, 'vcodec': 'h263'},
    '6': {'ext': 'flv', 'width': 450, 'height': 270, 'acodec': 'mp3', 'abr': 64, 'vcodec': 'h263'},
    '13': {'ext': '3gp', 'acodec': 'aac', 'vcodec': 'mp4v'},
    '17': {'ext': '3gp', 'width': 176, 'height': 144, 'acodec': 'aac', 'abr': 24, 'vcodec': 'mp4v'},
    '18': {'ext': 'mp4', 'width': 640, 'height': 360, 'acodec': 'aac', 'abr': 96, 'vcodec': 'h264'},
    '22': {'ext': 'mp4', 'width': 1280, 'height': 720, 'acodec': 'aac', 'abr': 192, 'vcodec': 'h264'},
    '34': {'ext': 'flv', 'width': 640, 'height': 360, 'acodec': 'aac', 'abr': 128, 'vcodec': 'h264'},
    '35': {'ext': 'flv', 'width': 854, 'height': 480, 'acodec': 'aac', 'abr': 128, 'vcodec': 'h264'},
    # itag 36 videos are either 320x180 (BaW_jenozKc) or 320x240 (__2ABJjxzNo), abr varies as well
    '36': {'ext': '3gp', 'width': 320, 'acodec': 'aac', 'vcodec': 'mp4v'},
    '37': {'ext': 'mp4', 'width': 1920, 'height': 1080, 'acodec': 'aac', 'abr': 192, 'vcodec': 'h264'},
    '38': {'ext': 'mp4', 'width': 4096, 'height': 3072, 'acodec': 'aac', 'abr': 192, 'vcodec': 'h264'},
    '43': {'ext': 'webm', 'width': 640, 'height': 360, 'acodec': 'vorbis', 'abr': 128, 'vcodec': 'vp8'},
    '44': {'ext': 'webm', 'width': 854, 'height': 480, 'acodec': 'vorbis', 'abr': 128, 'vcodec': 'vp8'},
    '45': {'ext': 'webm', 'width': 1280, 'height': 720, 'acodec': 'vorbis', 'abr': 192, 'vcodec': 'vp8'},
    '46': {'ext': 'webm', 'width': 1920, 'height': 1080, 'acodec': 'vorbis', 'abr': 192, 'vcodec': 'vp8'},
    '59': {'ext': 'mp4', 'width': 854, 'height': 480, 'acodec': 'aac', 'abr': 128, 'vcodec': 'h264'},
    '78': {'ext': 'mp4', 'width': 854, 'height': 480, 'acodec': 'aac', 'abr': 128, 'vcodec': 'h264'},


    # 3D videos
    '82': {'ext': 'mp4', 'height': 360, 'format_note': '3D', 'acodec': 'aac', 'abr': 128, 'vcodec': 'h264', 'preference': -20},
    '83': {'ext': 'mp4', 'height': 480, 'format_note': '3D', 'acodec': 'aac', 'abr': 128, 'vcodec': 'h264', 'preference': -20},
    '84': {'ext': 'mp4', 'height': 720, 'format_note': '3D', 'acodec': 'aac', 'abr': 192, 'vcodec': 'h264', 'preference': -20},
    '85': {'ext': 'mp4', 'height': 1080, 'format_note': '3D', 'acodec': 'aac', 'abr': 192, 'vcodec': 'h264', 'preference': -20},
    '100': {'ext': 'webm', 'height': 360, 'format_note': '3D', 'acodec': 'vorbis', 'abr': 128, 'vcodec': 'vp8', 'preference': -20},
    '101': {'ext': 'webm', 'height': 480, 'format_note': '3D', 'acodec': 'vorbis', 'abr': 192, 'vcodec': 'vp8', 'preference': -20},
    '102': {'ext': 'webm', 'height': 720, 'format_note': '3D', 'acodec': 'vorbis', 'abr': 192, 'vcodec': 'vp8', 'preference': -20},

    # Apple HTTP Live Streaming
    '91': {'ext': 'mp4', 'height': 144, 'format_note': 'HLS', 'acodec': 'aac', 'abr': 48, 'vcodec': 'h264', 'preference': -10},
    '92': {'ext': 'mp4', 'height': 240, 'format_note': 'HLS', 'acodec': 'aac', 'abr': 48, 'vcodec': 'h264', 'preference': -10},
    '93': {'ext': 'mp4', 'height': 360, 'format_note': 'HLS', 'acodec': 'aac', 'abr': 128, 'vcodec': 'h264', 'preference': -10},
    '94': {'ext': 'mp4', 'height': 480, 'format_note': 'HLS', 'acodec': 'aac', 'abr': 128, 'vcodec': 'h264', 'preference': -10},
    '95': {'ext': 'mp4', 'height': 720, 'format_note': 'HLS', 'acodec': 'aac', 'abr': 256, 'vcodec': 'h264', 'preference': -10},
    '96': {'ext': 'mp4', 'height': 1080, 'format_note': 'HLS', 'acodec': 'aac', 'abr': 256, 'vcodec': 'h264', 'preference': -10},
    '132': {'ext': 'mp4', 'height': 240, 'format_note': 'HLS', 'acodec': 'aac', 'abr': 48, 'vcodec': 'h264', 'preference': -10},
    '151': {'ext': 'mp4', 'height': 72, 'format_note': 'HLS', 'acodec': 'aac', 'abr': 24, 'vcodec': 'h264', 'preference': -10},

    # DASH mp4 video
    '133': {'ext': 'mp4', 'height': 240, 'format_note': 'DASH video', 'vcodec': 'h264'},
    '134': {'ext': 'mp4', 'height': 360, 'format_note': 'DASH video', 'vcodec': 'h264'},
    '135': {'ext': 'mp4', 'height': 480, 'format_note': 'DASH video', 'vcodec': 'h264'},
    '136': {'ext': 'mp4', 'height': 720, 'format_note': 'DASH video', 'vcodec': 'h264'},
    '137': {'ext': 'mp4', 'height': 1080, 'format_note': 'DASH video', 'vcodec': 'h264'},
    '138': {'ext': 'mp4', 'format_note': 'DASH video', 'vcodec': 'h264'},  # Height can vary (https://github.com/rg3/youtube-dl/issues/4559)
    '160': {'ext': 'mp4', 'height': 144, 'format_note': 'DASH video', 'vcodec': 'h264'},
    '212': {'ext': 'mp4', 'height': 480, 'format_note': 'DASH video', 'vcodec': 'h264'},
    '264': {'ext': 'mp4', 'height': 1440, 'format_note': 'DASH video', 'vcodec': 'h264'},
    '298': {'ext': 'mp4', 'height': 720, 'format_note': 'DASH video', 'vcodec': 'h264', 'fps': 60},
    '299': {'ext': 'mp4', 'height': 1080, 'format_note': 'DASH video', 'vcodec': 'h264', 'fps': 60},
    '266': {'ext': 'mp4', 'height': 2160, 'format_note': 'DASH video', 'vcodec': 'h264'},

    # Dash mp4 audio
    '139': {'ext': 'm4a', 'format_note': 'DASH audio', 'acodec': 'aac', 'abr': 48, 'container': 'm4a_dash'},
    '140': {'ext': 'm4a', 'format_note': 'DASH audio', 'acodec': 'aac', 'abr': 128, 'container': 'm4a_dash'},
    '141': {'ext': 'm4a', 'format_note': 'DASH audio', 'acodec': 'aac', 'abr': 256, 'container': 'm4a_dash'},
    '256': {'ext': 'm4a', 'format_note': 'DASH audio', 'acodec': 'aac', 'container': 'm4a_dash'},
    '258': {'ext': 'm4a', 'format_note': 'DASH audio', 'acodec': 'aac', 'container': 'm4a_dash'},
    '325': {'ext': 'm4a', 'format_note': 'DASH audio', 'acodec': 'dtse', 'container': 'm4a_dash'},
    '328': {'ext': 'm4a', 'format_note': 'DASH audio', 'acodec': 'ec-3', 'container': 'm4a_dash'},

    # Dash webm
    '167': {'ext': 'webm', 'height': 360, 'width': 640, 'format_note': 'DASH video', 'container': 'webm', 'vcodec': 'vp8'},
    '168': {'ext': 'webm', 'height': 480, 'width': 854, 'format_note': 'DASH video', 'container': 'webm', 'vcodec': 'vp8'},
    '169': {'ext': 'webm', 'height': 720, 'width': 1280, 'format_note': 'DASH video', 'container': 'webm', 'vcodec': 'vp8'},
    '170': {'ext': 'webm', 'height': 1080, 'width': 1920, 'format_note': 'DASH video', 'container': 'webm', 'vcodec': 'vp8'},
    '218': {'ext': 'webm', 'height': 480, 'width': 854, 'format_note': 'DASH video', 'container': 'webm', 'vcodec': 'vp8'},
    '219': {'ext': 'webm', 'height': 480, 'width': 854, 'format_note': 'DASH video', 'container': 'webm', 'vcodec': 'vp8'},
    '278': {'ext': 'webm', 'height': 144, 'format_note': 'DASH video', 'container': 'webm', 'vcodec': 'vp9'},
    '242': {'ext': 'webm', 'height': 240, 'format_note': 'DASH video', 'vcodec': 'vp9'},
    '243': {'ext': 'webm', 'height': 360, 'format_note': 'DASH video', 'vcodec': 'vp9'},
    '244': {'ext': 'webm', 'height': 480, 'format_note': 'DASH video', 'vcodec': 'vp9'},
    '245': {'ext': 'webm', 'height': 480, 'format_note': 'DASH video', 'vcodec': 'vp9'},
    '246': {'ext': 'webm', 'height': 480, 'format_note': 'DASH video', 'vcodec': 'vp9'},
    '247': {'ext': 'webm', 'height': 720, 'format_note': 'DASH video', 'vcodec': 'vp9'},
    '248': {'ext': 'webm', 'height': 1080, 'format_note': 'DASH video', 'vcodec': 'vp9'},
    '271': {'ext': 'webm', 'height': 1440, 'format_note': 'DASH video', 'vcodec': 'vp9'},
    # itag 272 videos are either 3840x2160 (e.g. RtoitU2A-3E) or 7680x4320 (sLprVF6d7Ug)
    '272': {'ext': 'webm', 'height': 2160, 'format_note': 'DASH video', 'vcodec': 'vp9'},
    '302': {'ext': 'webm', 'height': 720, 'format_note': 'DASH video', 'vcodec': 'vp9', 'fps': 60},
    '303': {'ext': 'webm', 'height': 1080, 'format_note': 'DASH video', 'vcodec': 'vp9', 'fps': 60},
    '308': {'ext': 'webm', 'height': 1440, 'format_note': 'DASH video', 'vcodec': 'vp9', 'fps': 60},
    '313': {'ext': 'webm', 'height': 2160, 'format_note': 'DASH video', 'vcodec': 'vp9'},
    '315': {'ext': 'webm', 'height': 2160, 'format_note': 'DASH video', 'vcodec': 'vp9', 'fps': 60},

    # Dash webm audio
    '171': {'ext': 'webm', 'acodec': 'vorbis', 'format_note': 'DASH audio', 'abr': 128},
    '172': {'ext': 'webm', 'acodec': 'vorbis', 'format_note': 'DASH audio', 'abr': 256},

    # Dash webm audio with opus inside
    '249': {'ext': 'webm', 'format_note': 'DASH audio', 'acodec': 'opus', 'abr': 50},
    '250': {'ext': 'webm', 'format_note': 'DASH audio', 'acodec': 'opus', 'abr': 70},
    '251': {'ext': 'webm', 'format_note': 'DASH audio', 'acodec': 'opus', 'abr': 160},

    # RTMP (unnamed)
    '_rtmp': {'protocol': 'rtmp'},
}






with open("yt_watch_template.html", "r") as file:
    yt_watch_template = Template(file.read())
    


# example:
#https://www.youtube.com/related_ajax?ctoken=CBQSJhILVGNxV29rOEF1YkXAAQDIAQDgAQGiAg0o____________AUAAGAAq0gEInJOqsOyB1tAaCNeMgaD4spLIKQioxdHSu8SF9JgBCLr27tnaioDpXwj1-L_R3s7r2wcIv8TnueeUo908CMXSganIrvHDJgiVuMirrqbgqYABCJDsu8PBzdGW8wEI_-WI2t-c-IlQCOK_m_KB_rP5wAEIl7S4serqnq5YCNSs55mMt8qLyQEImvutmp-x9LaCAQiVg96VpY_pqJMBCOPsgdTflsGRsQEI7ZfYleKIub0tCIrcsb7a_uu95gEIi9Gz6_bC76zEAQjo1c_W8JzlkhI%3D&continuation=CBQSJhILVGNxV29rOEF1YkXAAQDIAQDgAQGiAg0o____________AUAAGAAq0gEInJOqsOyB1tAaCNeMgaD4spLIKQioxdHSu8SF9JgBCLr27tnaioDpXwj1-L_R3s7r2wcIv8TnueeUo908CMXSganIrvHDJgiVuMirrqbgqYABCJDsu8PBzdGW8wEI_-WI2t-c-IlQCOK_m_KB_rP5wAEIl7S4serqnq5YCNSs55mMt8qLyQEImvutmp-x9LaCAQiVg96VpY_pqJMBCOPsgdTflsGRsQEI7ZfYleKIub0tCIrcsb7a_uu95gEIi9Gz6_bC76zEAQjo1c_W8JzlkhI%3D&itct=CCkQybcCIhMIg8PShInX2gIVgdvBCh15WA0ZKPgd
def get_bloated_more_related_videos(video_url, related_videos_token, id_token):
    related_videos_token = urllib.parse.quote(related_videos_token)
    url = "https://www.youtube.com/related_ajax?ctoken=" + related_videos_token + "&continuation=" + related_videos_token
    headers = {
        'Host': 'www.youtube.com',
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64)',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': video_url,
        'X-YouTube-Client-Name': '1',
        'X-YouTube-Client-Version': '2.20180418',
        'X-Youtube-Identity-Token': id_token,

    }
    #print(url)
    req = urllib.request.Request(url, headers=headers)
    response = urllib.request.urlopen(req, timeout = 5)
    content = response.read()
    info = json.loads(content)
    return info

def get_more_related_videos_info(video_url, related_videos_token, id_token):
    results = []
    info = get_bloated_more_related_videos(video_url, related_videos_token, id_token)
    bloated_results = info[1]['response']['continuationContents']['watchNextSecondaryResultsContinuation']['results']
    for bloated_result in bloated_results:
        bloated_result = bloated_result['compactVideoRenderer']
        results.append({
            "title": bloated_result['title']['simpleText'],
            "video_id": bloated_result['videoId'],
            "views_text": bloated_result['viewCountText']['simpleText'],
            "length_text": default_multi_get(bloated_result, 'lengthText', 'simpleText', default=''), # livestreams dont have a length
            "length_text": bloated_result['lengthText']['simpleText'],
            "uploader_name": bloated_result['longBylineText']['runs'][0]['text'],
            "uploader_url": bloated_result['longBylineText']['runs'][0]['navigationEndpoint']['commandMetadata']['webCommandMetadata']['url'],
        })
    return results

def more_related_videos_html(video_info):
    related_videos = get_related_videos(url, 1, video_info['related_videos_token'], video_info['id_token'])
            
    related_videos_html = ""
    for video in related_videos:
        related_videos_html += Template(video_related_template).substitute(
            video_title=html.escape(video["title"]),
            views=video["views_text"],
            uploader=html.escape(video["uploader_name"]),
            uploader_channel_url=video["uploader_url"],
            length=video["length_text"],
            video_url = "/youtube.com/watch?v=" + video["video_id"],
            thumbnail_url= get_thumbnail_url(video['video_id']),
        )
    return related_videos_html



def get_related_items_html(info):
    result = ""
    for item in info['related_vids']:
        if 'list' in item:  # playlist:
            result += common.small_playlist_item_html(watch_page_related_playlist_info(item))
        else:
            result += common.small_video_item_html(watch_page_related_video_info(item))
    return result

    
# json of related items retrieved directly from the watch page has different names for everything
# converts these to standard names
def watch_page_related_video_info(item):
    result = {key: item[key] for key in ('id', 'title', 'author')}
    result['duration'] = common.seconds_to_timestamp(item['length_seconds'])
    try:
        result['views'] = item['short_view_count_text']
    except KeyError:
        result['views'] = ''
    return result
    
def watch_page_related_playlist_info(item):
    return {
        'size': item['playlist_length'] if item['playlist_length'] != "0" else "50+",
        'title': item['playlist_title'],
        'id': item['list'],
        'first_video_id': item['video_id'],
    }

    
def sort_formats(info):
    info['formats'].sort(key=lambda x: default_multi_get(_formats, x['format_id'], 'height', default=0))
    for index, format in enumerate(info['formats']):
        if default_multi_get(_formats, format['format_id'], 'height', default=0) >= 360:
            break
    info['formats'] = info['formats'][index:] + info['formats'][0:index]
    info['formats'] = [format for format in info['formats'] if format['acodec'] != 'none' and format['vcodec'] != 'none']
    
def formats_html(info):
    result = ''
    for format in info['formats']:
        result += source_tag_template.substitute(
            src=format['url'],
            type='audio/' + format['ext'] if format['vcodec'] == "none" else 'video/' + format['ext'],
        )
    return result
    
def choose_format(info):
    suitable_formats = []
    with open('teste.txt', 'w', encoding='utf-8') as f:
        f.write(json.dumps(info['formats']))
    for format in info['formats']:
        if (format["ext"] in ("mp4", "webm") 
        and format["acodec"] != "none"
        and format["vcodec"] != "none"
        and format.get("height","none") in video_height_priority):
            suitable_formats.append(format)

    current_best = (suitable_formats[0],video_height_priority.index(suitable_formats[0]["height"]))
    for format in suitable_formats:
        video_priority_index = video_height_priority.index(format["height"])
        if video_priority_index < current_best[1]:
            current_best = (format, video_priority_index)
    return current_best[0]

subtitles_tag_template = Template('''
<track label="$label" src="$src" kind="subtitles" srclang="$srclang" $default>''')
def subtitles_html(info):
    result = ''
    default_found = False
    for language, formats in info['subtitles'].items():
        for format in formats:
            if format['ext'] == 'vtt':
                if language == settings.subtitles_language:
                    default_found = True
                result += subtitles_tag_template.substitute(
                    src = html.escape('/' + format['url']),
                    label = html.escape(language),
                    srclang = html.escape(language),
                    default = 'default' if language == settings.subtitles_language and settings.subtitles_mode > 0 else '',
                )
                break
    try:
        formats = info['automatic_captions'][settings.subtitles_language]
    except KeyError:
        pass
    else:
        for format in formats:
            if format['ext'] == 'vtt':
                result += subtitles_tag_template.substitute(
                    src = html.escape('/' + format['url']),
                    label = settings.subtitles_language + ' - Automatic',
                    srclang = settings.subtitles_language,
                    default = 'default' if settings.subtitles_mode == 2 and not default_found else '',
                )
    return result


more_comments_template = Template('''<a class="page-button more-comments" href="$url">More comments</a>''')
source_tag_template = Template('''
<source src="$src" type="$type">''')

def get_watch_page(query_string):
        id = urllib.parse.parse_qs(query_string)['v'][0]
        tasks = (
            gevent.spawn(comments.video_comments, id ), 
            gevent.spawn(YoutubeDL(params={'youtube_include_dash_manifest':False}).extract_info, "https://www.youtube.com/watch?v=" + id, download=False)
        )
        gevent.joinall(tasks)
        comments_info, info = tasks[0].value, tasks[1].value
        comments_html, ctoken = comments_info

        if ctoken == '':
            more_comments_button = ''
        else:
            more_comments_button = more_comments_template.substitute(url = URL_ORIGIN + '/comments?ctoken=' + ctoken)
        #comments_html = comments.comments_html(video_id(url))
        #info = YoutubeDL().extract_info(url, download=False)
        
        #chosen_format = choose_format(info)
        sort_formats(info)
        
        video_info = {
            "duration": common.seconds_to_timestamp(info["duration"]),
            "id":       info['id'],
            "title":    info['title'],
            "author":   info['uploader'],
        }

        upload_year = info["upload_date"][0:4]
        upload_month = info["upload_date"][4:6]
        upload_day = info["upload_date"][6:8]
        upload_date = upload_month + "/" + upload_day + "/" + upload_year
        
        if settings.enable_related_videos:
            related_videos_html = get_related_items_html(info)
        else:
            related_videos_html = ''
        
        page = yt_watch_template.substitute(
            video_title             = html.escape(info["title"]),
            page_title              = html.escape(info["title"]),
            header                  = common.get_header(),
            uploader                = html.escape(info["uploader"]),
            uploader_channel_url    = '/' + info["uploader_url"],
            upload_date             = upload_date,
            views           = (lambda x: '{:,}'.format(x) if x is not None else "")(info.get("view_count", None)),
            likes           = (lambda x: '{:,}'.format(x) if x is not None else "")(info.get("like_count", None)),
            dislikes        = (lambda x: '{:,}'.format(x) if x is not None else "")(info.get("dislike_count", None)),
            video_info              = html.escape(json.dumps(video_info)),
            description             = html.escape(info["description"]),
            video_sources           = formats_html(info) + subtitles_html(info),
            related                 = related_videos_html,
            comments                = comments_html,
            more_comments_button    = more_comments_button,
        )
        return page