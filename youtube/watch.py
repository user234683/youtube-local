from youtube import yt_app
from youtube import util, comments, local_playlist, yt_data_extract
import settings

from flask import request
import flask

from youtube_dl.YoutubeDL import YoutubeDL
from youtube_dl.extractor.youtube import YoutubeError
import json
import html
import gevent
import os


def get_related_items(info):
    results = []
    for item in info['related_vids']:
        if 'list' in item:  # playlist:
            result = watch_page_related_playlist_info(item)
        else:
            result = watch_page_related_video_info(item)
        yt_data_extract.prefix_urls(result)
        yt_data_extract.add_extra_html_info(result)
        results.append(result)
    return results

    
# json of related items retrieved directly from the watch page has different names for everything
# converts these to standard names
def watch_page_related_video_info(item):
    result = {key: item[key] for key in ('id', 'title', 'author')}
    result['duration'] = util.seconds_to_timestamp(item['length_seconds'])
    try:
        result['views'] = item['short_view_count_text']
    except KeyError:
        result['views'] = ''
    result['thumbnail'] = util.get_thumbnail_url(item['id'])
    result['type'] = 'video'
    return result
    
def watch_page_related_playlist_info(item):
    return {
        'size': item['playlist_length'] if item['playlist_length'] != "0" else "50+",
        'title': item['playlist_title'],
        'id': item['list'],
        'first_video_id': item['video_id'],
        'thumbnail': util.get_thumbnail_url(item['video_id']),
        'type': 'playlist',
    }

def get_video_sources(info):
    video_sources = []
    if not settings.theater_mode:
        max_resolution = 360
    else:
        max_resolution = settings.default_resolution

    for format in info['formats']:
        if format['acodec'] != 'none' and format['vcodec'] != 'none' and format['height'] <= max_resolution:
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


def extract_info(downloader, *args, **kwargs):
    try:
        return downloader.extract_info(*args, **kwargs)
    except YoutubeError as e:
        return str(e)




@yt_app.route('/watch')
def get_watch_page():
    video_id = request.args['v']
    if len(video_id) < 11:
        flask.abort(404)
        flask.abort(flask.Response('Incomplete video id (too short): ' + video_id))

    lc = request.args.get('lc', '')
    if settings.route_tor:
        proxy = 'socks5://127.0.0.1:9150/'
    else:
        proxy = ''
    yt_dl_downloader = YoutubeDL(params={'youtube_include_dash_manifest':False, 'proxy':proxy})
    tasks = (
        gevent.spawn(comments.video_comments, video_id, int(settings.default_comment_sorting), lc=lc ),
        gevent.spawn(extract_info, yt_dl_downloader, "https://www.youtube.com/watch?v=" + video_id, download=False)
    )
    gevent.joinall(tasks)
    comments_info, info = tasks[0].value, tasks[1].value

    if isinstance(info, str): # youtube error
        return flask.render_template('error.html', error_message = info)

    video_info = {
        "duration": util.seconds_to_timestamp(info["duration"]),
        "id":       info['id'],
        "title":    info['title'],
        "author":   info['uploader'],
    }

    upload_year = info["upload_date"][0:4]
    upload_month = info["upload_date"][4:6]
    upload_day = info["upload_date"][6:8]
    upload_date = upload_month + "/" + upload_day + "/" + upload_year
    
    if settings.related_videos_mode:
        related_videos = get_related_items(info)
    else:
        related_videos = []


    if settings.gather_googlevideo_domains:
        with open(os.path.join(settings.data_dir, 'googlevideo-domains.txt'), 'a+', encoding='utf-8') as f:
            url = info['formats'][0]['url']
            subdomain = url[0:url.find(".googlevideo.com")]
            f.write(subdomain + "\n")


    download_formats = []

    for format in info['formats']:
        download_formats.append({
            'url': format['url'],
            'ext': format['ext'],
            'resolution': yt_dl_downloader.format_resolution(format),
            'note': yt_dl_downloader._format_note(format),
        })

    video_sources = get_video_sources(info)
    video_height = video_sources[0]['height']

    # 1 second per pixel, or the actual video width
    theater_video_target_width = max(640, info['duration'], video_sources[0]['width'])

    return flask.render_template('watch.html',
        header_playlist_names   = local_playlist.get_playlist_names(),
        uploader_channel_url    = '/' + info['uploader_url'],
        upload_date             = upload_date,
        views           = (lambda x: '{:,}'.format(x) if x is not None else "")(info.get("view_count", None)),
        likes           = (lambda x: '{:,}'.format(x) if x is not None else "")(info.get("like_count", None)),
        dislikes        = (lambda x: '{:,}'.format(x) if x is not None else "")(info.get("dislike_count", None)),
        download_formats        = download_formats,
        video_info              = json.dumps(video_info),
        video_sources           = video_sources,
        subtitle_sources        = get_subtitle_sources(info),
        related                 = related_videos,
        music_list              = info['music_list'],
        music_attributes        = get_ordered_music_list_attributes(info['music_list']),
        comments_info           = comments_info,

        theater_mode            = settings.theater_mode,
        related_videos_mode     = settings.related_videos_mode,
        comments_mode           = settings.comments_mode,

        video_height            = video_height,
        theater_video_target_width = theater_video_target_width,

        title       = info['title'],
        uploader    = info['uploader'],
        description = info['description'],
        unlisted    = info['unlisted'],
    )


@yt_app.route('/api/<path:dummy>')
def get_captions(dummy):
    result = util.fetch_url('https://www.youtube.com' + request.full_path)
    result = result.replace(b"align:start position:0%", b"")
    return result




