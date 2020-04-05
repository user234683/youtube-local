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
import urllib
import re
import urllib3.exceptions

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

def make_caption_src(info, lang, auto=False, trans_lang=None):
    label = lang
    if auto:
        label += ' (Automatic)'
    if trans_lang:
        label += ' -> ' + trans_lang
    return {
        'url': '/' + yt_data_extract.get_caption_url(info, lang, 'vtt', auto, trans_lang),
        'label': label,
        'srclang': trans_lang[0:2] if trans_lang else lang[0:2],
        'on': False,
    }

def lang_in(lang, sequence):
    '''Tests if the language is in sequence, with e.g. en and en-US considered the same'''
    if lang is None:
        return False
    lang = lang[0:2]
    return lang in (l[0:2] for l in sequence)

def lang_eq(lang1, lang2):
    '''Tests if two iso 639-1 codes are equal, with en and en-US considered the same.
       Just because the codes are equal does not mean the dialects are mutually intelligible, but this will have to do for now without a complex language model'''
    if lang1 is None or lang2 is None:
        return False
    return lang1[0:2] == lang2[0:2]

def equiv_lang_in(lang, sequence):
    '''Extracts a language in sequence which is equivalent to lang.
    e.g. if lang is en, extracts en-GB from sequence.
    Necessary because if only a specific variant like en-GB is available, can't ask Youtube for simply en. Need to get the available variant.'''
    lang = lang[0:2]
    for l in sequence:
        if l[0:2] == lang:
            return l
    return None

def get_subtitle_sources(info):
    '''Returns these sources, ordered from least to most intelligible:
    native_video_lang (Automatic)
    foreign_langs (Manual)
    native_video_lang (Automatic) -> pref_lang
    foreign_langs (Manual) -> pref_lang
    native_video_lang (Manual) -> pref_lang
    pref_lang (Automatic)
    pref_lang (Manual)'''
    sources = []
    pref_lang = settings.subtitles_language
    native_video_lang = None
    if info['automatic_caption_languages']:
        native_video_lang = info['automatic_caption_languages'][0]

    highest_fidelity_is_manual = False

    # Sources are added in very specific order outlined above
    # More intelligible sources are put further down to avoid browser bug when there are too many languages
    # (in firefox, it is impossible to select a language near the top of the list because it is cut off)

    # native_video_lang (Automatic)
    if native_video_lang and not lang_eq(native_video_lang, pref_lang):
        sources.append(make_caption_src(info, native_video_lang, auto=True))

    # foreign_langs (Manual)
    for lang in info['manual_caption_languages']:
        if not lang_eq(lang, pref_lang):
            sources.append(make_caption_src(info, lang))

    if (lang_in(pref_lang, info['translation_languages'])
            and not lang_in(pref_lang, info['automatic_caption_languages'])
            and not lang_in(pref_lang, info['manual_caption_languages'])):
        # native_video_lang (Automatic) -> pref_lang
        if native_video_lang and not lang_eq(pref_lang, native_video_lang):
            sources.append(make_caption_src(info, native_video_lang, auto=True, trans_lang=pref_lang))

        # foreign_langs (Manual) -> pref_lang
        for lang in info['manual_caption_languages']:
            if not lang_eq(lang, native_video_lang) and not lang_eq(lang, pref_lang):
                sources.append(make_caption_src(info, lang, trans_lang=pref_lang))

        # native_video_lang (Manual) -> pref_lang
        if lang_in(native_video_lang, info['manual_caption_languages']):
            sources.append(make_caption_src(info, native_video_lang, trans_lang=pref_lang))

    # pref_lang (Automatic)
    if lang_in(pref_lang, info['automatic_caption_languages']):
        sources.append(make_caption_src(info, equiv_lang_in(pref_lang, info['automatic_caption_languages']), auto=True))

    # pref_lang (Manual)
    if lang_in(pref_lang, info['manual_caption_languages']):
        sources.append(make_caption_src(info, equiv_lang_in(pref_lang, info['manual_caption_languages'])))
        highest_fidelity_is_manual = True

    if sources and sources[-1]['srclang'] == pref_lang:
        # set as on by default since it's manual a default-on subtitles mode is in settings
        if highest_fidelity_is_manual and settings.subtitles_mode > 0:
            sources[-1]['on'] = True
        # set as on by default since settings indicate to set it as such even if it's not manual
        elif settings.subtitles_mode == 2:
            sources[-1]['on'] = True

    if len(sources) == 0:
        assert len(info['automatic_caption_languages']) == 0 and len(info['manual_caption_languages']) == 0

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

def decrypt_signatures(info):
    '''return error string, or False if no errors'''
    if not yt_data_extract.requires_decryption(info):
        return False
    if not info['player_name']:
        return 'Could not find player name'
    if not info['base_js']:
        return 'Failed to find base.js'

    player_name = info['player_name']
    if player_name in decrypt_cache:
        print('Using cached decryption function for: ' + player_name)
        info['decryption_function'] = decrypt_cache[player_name]
    else:
        base_js = util.fetch_url(info['base_js'], debug_name='base.js', report_text='Fetched player ' + player_name)
        base_js = base_js.decode('utf-8')
        err = yt_data_extract.extract_decryption_function(info, base_js)
        if err:
            return err
        decrypt_cache[player_name] = info['decryption_function']
        save_decrypt_cache()
    err = yt_data_extract.decrypt_signatures(info)
    return err

headers = (
    ('Accept', '*/*'),
    ('Accept-Language', 'en-US,en;q=0.5'),
    ('X-YouTube-Client-Name', '2'),
    ('X-YouTube-Client-Version', '2.20180830'),
) + util.mobile_ua

def extract_info(video_id, playlist_id=None, index=None):
    # bpctr=9999999999 will bypass are-you-sure dialogs for controversial
    # videos
    url = 'https://m.youtube.com/watch?v=' + video_id + '&pbj=1&bpctr=9999999999'
    if playlist_id:
        url += '&list=' + playlist_id
    if index:
        url += '&index=' + index
    polymer_json = util.fetch_url(url, headers=headers, debug_name='watch')
    polymer_json = polymer_json.decode('utf-8')
    # TODO: Decide whether this should be done in yt_data_extract.extract_watch_info
    try:
        polymer_json = json.loads(polymer_json)
    except json.decoder.JSONDecodeError:
        traceback.print_exc()
        return {'error': 'Failed to parse json response'}
    info = yt_data_extract.extract_watch_info(polymer_json)

    # age restriction bypass
    if info['age_restricted']:
        print('Fetching age restriction bypass page')
        data = {
            'video_id': video_id,
            'eurl': 'https://youtube.googleapis.com/v/' + video_id,
        }
        url = 'https://www.youtube.com/get_video_info?' + urllib.parse.urlencode(data)
        video_info_page = util.fetch_url(url, debug_name='get_video_info', report_text='Fetched age restriction bypass page').decode('utf-8')
        yt_data_extract.update_with_age_restricted_info(info, video_info_page)

    # signature decryption
    decryption_error = decrypt_signatures(info)
    if decryption_error:
        decryption_error = 'Error decrypting url signatures: ' + decryption_error
        info['playability_error'] = decryption_error

    # check for 403
    info['invidious_used'] = False
    if settings.route_tor and info['formats'] and info['formats'][0]['url']:
        try:
            response = util.head(info['formats'][0]['url'],
                report_text='Checked for URL access')
        except urllib3.exceptions.HTTPError:
            print('Error while checking for URL access:\n')
            traceback.print_exc()
            return info

        if response.status == 403:
            print(('Access denied (403) for video urls.'
                ' Retrieving urls from Invidious...'))
            info['invidious_used'] = True
            try:
                video_info = util.fetch_url(
                    'https://invidio.us/api/v1/videos/'
                    + video_id
                    + '?fields=adaptiveFormats,formatStreams',
                    report_text='Retrieved urls from Invidious',
                    debug_name='invidious_urls')
            except (urllib3.exceptions.HTTPError) as e:
                traceback.print_exc()
                playability_error = ('Access denied (403) for video urls.'
                        + ' Failed to use Invidious to get the urls: '
                        + str(e))
                if info['playability_error']:
                    info['playability_error'] += '\n' + playability_error
                else:
                    info['playability_error'] = playability_error
                
                return info

            video_info = json.loads(video_info.decode('utf-8'))
            # collect invidious urls for each itag
            itag_to_url = {}
            for invidious_fmt in (video_info['adaptiveFormats']
                        + video_info['formatStreams']):
                itag_to_url[invidious_fmt['itag']] = invidious_fmt['url']

            # replace urls with urls from invidious
            for fmt in info['formats']:
                itag = str(fmt['itag'])
                if itag not in itag_to_url:
                    print(('Warning: itag '
                        + itag + ' not found in invidious urls'))
                    continue
                fmt['url'] = itag_to_url[itag]
        elif 300 <= response.status < 400:
            print('Error: exceeded max redirects while checking video URL')
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
@yt_app.route('/embed')
@yt_app.route('/embed/<video_id>')
def get_watch_page(video_id=None):
    video_id = request.args.get('v') or video_id
    if not video_id:
        return flask.render_template('error.html', error_message='Missing video id'), 404
    if len(video_id) < 11:
        return flask.render_template('error.html', error_message='Incomplete video id (too short): ' + video_id), 404

    lc = request.args.get('lc', '')
    playlist_id = request.args.get('list')
    index = request.args.get('index')
    tasks = (
        gevent.spawn(comments.video_comments, video_id, int(settings.default_comment_sorting), lc=lc ),
        gevent.spawn(extract_info, video_id, playlist_id=playlist_id,
            index=index)
    )
    gevent.joinall(tasks)
    util.check_gevent_exceptions(tasks[1])
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
        util.prefix_urls(item)
        util.add_extra_html_info(item)

    if info['playlist']:
        playlist_id = info['playlist']['id']
        for item in info['playlist']['items']:
            util.prefix_urls(item)
            util.add_extra_html_info(item)
            if playlist_id:
                item['url'] += '&list=' + playlist_id
            if item['index']:
                item['url'] += '&index=' + str(item['index'])
        info['playlist']['author_url'] = util.prefix_url(
            info['playlist']['author_url'])

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
    video_height = yt_data_extract.deep_get(video_sources, 0, 'height', default=360)
    video_width = yt_data_extract.deep_get(video_sources, 0, 'width', default=640)
    # 1 second per pixel, or the actual video width
    theater_video_target_width = max(640, info['duration'] or 0, video_width)

    return flask.render_template('watch.html',
        header_playlist_names   = local_playlist.get_playlist_names(),
        uploader_channel_url    = ('/' + info['author_url']) if info['author_url'] else '',
        time_published             = info['time_published'],
        view_count    = (lambda x: '{:,}'.format(x) if x is not None else "")(info.get("view_count", None)),
        like_count    = (lambda x: '{:,}'.format(x) if x is not None else "")(info.get("like_count", None)),
        dislike_count = (lambda x: '{:,}'.format(x) if x is not None else "")(info.get("dislike_count", None)),
        download_formats        = download_formats,
        video_info              = json.dumps(video_info),
        video_sources           = video_sources,
        subtitle_sources        = get_subtitle_sources(info),
        related                 = info['related_videos'],
        playlist                = info['playlist'],
        music_list              = info['music_list'],
        music_attributes        = get_ordered_music_list_attributes(info['music_list']),
        comments_info           = comments_info,
        comment_count           = info['comment_count'],
        comments_disabled       = info['comments_disabled'],

        theater_mode            = settings.theater_mode,
        related_videos_mode     = settings.related_videos_mode,
        comments_mode           = settings.comments_mode,

        video_height            = video_height,
        theater_video_target_width = theater_video_target_width,

        title       = info['title'],
        uploader    = info['author'],
        description = info['description'],
        unlisted    = info['unlisted'],
        limited_state = info['limited_state'],
        age_restricted    = info['age_restricted'],
        playability_error = info['playability_error'],

        allowed_countries = info['allowed_countries'],
        ip_address   = info['ip_address'] if settings.route_tor else None,
        invidious_used    = info['invidious_used'],
    )


@yt_app.route('/api/<path:dummy>')
def get_captions(dummy):
    result = util.fetch_url('https://www.youtube.com' + request.full_path)
    result = result.replace(b"align:start position:0%", b"")
    return result




