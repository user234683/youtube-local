from youtube import yt_app
from youtube import util, comments, local_playlist, yt_data_extract
import settings

from flask import request
import flask

import json
import html
import gevent
import os
import math
import traceback
import re
import urllib

try:
    with open(os.path.join(settings.data_dir, 'decrypt_function_cache.json'), 'r') as f:
        decrypt_cache = json.loads(f.read())['decrypt_cache']
except FileNotFoundError:
    decrypt_cache = {}


def get_video_sources(info):
    video_sources = []
    if not settings.theater_mode:
        max_resolution = 360
    else:
        max_resolution = settings.default_resolution
    for format in info['formats']:
        if not all(format[attr] for attr in ('height', 'width', 'ext', 'url')):
            continue
        if format['acodec'] and format['vcodec'] and format['height'] <= max_resolution:
            video_sources.append({
                'src': format['url'],
                'type': 'video/' + format['ext'],
                'height': format['height'],
                'width': format['width'],
            })

    #### order the videos sources so the preferred resolution is first ###

    video_sources.sort(key=lambda source: source['height'], reverse=True)

    return video_sources

def get_subtitle_sources(info):
    sources = []
    default_found = False
    default = None
    for language, formats in info['subtitles'].items():
        for format in formats:
            if format['ext'] == 'vtt':
                source = {
                    'url': '/' + format['url'],
                    'label': language,
                    'srclang': language,

                    # set as on by default if this is the preferred language and a default-on subtitles mode is in settings
                    'on': language == settings.subtitles_language and settings.subtitles_mode > 0,
                }

                if language == settings.subtitles_language:
                    default_found = True
                    default = source
                else:
                    sources.append(source)
                break

    # Put it at the end to avoid browser bug when there are too many languages
    # (in firefox, it is impossible to select a language near the top of the list because it is cut off)
    if default_found:
        sources.append(default)

    try:
        formats = info['automatic_captions'][settings.subtitles_language]
    except KeyError:
        pass
    else:
        for format in formats:
            if format['ext'] == 'vtt':
                sources.append({
                    'url': '/' + format['url'],
                    'label': settings.subtitles_language + ' - Automatic',
                    'srclang': settings.subtitles_language,

                    # set as on by default if this is the preferred language and a default-on subtitles mode is in settings
                    'on': settings.subtitles_mode == 2 and not default_found,

                })

    return sources


def get_ordered_music_list_attributes(music_list):
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

    return ordered_attributes

def save_decrypt_cache():
    try:
        f = open(os.path.join(settings.data_dir, 'decrypt_function_cache.json'), 'w')
    except FileNotFoundError:
        os.makedirs(settings.data_dir)
        f = open(os.path.join(settings.data_dir, 'decrypt_function_cache.json'), 'w')

    f.write(json.dumps({'version': 1, 'decrypt_cache':decrypt_cache}, indent=4, sort_keys=True))
    f.close()

# adapted from youtube-dl and invidious:
# https://github.com/omarroth/invidious/blob/master/src/invidious/helpers/signatures.cr
decrypt_function_re = re.compile(r'function\(a\)\{(a=a\.split\(""\)[^\}]+)\}')
op_with_arg_re = re.compile(r'[^\.]+\.([^\(]+)\(a,(\d+)\)')
def decrypt_signatures(info):
    '''return error string, or False if no errors'''
    if ('formats' not in info) or (not info['formats']) or (not info['formats'][0]['s']):
        return False    # No decryption needed
    if not info['base_js']:
        return 'Failed to find base.js'
    player_name = yt_data_extract.default_get(info['base_js'].split('/'), -2)
    if not player_name:
        return 'Could not find player name'

    if player_name in decrypt_cache:
        print('Using cached decryption function for: ' + player_name)
        decryption_function = decrypt_cache[player_name]
    else:
        base_js = util.fetch_url(info['base_js'], debug_name='base.js', report_text='Fetched player ' + player_name)
        base_js = base_js.decode('utf-8')

        decrypt_function_match = decrypt_function_re.search(base_js)
        if decrypt_function_match is None:
            return 'Could not find decryption function in base.js'

        function_body = decrypt_function_match.group(1).split(';')[1:-1]
        if not function_body:
            return 'Empty decryption function body'

        var_name = yt_data_extract.default_get(function_body[0].split('.'), 0)
        if var_name is None:
            return 'Could not find var_name'

        var_body_match = re.search(r'var ' + re.escape(var_name) + r'=\{(.*?)\};', base_js, flags=re.DOTALL)
        if var_body_match is None:
            return 'Could not find var_body'

        operations = var_body_match.group(1).replace('\n', '').split('},')
        if not operations:
            return 'Did not find any definitions in var_body'
        operations[-1] = operations[-1][:-1]    # remove the trailing '}' since we split by '},' on the others
        operation_definitions = {}
        for op in operations:
            colon_index = op.find(':')
            opening_brace_index = op.find('{')

            if colon_index == -1 or opening_brace_index == -1:
                return 'Could not parse operation'
            op_name = op[:colon_index]
            op_body = op[opening_brace_index+1:]
            if op_body == 'a.reverse()':
                operation_definitions[op_name] = 0
            elif op_body == 'a.splice(0,b)':
                operation_definitions[op_name] = 1
            elif op_body.startswith('var c=a[0]'):
                operation_definitions[op_name] = 2
            else:
                return 'Unknown op_body: ' + op_body

        decryption_function = []
        for op_with_arg in function_body:
            match = op_with_arg_re.fullmatch(op_with_arg)
            if match is None:
                return 'Could not parse operation with arg'
            op_name = match.group(1)
            if op_name not in operation_definitions:
                return 'Unknown op_name: ' + op_name
            op_argument = match.group(2)
            decryption_function.append([operation_definitions[op_name], int(op_argument)])

        decrypt_cache[player_name] = decryption_function
        save_decrypt_cache()

    for format in info['formats']:
        if not format['s'] or not format['sp'] or not format['url']:
            print('Warning: s, sp, or url not in format')
            continue

        a = list(format['s'])
        for op, argument in decryption_function:
            if op == 0:
                a.reverse()
            elif op == 1:
                a = a[argument:]
            else:
                operation_2(a, argument)

        signature = ''.join(a)
        format['url'] += '&' + format['sp'] + '=' + signature
    return False

def operation_2(a, b):
    c = a[0]
    a[0] = a[b % len(a)]
    a[b % len(a)] = c

headers = (
    ('Accept', '*/*'),
    ('Accept-Language', 'en-US,en;q=0.5'),
    ('X-YouTube-Client-Name', '2'),
    ('X-YouTube-Client-Version', '2.20180830'),
) + util.mobile_ua

def extract_info(video_id):
    polymer_json = util.fetch_url('https://m.youtube.com/watch?v=' + video_id + '&pbj=1', headers=headers, debug_name='watch')
    try:
        polymer_json = json.loads(polymer_json)
    except json.decoder.JSONDecodeError:
        traceback.print_exc()
        return {'error': 'Failed to parse json response'}
    info = yt_data_extract.extract_watch_info(polymer_json)
    error = decrypt_signatures(info)
    if error:
        print('Error decrypting url signatures: ' + error)
        info['playability_error'] = error
    return info

def video_quality_string(format):
    if format['vcodec']:
        result =str(format['width'] or '?') + 'x' + str(format['height'] or '?')
        if format['fps']:
            result += ' ' + str(format['fps']) + 'fps'
        return result
    elif format['acodec']:
        return 'audio only'

    return '?'

def audio_quality_string(format):
    if format['acodec']:
        result = str(format['audio_bitrate'] or '?') + 'k'
        if format['audio_sample_rate']:
            result += ' ' + str(format['audio_sample_rate']) + ' Hz'
        return result
    elif format['vcodec']:
        return 'video only'

    return '?'

# from https://github.com/ytdl-org/youtube-dl/blob/master/youtube_dl/utils.py
def format_bytes(bytes):
    if bytes is None:
        return 'N/A'
    if type(bytes) is str:
        bytes = float(bytes)
    if bytes == 0.0:
        exponent = 0
    else:
        exponent = int(math.log(bytes, 1024.0))
    suffix = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB'][exponent]
    converted = float(bytes) / float(1024 ** exponent)
    return '%.2f%s' % (converted, suffix)


@yt_app.route('/watch')
def get_watch_page():
    video_id = request.args['v']
    if len(video_id) < 11:
        flask.abort(404)
        flask.abort(flask.Response('Incomplete video id (too short): ' + video_id))

    lc = request.args.get('lc', '')
    tasks = (
        gevent.spawn(comments.video_comments, video_id, int(settings.default_comment_sorting), lc=lc ),
        gevent.spawn(extract_info, video_id)
    )
    gevent.joinall(tasks)
    comments_info, info = tasks[0].value, tasks[1].value

    if info['error']:
        return flask.render_template('error.html', error_message = info['error'])

    video_info = {
        "duration": util.seconds_to_timestamp(info["duration"] or 0),
        "id":       info['id'],
        "title":    info['title'],
        "author":   info['author'],
    }

    for item in info['related_videos']:
        yt_data_extract.prefix_urls(item)
        yt_data_extract.add_extra_html_info(item)

    if settings.gather_googlevideo_domains:
        with open(os.path.join(settings.data_dir, 'googlevideo-domains.txt'), 'a+', encoding='utf-8') as f:
            url = info['formats'][0]['url']
            subdomain = url[0:url.find(".googlevideo.com")]
            f.write(subdomain + "\n")


    download_formats = []

    for format in info['formats']:
        if format['acodec'] and format['vcodec']:
            codecs_string = format['acodec'] + ', ' + format['vcodec']
        else:
            codecs_string = format['acodec'] or format['vcodec'] or '?'
        download_formats.append({
            'url': format['url'],
            'ext': format['ext'] or '?',
            'audio_quality': audio_quality_string(format),
            'video_quality': video_quality_string(format),
            'file_size': format_bytes(format['file_size']),
            'codecs': codecs_string,
        })

    video_sources = get_video_sources(info)
    video_height = yt_data_extract.default_multi_get(video_sources, 0, 'height', default=360)
    video_width = yt_data_extract.default_multi_get(video_sources, 0, 'width', default=640)
    # 1 second per pixel, or the actual video width
    theater_video_target_width = max(640, info['duration'] or 0, video_width)

    return flask.render_template('watch.html',
        header_playlist_names   = local_playlist.get_playlist_names(),
        uploader_channel_url    = ('/' + info['author_url']) if info['author_url'] else '',
        upload_date             = info['published_date'],
        views           = (lambda x: '{:,}'.format(x) if x is not None else "")(info.get("view_count", None)),
        likes           = (lambda x: '{:,}'.format(x) if x is not None else "")(info.get("like_count", None)),
        dislikes        = (lambda x: '{:,}'.format(x) if x is not None else "")(info.get("dislike_count", None)),
        download_formats        = download_formats,
        video_info              = json.dumps(video_info),
        video_sources           = video_sources,
        subtitle_sources        = get_subtitle_sources(info),
        related                 = info['related_videos'],
        music_list              = info['music_list'],
        music_attributes        = get_ordered_music_list_attributes(info['music_list']),
        comments_info           = comments_info,

        theater_mode            = settings.theater_mode,
        related_videos_mode     = settings.related_videos_mode,
        comments_mode           = settings.comments_mode,

        video_height            = video_height,
        theater_video_target_width = theater_video_target_width,

        title       = info['title'],
        uploader    = info['author'],
        description = info['description'],
        unlisted    = info['unlisted'],
        playability_error = info['playability_error'],
    )


@yt_app.route('/api/<path:dummy>')
def get_captions(dummy):
    result = util.fetch_url('https://www.youtube.com' + request.full_path)
    result = result.replace(b"align:start position:0%", b"")
    return result




