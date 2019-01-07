from youtube_dl.YoutubeDL import YoutubeDL
from youtube_dl.extractor.youtube import YoutubeError
import json
import urllib
from string import Template
import html
import youtube.common as common
from youtube.common import default_multi_get, get_thumbnail_url, video_id, URL_ORIGIN
import youtube.comments as comments
import gevent
import settings
import os

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
    sorted_formats = info['formats'].copy()
    sorted_formats.sort(key=lambda x: default_multi_get(_formats, x['format_id'], 'height', default=0))
    for index, format in enumerate(sorted_formats):
        if default_multi_get(_formats, format['format_id'], 'height', default=0) >= 360:
            break
    sorted_formats = sorted_formats[index:] + sorted_formats[0:index]
    sorted_formats = [format for format in info['formats'] if format['acodec'] != 'none' and format['vcodec'] != 'none']
    return sorted_formats

source_tag_template = Template('''
<source src="$src" type="$type">''')
def formats_html(formats):
    result = ''
    for format in formats:
        result += source_tag_template.substitute(
            src=format['url'],
            type='audio/' + format['ext'] if format['vcodec'] == "none" else 'video/' + format['ext'],
        )
    return result


subtitles_tag_template = Template('''
<track label="$label" src="$src" kind="subtitles" srclang="$srclang" $default>''')
def subtitles_html(info):
    result = ''
    default_found = False
    default = ''
    for language, formats in info['subtitles'].items():
        for format in formats:
            if format['ext'] == 'vtt':
                append = subtitles_tag_template.substitute(
                    src = html.escape('/' + format['url']),
                    label = html.escape(language),
                    srclang = html.escape(language),
                    default = 'default' if language == settings.subtitles_language and settings.subtitles_mode > 0 else '',
                )
                if language == settings.subtitles_language:
                    default_found = True
                    default = append
                else:
                    result += append
                break
    result += default
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

download_link_template = Template('''
<a href="$url"> <span>$ext</span> <span>$resolution</span> <span>$note</span></a>''')

def extract_info(downloader, *args, **kwargs):
    try:
        return downloader.extract_info(*args, **kwargs)
    except YoutubeError as e:
        return str(e)

music_list_table_row = Template('''<tr>
    <td>$attribute</td>
    <td>$value</td>
''')
def get_watch_page(env, start_response):
        video_id = env['parameters']['v'][0]
        if len(video_id) < 11:
            start_response('404 Not Found', [('Content-type', 'text/plain'),])
            return b'Incomplete video id (too short): ' + video_id.encode('ascii')

        start_response('200 OK', [('Content-type','text/html'),])

        lc = common.default_multi_get(env['parameters'], 'lc', 0, default='')
        if settings.route_tor:
            proxy = 'socks5://127.0.0.1:9150/'
        else:
            proxy = ''
        downloader = YoutubeDL(params={'youtube_include_dash_manifest':False, 'proxy':proxy})
        tasks = (
            gevent.spawn(comments.video_comments, video_id, int(settings.default_comment_sorting), lc=lc ),
            gevent.spawn(extract_info, downloader, "https://www.youtube.com/watch?v=" + video_id, download=False)
        )
        gevent.joinall(tasks)
        comments_html, info = tasks[0].value, tasks[1].value


        #comments_html = comments.comments_html(video_id(url))
        #info = YoutubeDL().extract_info(url, download=False)
        
        #chosen_format = choose_format(info)

        if isinstance(info, str): # youtube error
            return common.yt_basic_template.substitute(
                page_title = "Error",
                style = "",
                header = common.get_header(),
                page = html.escape(info),
            ).encode('utf-8')
            
        sorted_formats = sort_formats(info)
        
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

        music_list = info['music_list']
        if len(music_list) == 0:
            music_list_html = ''
        else:
            # get the set of attributes which are used by atleast 1 track
            # so there isn't an empty, extraneous album column which no tracks use, for example
            used_attributes = set()
            for track in music_list:
                used_attributes = used_attributes | track.keys()

            # now put them in the right order
            ordered_attributes = []
            for attribute in ('Artist', 'Title', 'Album'):
                if attribute.lower() in used_attributes:
                    ordered_attributes.append(attribute)

            music_list_html = '''<hr>
<table>
    <caption>Music</caption>
    <tr>
'''
            # table headings
            for attribute in ordered_attributes:
                music_list_html += "<th>" + attribute + "</th>\n"
            music_list_html += '''</tr>\n'''

            for track in music_list:
                music_list_html += '''<tr>\n'''
                for attribute in ordered_attributes:
                    try:
                        value = track[attribute.lower()]
                    except KeyError:
                        music_list_html += '''<td></td>'''
                    else:
                        music_list_html += '''<td>''' + html.escape(value) + '''</td>'''
                music_list_html += '''</tr>\n'''
            music_list_html += '''</table>\n'''
        if settings.gather_googlevideo_domains:
            with open(os.path.join(settings.data_dir, 'googlevideo-domains.txt'), 'a+', encoding='utf-8') as f:
                url = info['formats'][0]['url']
                subdomain = url[0:url.find(".googlevideo.com")]
                f.write(subdomain + "\n")

        download_options = ''
        for format in info['formats']:
            download_options += download_link_template.substitute(
                url        = html.escape(format['url']),
                ext         = html.escape(format['ext']),
                resolution  = html.escape(downloader.format_resolution(format)),
                note        = html.escape(downloader._format_note(format)),
            )


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
            download_options        = download_options,
            video_info              = html.escape(json.dumps(video_info)),
            description             = html.escape(info["description"]),
            video_sources           = formats_html(sorted_formats) + subtitles_html(info),
            related                 = related_videos_html,

            comments                = comments_html,

            music_list              = music_list_html,
            is_unlisted             = '<span class="is-unlisted">Unlisted</span>' if info['unlisted'] else '',
        )
        return page.encode('utf-8')
