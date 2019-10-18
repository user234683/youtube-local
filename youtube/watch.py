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




def get_video_sources(info):
    video_sources = []
    if not settings.theater_mode:
        max_resolution = 360
    else:
        max_resolution = settings.default_resolution
    for format in info['formats']:
        if not all(attr in format for attr in ('height', 'width', 'ext', 'url')):
            continue
        if 'acodec' in format and 'vcodec' in format and format['height'] <= max_resolution:
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
    return yt_data_extract.extract_watch_info(polymer_json)

def video_quality_string(format):
    if 'vcodec' in format:
        result =str(format.get('width', '?')) + 'x' + str(format.get('height', '?'))
        if 'fps' in format:
            result += ' ' + format['fps'] + 'fps'
        return result
    elif 'acodec' in format:
        return 'audio only'

    return '?'

def audio_quality_string(format):
    if 'acodec' in format:
        result = str(format.get('abr', '?')) + 'k'
        if 'audio_sample_rate' in format:
            result += ' ' + str(format['audio_sample_rate']) + ' Hz'
        return result
    elif 'vcodec' in format:
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
        if 'acodec' in format and 'vcodec' in format:
            codecs_string = format['acodec'] + ', ' + format['vcodec']
        else:
            codecs_string = format.get('acodec') or format.get('vcodec') or '?'
        download_formats.append({
            'url': format['url'],
            'ext': format.get('ext', '?'),
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
    )


@yt_app.route('/api/<path:dummy>')
def get_captions(dummy):
    result = util.fetch_url('https://www.youtube.com' + request.full_path)
    result = result.replace(b"align:start position:0%", b"")
    return result




