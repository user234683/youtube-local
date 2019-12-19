from youtube import util, proto

import html
import json
import re
import urllib.parse
import collections
from math import ceil
import traceback

# videos:

# id
# title
# url
# author
# author_url
# thumbnail
# description
# time_published (str)
# duration (str)
# like_count (int)
# dislike_count (int)
# view_count (int)
# approx_view_count (str)
# playlist_index

# playlists:

# id
# title
# url
# author
# author_url
# thumbnail
# description
# time_published (str)
# video_count (int)
# first_video_id

# from https://github.com/ytdl-org/youtube-dl/blob/master/youtube_dl/extractor/youtube.py
_formats = {
    '5': {'ext': 'flv', 'width': 400, 'height': 240, 'acodec': 'mp3', 'audio_bitrate': 64, 'vcodec': 'h263'},
    '6': {'ext': 'flv', 'width': 450, 'height': 270, 'acodec': 'mp3', 'audio_bitrate': 64, 'vcodec': 'h263'},
    '13': {'ext': '3gp', 'acodec': 'aac', 'vcodec': 'mp4v'},
    '17': {'ext': '3gp', 'width': 176, 'height': 144, 'acodec': 'aac', 'audio_bitrate': 24, 'vcodec': 'mp4v'},
    '18': {'ext': 'mp4', 'width': 640, 'height': 360, 'acodec': 'aac', 'audio_bitrate': 96, 'vcodec': 'h264'},
    '22': {'ext': 'mp4', 'width': 1280, 'height': 720, 'acodec': 'aac', 'audio_bitrate': 192, 'vcodec': 'h264'},
    '34': {'ext': 'flv', 'width': 640, 'height': 360, 'acodec': 'aac', 'audio_bitrate': 128, 'vcodec': 'h264'},
    '35': {'ext': 'flv', 'width': 854, 'height': 480, 'acodec': 'aac', 'audio_bitrate': 128, 'vcodec': 'h264'},
    # itag 36 videos are either 320x180 (BaW_jenozKc) or 320x240 (__2ABJjxzNo), audio_bitrate varies as well
    '36': {'ext': '3gp', 'width': 320, 'acodec': 'aac', 'vcodec': 'mp4v'},
    '37': {'ext': 'mp4', 'width': 1920, 'height': 1080, 'acodec': 'aac', 'audio_bitrate': 192, 'vcodec': 'h264'},
    '38': {'ext': 'mp4', 'width': 4096, 'height': 3072, 'acodec': 'aac', 'audio_bitrate': 192, 'vcodec': 'h264'},
    '43': {'ext': 'webm', 'width': 640, 'height': 360, 'acodec': 'vorbis', 'audio_bitrate': 128, 'vcodec': 'vp8'},
    '44': {'ext': 'webm', 'width': 854, 'height': 480, 'acodec': 'vorbis', 'audio_bitrate': 128, 'vcodec': 'vp8'},
    '45': {'ext': 'webm', 'width': 1280, 'height': 720, 'acodec': 'vorbis', 'audio_bitrate': 192, 'vcodec': 'vp8'},
    '46': {'ext': 'webm', 'width': 1920, 'height': 1080, 'acodec': 'vorbis', 'audio_bitrate': 192, 'vcodec': 'vp8'},
    '59': {'ext': 'mp4', 'width': 854, 'height': 480, 'acodec': 'aac', 'audio_bitrate': 128, 'vcodec': 'h264'},
    '78': {'ext': 'mp4', 'width': 854, 'height': 480, 'acodec': 'aac', 'audio_bitrate': 128, 'vcodec': 'h264'},


    # 3D videos
    '82': {'ext': 'mp4', 'height': 360, 'format_note': '3D', 'acodec': 'aac', 'audio_bitrate': 128, 'vcodec': 'h264'},
    '83': {'ext': 'mp4', 'height': 480, 'format_note': '3D', 'acodec': 'aac', 'audio_bitrate': 128, 'vcodec': 'h264'},
    '84': {'ext': 'mp4', 'height': 720, 'format_note': '3D', 'acodec': 'aac', 'audio_bitrate': 192, 'vcodec': 'h264'},
    '85': {'ext': 'mp4', 'height': 1080, 'format_note': '3D', 'acodec': 'aac', 'audio_bitrate': 192, 'vcodec': 'h264'},
    '100': {'ext': 'webm', 'height': 360, 'format_note': '3D', 'acodec': 'vorbis', 'audio_bitrate': 128, 'vcodec': 'vp8'},
    '101': {'ext': 'webm', 'height': 480, 'format_note': '3D', 'acodec': 'vorbis', 'audio_bitrate': 192, 'vcodec': 'vp8'},
    '102': {'ext': 'webm', 'height': 720, 'format_note': '3D', 'acodec': 'vorbis', 'audio_bitrate': 192, 'vcodec': 'vp8'},

    # Apple HTTP Live Streaming
    '91': {'ext': 'mp4', 'height': 144, 'format_note': 'HLS', 'acodec': 'aac', 'audio_bitrate': 48, 'vcodec': 'h264'},
    '92': {'ext': 'mp4', 'height': 240, 'format_note': 'HLS', 'acodec': 'aac', 'audio_bitrate': 48, 'vcodec': 'h264'},
    '93': {'ext': 'mp4', 'height': 360, 'format_note': 'HLS', 'acodec': 'aac', 'audio_bitrate': 128, 'vcodec': 'h264'},
    '94': {'ext': 'mp4', 'height': 480, 'format_note': 'HLS', 'acodec': 'aac', 'audio_bitrate': 128, 'vcodec': 'h264'},
    '95': {'ext': 'mp4', 'height': 720, 'format_note': 'HLS', 'acodec': 'aac', 'audio_bitrate': 256, 'vcodec': 'h264'},
    '96': {'ext': 'mp4', 'height': 1080, 'format_note': 'HLS', 'acodec': 'aac', 'audio_bitrate': 256, 'vcodec': 'h264'},
    '132': {'ext': 'mp4', 'height': 240, 'format_note': 'HLS', 'acodec': 'aac', 'audio_bitrate': 48, 'vcodec': 'h264'},
    '151': {'ext': 'mp4', 'height': 72, 'format_note': 'HLS', 'acodec': 'aac', 'audio_bitrate': 24, 'vcodec': 'h264'},

    # DASH mp4 video
    '133': {'ext': 'mp4', 'height': 240, 'format_note': 'DASH video', 'vcodec': 'h264'},
    '134': {'ext': 'mp4', 'height': 360, 'format_note': 'DASH video', 'vcodec': 'h264'},
    '135': {'ext': 'mp4', 'height': 480, 'format_note': 'DASH video', 'vcodec': 'h264'},
    '136': {'ext': 'mp4', 'height': 720, 'format_note': 'DASH video', 'vcodec': 'h264'},
    '137': {'ext': 'mp4', 'height': 1080, 'format_note': 'DASH video', 'vcodec': 'h264'},
    '138': {'ext': 'mp4', 'format_note': 'DASH video', 'vcodec': 'h264'},  # Height can vary (https://github.com/ytdl-org/youtube-dl/issues/4559)
    '160': {'ext': 'mp4', 'height': 144, 'format_note': 'DASH video', 'vcodec': 'h264'},
    '212': {'ext': 'mp4', 'height': 480, 'format_note': 'DASH video', 'vcodec': 'h264'},
    '264': {'ext': 'mp4', 'height': 1440, 'format_note': 'DASH video', 'vcodec': 'h264'},
    '298': {'ext': 'mp4', 'height': 720, 'format_note': 'DASH video', 'vcodec': 'h264', 'fps': 60},
    '299': {'ext': 'mp4', 'height': 1080, 'format_note': 'DASH video', 'vcodec': 'h264', 'fps': 60},
    '266': {'ext': 'mp4', 'height': 2160, 'format_note': 'DASH video', 'vcodec': 'h264'},

    # Dash mp4 audio
    '139': {'ext': 'm4a', 'format_note': 'DASH audio', 'acodec': 'aac', 'audio_bitrate': 48, 'container': 'm4a_dash'},
    '140': {'ext': 'm4a', 'format_note': 'DASH audio', 'acodec': 'aac', 'audio_bitrate': 128, 'container': 'm4a_dash'},
    '141': {'ext': 'm4a', 'format_note': 'DASH audio', 'acodec': 'aac', 'audio_bitrate': 256, 'container': 'm4a_dash'},
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
    '171': {'ext': 'webm', 'acodec': 'vorbis', 'format_note': 'DASH audio', 'audio_bitrate': 128},
    '172': {'ext': 'webm', 'acodec': 'vorbis', 'format_note': 'DASH audio', 'audio_bitrate': 256},

    # Dash webm audio with opus inside
    '249': {'ext': 'webm', 'format_note': 'DASH audio', 'acodec': 'opus', 'audio_bitrate': 50},
    '250': {'ext': 'webm', 'format_note': 'DASH audio', 'acodec': 'opus', 'audio_bitrate': 70},
    '251': {'ext': 'webm', 'format_note': 'DASH audio', 'acodec': 'opus', 'audio_bitrate': 160},

    # RTMP (unnamed)
    '_rtmp': {'protocol': 'rtmp'},

    # av01 video only formats sometimes served with "unknown" codecs
    '394': {'vcodec': 'av01.0.05M.08'},
    '395': {'vcodec': 'av01.0.05M.08'},
    '396': {'vcodec': 'av01.0.05M.08'},
    '397': {'vcodec': 'av01.0.05M.08'},
}

def get(object, key, default=None, types=()):
    '''Like dict.get(), but returns default if the result doesn't match one of the types.
       Also works for indexing lists.'''
    try:
        result = object[key]
    except (TypeError, IndexError, KeyError):
        return default

    if not types or isinstance(result, types):
        return result
    else:
        return default

def multi_get(object, *keys, default=None, types=()):
    '''Like get, but try other keys if the first fails'''
    for key in keys:
        try:
            result = object[key]
        except (TypeError, IndexError, KeyError):
            pass
        else:
            if not types or isinstance(result, types):
                return result
            else:
                continue
    return default


def deep_get(object, *keys, default=None, types=()):
    '''Like dict.get(), but for nested dictionaries/sequences, supporting keys or indices.
       Last argument is the default value to use in case of any IndexErrors or KeyErrors.
       If types is given and the result doesn't match one of those types, default is returned'''
    try:
        for key in keys:
            object = object[key]
    except (TypeError, IndexError, KeyError):
        return default
    else:
        if not types or isinstance(object, types):
            return object
        else:
            return default

def multi_deep_get(object, *key_sequences, default=None, types=()):
    '''Like deep_get, but can try different key sequences in case one fails.
       Return default if all of them fail. key_sequences is a list of lists'''
    for key_sequence in key_sequences:
        _object = object
        try:
            for key in key_sequence:
                _object = _object[key]
        except (TypeError, IndexError, KeyError):
            pass
        else:
            if not types or isinstance(_object, types):
                return _object
            else:
                continue
    return default

def liberal_update(obj, key, value):
    '''Updates obj[key] with value as long as value is not None.
    Ensures obj[key] will at least get a value of None, however'''
    if (value is not None) or (key not in obj):
        obj[key] = value

def conservative_update(obj, key, value):
    '''Only updates obj if it doesn't have key or obj[key] is None'''
    if obj.get(key) is None:
        obj[key] = value

def remove_redirect(url):
    if re.fullmatch(r'(((https?:)?//)?(www.)?youtube.com)?/redirect\?.*', url) is not None: # youtube puts these on external links to do tracking
        query_string = url[url.find('?')+1: ]
        return urllib.parse.parse_qs(query_string)['q'][0]
    return url

def _recover_urls(runs):
    for run in runs:
        url = deep_get(run, 'navigationEndpoint', 'urlEndpoint', 'url')
        text = run.get('text', '')
        # second condition is necessary because youtube makes other things into urls, such as hashtags, which we want to keep as text
        if url is not None and (text.startswith('http://') or text.startswith('https://')):
            url = remove_redirect(url)
            run['url'] = url
            run['text'] = url # youtube truncates the url text, use actual url instead

def extract_str(node, default=None, recover_urls=False):
    '''default is the value returned if the extraction fails. If recover_urls is true, will attempt to fix Youtube's truncation of url text (most prominently seen in descriptions)'''
    if isinstance(node, str):
        return node

    try:
        return node['simpleText']
    except (KeyError, TypeError):
        pass

    if isinstance(node, dict) and 'runs' in node:
        if recover_urls:
            _recover_urls(node['runs'])
        return ''.join(text_run.get('text', '') for text_run in node['runs'])

    return default

def extract_formatted_text(node):
    if not node:
        return []
    if 'runs' in node:
        _recover_urls(node['runs'])
        return node['runs']
    elif 'simpleText' in node:
        return [{'text': node['simpleText']}]
    return []

def extract_int(string):
    if isinstance(string, int):
        return string
    if not isinstance(string, str):
        string = extract_str(string)
    if not string:
        return None
    match = re.search(r'(\d+)', string.replace(',', ''))
    if match is None:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None

def extract_approx_int(string):
    '''e.g. "15M" from "15M subscribers"'''
    if not isinstance(string, str):
        string = extract_str(string)
    if not string:
        return None
    match = re.search(r'(\d+[KMBTkmbt])', string.replace(',', ''))
    if match is None:
        return None
    return match.group(1)

youtube_url_re = re.compile(r'^(?:(?:(?:https?:)?//)?(?:www\.)?youtube\.com)?(/.*)$')
def normalize_url(url):
    if url is None:
        return None
    match = youtube_url_re.fullmatch(url)
    if match is None:
        raise Exception()

    return 'https://www.youtube.com' + match.group(1)

def prefix_urls(item):
    try:
        item['thumbnail'] = util.prefix_url(item['thumbnail'])
    except KeyError:
        pass

    try:
        item['author_url'] = util.prefix_url(item['author_url'])
    except KeyError:
        pass

def add_extra_html_info(item):
    if item['type'] == 'video':
        item['url'] = (util.URL_ORIGIN + '/watch?v=' + item['id']) if item.get('id') else None

        video_info = {}
        for key in ('id', 'title', 'author', 'duration'):
            try:
                video_info[key] = item[key]
            except KeyError:
                video_info[key] = ''

        item['video_info'] = json.dumps(video_info)

    elif item['type'] == 'playlist':
        item['url'] = (util.URL_ORIGIN + '/playlist?list=' + item['id']) if item.get('id') else None
    elif item['type'] == 'channel':
        item['url'] = (util.URL_ORIGIN + "/channel/" + item['id']) if item.get('id') else None

def extract_item_info(item, additional_info={}):
    if not item:
        return {'error': 'No item given'}

    type = get(list(item.keys()), 0)
    if not type:
        return {'error': 'Could not find type'}
    item = item[type]

    info = {'error': None}
    if type in ('itemSectionRenderer', 'compactAutoplayRenderer'):
        return extract_item_info(deep_get(item, 'contents', 0), additional_info)

    if type in ('movieRenderer', 'clarificationRenderer'):
        info['type'] = 'unsupported'
        return info

    info.update(additional_info)

    # type looks like e.g. 'compactVideoRenderer' or 'gridVideoRenderer'
    # camelCase split, https://stackoverflow.com/a/37697078
    type_parts = [s.lower() for s in re.sub(r'([A-Z][a-z]+)', r' \1', type).split()]
    if len(type_parts) < 2:
        info['type'] = 'unsupported'
        return
    primary_type = type_parts[-2]
    if primary_type == 'video':
        info['type'] = 'video'
    elif primary_type in ('playlist', 'radio', 'show'):
        info['type'] = 'playlist'
    elif primary_type == 'channel':
        info['type'] = 'channel'
    else:
        info['type'] = 'unsupported'

    info['title'] = extract_str(item.get('title'))
    info['author'] = extract_str(multi_get(item, 'longBylineText', 'shortBylineText', 'ownerText'))
    info['author_id'] = extract_str(multi_deep_get(item,
        ['longBylineText', 'runs', 0, 'navigationEndpoint', 'browseEndpoint', 'browseId'],
        ['shortBylineText', 'runs', 0, 'navigationEndpoint', 'browseEndpoint', 'browseId'],
        ['ownerText', 'runs', 0, 'navigationEndpoint', 'browseEndpoint', 'browseId']
    ))
    info['author_url'] = ('https://www.youtube.com/channel/' + info['author_id']) if info['author_id'] else None
    info['description'] = extract_formatted_text(multi_get(item, 'descriptionSnippet', 'descriptionText'))
    info['thumbnail'] = multi_deep_get(item,
        ['thumbnail', 'thumbnails', 0, 'url'],      # videos
        ['thumbnails', 0, 'thumbnails', 0, 'url'],  # playlists
        ['thumbnailRenderer', 'showCustomThumbnailRenderer', 'thumbnail', 'thumbnails', 0, 'url'], # shows
    )

    info['badges'] = []
    for badge_node in multi_get(item, 'badges', 'ownerBadges', default=()):
        badge = deep_get(badge_node, 'metadataBadgeRenderer', 'label')
        if badge:
            info['badges'].append(badge)

    if primary_type in ('video', 'playlist'):
        info['time_published'] = extract_str(item.get('publishedTimeText'))

    if primary_type == 'video':
        info['id'] = item.get('videoId')
        info['view_count'] = extract_int(item.get('viewCountText'))

        # dig into accessibility data to get view_count for videos marked as recommended, and to get time_published
        accessibility_label = deep_get(item, 'title', 'accessibility', 'accessibilityData', 'label', default='')
        timestamp = re.search(r'(\d+ \w+ ago)', accessibility_label)
        if timestamp:
            conservative_update(info, 'time_published', timestamp.group(1))
        view_count = re.search(r'(\d+) views', accessibility_label.replace(',', ''))
        if view_count:
            conservative_update(info, 'view_count', int(view_count.group(1)))

        if info['view_count']:
            info['approx_view_count'] = '{:,}'.format(info['view_count'])
        else:
            info['approx_view_count'] = extract_approx_int(multi_get(item, 'shortViewCountText'))
        info['duration'] = extract_str(item.get('lengthText'))
    elif primary_type == 'playlist':
        info['id'] = item.get('playlistId')
        info['video_count'] = extract_int(item.get('videoCount'))
    elif primary_type == 'channel':
        info['id'] = item.get('channelId')
        info['approx_subscriber_count'] = extract_approx_int(item.get('subscriberCountText'))
    elif primary_type == 'show':
        info['id'] = deep_get(item, 'navigationEndpoint', 'watchEndpoint', 'playlistId')

    if primary_type in ('playlist', 'channel'):
        conservative_update(info, 'video_count', extract_int(item.get('videoCountText')))

    for overlay in item.get('thumbnailOverlays', []):
        conservative_update(info, 'duration', extract_str(deep_get(
            overlay, 'thumbnailOverlayTimeStatusRenderer', 'text'
        )))
        # show renderers don't have videoCountText
        conservative_update(info, 'video_count', extract_int(deep_get(
            overlay, 'thumbnailOverlayBottomPanelRenderer', 'text'
        )))
    return info

def parse_info_prepare_for_html(renderer, additional_info={}):
    item = extract_item_info(renderer, additional_info)
    prefix_urls(item)
    add_extra_html_info(item)

    return item

def extract_response(polymer_json):
    '''return response, error'''
    response = multi_deep_get(polymer_json, [1, 'response'], ['response'], default=None, types=dict)
    if response is None:
        return None, 'Failed to extract response'
    else:
        return response, None


list_types = {
    'sectionListRenderer',
    'itemSectionRenderer',
    'gridRenderer',
    'playlistVideoListRenderer',
}

item_types = {
    'movieRenderer',
    'didYouMeanRenderer',
    'showingResultsForRenderer',

    'videoRenderer',
    'compactVideoRenderer',
    'compactAutoplayRenderer',
    'gridVideoRenderer',
    'playlistVideoRenderer',

    'playlistRenderer',
    'compactPlaylistRenderer',
    'gridPlaylistRenderer',

    'radioRenderer',
    'compactRadioRenderer',
    'gridRadioRenderer',

    'showRenderer',
    'compactShowRenderer',
    'gridShowRenderer',


    'channelRenderer',
    'compactChannelRenderer',
    'gridChannelRenderer',

    'channelAboutFullMetadataRenderer',
}

def traverse_browse_renderer(renderer):
    for tab in get(renderer, 'tabs', (), types=(list, tuple)):
        tab_renderer = multi_deep_get(tab, ['tabRenderer'], ['expandableTabRenderer'], default=None, types=dict)
        if tab_renderer is None:
            continue
        if tab_renderer.get('selected', False):
            return get(tab_renderer, 'content', {}, types=(dict))
    print('Could not find tab with content')
    return {}

def traverse_standard_list(renderer):
    renderer_list = multi_deep_get(renderer, ['contents'], ['items'], default=(), types=(list, tuple))
    continuation = deep_get(renderer, 'continuations', 0, 'nextContinuationData', 'continuation')
    return renderer_list, continuation

# these renderers contain one inside them
nested_renderer_dispatch = {
    'singleColumnBrowseResultsRenderer': traverse_browse_renderer,
    'twoColumnBrowseResultsRenderer': traverse_browse_renderer,
    'twoColumnSearchResultsRenderer': lambda renderer: get(renderer, 'primaryContents', {}, types=dict),
}

# these renderers contain a list of renderers in side them
nested_renderer_list_dispatch = {
    'sectionListRenderer': traverse_standard_list,
    'itemSectionRenderer': traverse_standard_list,
    'gridRenderer': traverse_standard_list,
    'playlistVideoListRenderer': traverse_standard_list,
    'singleColumnWatchNextResults': lambda r: (deep_get(r, 'results', 'results', 'contents', default=[], types=(list, tuple)), None),
}

def extract_items(response, item_types=item_types):
    '''return items, ctoken'''
    if 'continuationContents' in response:
        # always has just the one [something]Continuation key, but do this just in case they add some tracking key or something
        for key, renderer_continuation in get(response, 'continuationContents', {}, types=dict).items():
            if key.endswith('Continuation'):    # e.g. commentSectionContinuation, playlistVideoListContinuation
                items = multi_deep_get(renderer_continuation, ['contents'], ['items'], default=None, types=(list, tuple))
                ctoken = deep_get(renderer_continuation, 'continuations', 0, 'nextContinuationData', 'continuation', default=None, types=str)
                return items, ctoken
        return [], None
    elif 'contents' in response:
        ctoken = None
        items = []

        iter_stack = collections.deque()
        current_iter = iter(())

        renderer = get(response, 'contents', {}, types=dict)

        while True:
            # mode 1: dig into the current renderer
            # Will stay in mode 1 (via continue) if a new renderer is found inside this one
            # Otherwise, after finding that it is an item renderer,
            # contains a list, or contains nothing,
            # falls through into mode 2 to get a new renderer
            if len(renderer) != 0:
                key, value = list(renderer.items())[0]

                # has a list in it, add it to the iter stack
                if key in nested_renderer_list_dispatch:
                    renderer_list, continuation = nested_renderer_list_dispatch[key](value)
                    if renderer_list:
                        iter_stack.append(current_iter)
                        current_iter = iter(renderer_list)
                    if continuation:
                        ctoken = continuation

                # new renderer nested inside this one
                elif key in nested_renderer_dispatch:
                    renderer = nested_renderer_dispatch[key](value)
                    continue    # back to mode 1

                # the renderer is an item
                elif key in item_types:
                    items.append(renderer)


            # mode 2: get a new renderer by iterating.
            # goes up the stack for an iterator if one has been exhausted
            while current_iter is not None:
                try:
                    renderer = current_iter.__next__()
                    break
                except StopIteration:
                    try:
                        current_iter = iter_stack.pop()   # go back up the stack
                    except IndexError:
                        return items, ctoken

    else:
        return [], None

def extract_channel_info(polymer_json, tab):
    response, err = extract_response(polymer_json)
    if err:
        return {'error': err}

    try:
        microformat = response['microformat']['microformatDataRenderer']

    # channel doesn't exist or was terminated
    # example terminated channel: https://www.youtube.com/channel/UCnKJeK_r90jDdIuzHXC0Org
    except KeyError:
        if 'alerts' in response and len(response['alerts']) > 0:
            return {'error': ' '.join(alert['alertRenderer']['text']['simpleText'] for alert in response['alerts']) }
        elif 'errors' in response['responseContext']:
            for error in response['responseContext']['errors']['error']:
                if error['code'] == 'INVALID_VALUE' and error['location'] == 'browse_id':
                    return {'error': 'This channel does not exist'}
        return {'error': 'Failure getting microformat'}

    info = {'error': None}
    info['current_tab'] = tab


    # stuff from microformat (info given by youtube for every page on channel)
    info['short_description'] = microformat['description']
    info['channel_name'] = microformat['title']
    info['avatar'] = microformat['thumbnail']['thumbnails'][0]['url']
    channel_url = microformat['urlCanonical'].rstrip('/')
    channel_id = channel_url[channel_url.rfind('/')+1:]
    info['channel_id'] = channel_id
    info['channel_url'] = 'https://www.youtube.com/channel/' + channel_id

    info['items'] = []

    # empty channel
    if 'contents' not in response and 'continuationContents' not in response:
        return info


    items, _ = extract_items(response)
    if tab in ('videos', 'playlists', 'search'):
        additional_info = {'author': info['channel_name'], 'author_url': 'https://www.youtube.com/channel/' + channel_id}
        info['items'] = [extract_item_info(renderer, additional_info) for renderer in items]

    elif tab == 'about':
        for item in items:
            try:
                channel_metadata = item['channelAboutFullMetadataRenderer']
                break
            except KeyError:
                pass
        else:
            info['error'] = 'Could not find channelAboutFullMetadataRenderer'
            return info

        info['links'] = []
        for link_json in channel_metadata.get('primaryLinks', ()):
            url = remove_redirect(link_json['navigationEndpoint']['urlEndpoint']['url'])

            text = extract_str(link_json['title'])

            info['links'].append( (text, url) )


        info['stats'] = []
        for stat_name in ('subscriberCountText', 'joinedDateText', 'viewCountText', 'country'):
            try:
                stat = channel_metadata[stat_name]
            except KeyError:
                continue
            info['stats'].append(extract_str(stat))

        if 'description' in channel_metadata:
            info['description'] = extract_str(channel_metadata['description'])
        else:
            info['description'] = ''

    else:
        raise NotImplementedError('Unknown or unsupported channel tab: ' + tab)

    return info

def extract_search_info(polymer_json):
    response, err = extract_response(polymer_json)
    if err:
        return {'error': err}
    info = {'error': None}
    info['estimated_results'] = int(response['estimatedResults'])
    info['estimated_pages'] = ceil(info['estimated_results']/20)


    results, _ = extract_items(response)


    info['items'] = []
    info['corrections'] = {'type': None}
    for renderer in results:
        type = list(renderer.keys())[0]
        if type == 'shelfRenderer':
            continue
        if type == 'didYouMeanRenderer':
            renderer = renderer[type]

            info['corrections'] = {
                'type': 'did_you_mean',
                'corrected_query': renderer['correctedQueryEndpoint']['searchEndpoint']['query'],
                'corrected_query_text': renderer['correctedQuery']['runs'],
            }
            continue
        if type == 'showingResultsForRenderer':
            renderer = renderer[type]

            info['corrections'] = {
                'type': 'showing_results_for',
                'corrected_query_text': renderer['correctedQuery']['runs'],
                'original_query_text': renderer['originalQuery']['simpleText'],
            }
            continue

        i_info = extract_item_info(renderer)
        if i_info.get('type') != 'unsupported':
            info['items'].append(i_info)


    return info

def extract_playlist_metadata(polymer_json):
    response, err = extract_response(polymer_json)
    if err:
        return {'error': err}

    metadata = {'error': None}
    header = deep_get(response, 'header', 'playlistHeaderRenderer', default={})
    metadata['title'] = extract_str(header.get('title'))

    metadata['first_video_id'] = deep_get(header, 'playEndpoint', 'watchEndpoint', 'videoId')
    first_id = re.search(r'([a-z_\-]{11})', deep_get(header,
        'thumbnail', 'thumbnails', 0, 'url', default=''))
    if first_id:
        conservative_update(metadata, 'first_video_id', first_id.group(1))
    if metadata['first_video_id'] is None:
        metadata['thumbnail'] = None
    else:
        metadata['thumbnail'] = 'https://i.ytimg.com/vi/' + metadata['first_video_id'] + '/mqdefault.jpg'

    metadata['video_count'] = extract_int(header.get('numVideosText'))
    metadata['description'] = extract_str(header.get('descriptionText'), default='')
    metadata['author'] = extract_str(header.get('ownerText'))
    metadata['author_id'] = multi_deep_get(header, 
        ['ownerText', 'runs', 0, 'navigationEndpoint', 'browseEndpoint', 'browseId'],
        ['ownerEndpoint', 'browseEndpoint', 'browseId'])
    if metadata['author_id']:
        metadata['author_url'] = 'https://www.youtube.com/channel/' + metadata['author_id']
    else:
        metadata['author_url'] = None
    metadata['view_count'] = extract_int(header.get('viewCountText'))
    metadata['like_count'] = extract_int(header.get('likesCountWithoutLikeText'))
    for stat in header.get('stats', ()):
        text = extract_str(stat)
        if 'videos' in text:
            conservative_update(metadata, 'video_count', extract_int(text))
        elif 'views' in text:
            conservative_update(metadata, 'view_count', extract_int(text))
        elif 'updated' in text:
            metadata['time_published'] = extract_date(text)

    return metadata

def extract_playlist_info(polymer_json):
    response, err = extract_response(polymer_json)
    if err:
        return {'error': err}
    info = {'error': None}
    first_page = 'continuationContents' not in response
    video_list, _ = extract_items(response)

    info['items'] = [extract_item_info(renderer) for renderer in video_list]

    if first_page:
        info['metadata'] = extract_playlist_metadata(polymer_json)

    return info

def ctoken_metadata(ctoken):
    result = dict()
    params = proto.parse(proto.b64_to_bytes(ctoken))
    result['video_id'] = proto.parse(params[2])[2].decode('ascii')

    offset_information = proto.parse(params[6])
    result['offset'] = offset_information.get(5, 0)

    result['is_replies'] = False
    if (3 in offset_information) and (2 in proto.parse(offset_information[3])):
        result['is_replies'] = True
        result['sort'] = None
    else:
        try:
            result['sort'] = proto.parse(offset_information[4])[6]
        except KeyError:
            result['sort'] = 0
    return result

def parse_comments_polymer(polymer_json):
    try:
        video_title = ''
        response, err = extract_response(polymer_json)
        if err:
            raise Exception(err)

        try:
            url = polymer_json[1]['url']
        except (TypeError, IndexError, KeyError):
            url = polymer_json['url']

        ctoken = urllib.parse.parse_qs(url[url.find('?')+1:])['ctoken'][0]
        metadata = ctoken_metadata(ctoken)

        comments_raw, ctoken = extract_items(response)

        comments = []
        for comment_json in comments_raw:
            number_of_replies = 0
            try:
                comment_thread = comment_json['commentThreadRenderer']
            except KeyError:
                comment_renderer = comment_json['commentRenderer']
            else:
                if 'commentTargetTitle' in comment_thread:
                    video_title = comment_thread['commentTargetTitle']['runs'][0]['text']

                if 'replies' in comment_thread:
                    view_replies_text = extract_str(comment_thread['replies']['commentRepliesRenderer']['moreText'])
                    view_replies_text = view_replies_text.replace(',', '')
                    match = re.search(r'(\d+)', view_replies_text)
                    if match is None:
                        number_of_replies = 1
                    else:
                        number_of_replies = int(match.group(1))
                comment_renderer = comment_thread['comment']['commentRenderer']

            comment = {
                'author_id': comment_renderer.get('authorId', ''),
                'author_avatar': comment_renderer['authorThumbnail']['thumbnails'][0]['url'],
                'like_count': comment_renderer['likeCount'],
                'time_published': extract_str(comment_renderer['publishedTimeText']),
                'text': comment_renderer['contentText'].get('runs', ''),
                'reply_count': number_of_replies,
                'id': comment_renderer['commentId'],
            }

            if 'authorText' in comment_renderer:     # deleted channels have no name or channel link
                comment['author'] = extract_str(comment_renderer['authorText'])
                comment['author_url'] = comment_renderer['authorEndpoint']['commandMetadata']['webCommandMetadata']['url']
                comment['author_channel_id'] = comment_renderer['authorEndpoint']['browseEndpoint']['browseId']
            else:
                comment['author'] = ''
                comment['author_url'] = ''
                comment['author_channel_id'] = ''

            comments.append(comment)
    except Exception as e:
        print('Error parsing comments: ' + str(e))
        comments = ()
        ctoken = ''

    return {
        'ctoken': ctoken,
        'comments': comments,
        'video_title': video_title,
        'video_id': metadata['video_id'],
        'offset': metadata['offset'],
        'is_replies': metadata['is_replies'],
        'sort': metadata['sort'],
    }

def check_missing_keys(object, *key_sequences):
    for key_sequence in key_sequences:
        _object = object
        try:
            for key in key_sequence:
                _object = _object[key]
        except (KeyError, IndexError, TypeError):
            return 'Could not find ' + key

    return None

def extract_metadata_row_info(video_renderer_info):
    # extract category and music list
    info = {
        'category': None,
        'music_list': [],
    }

    current_song = {}
    for row in deep_get(video_renderer_info, 'metadataRowContainer', 'metadataRowContainerRenderer', 'rows', default=[]):
        row_title = extract_str(deep_get(row, 'metadataRowRenderer', 'title'), default='')
        row_content = extract_str(deep_get(row, 'metadataRowRenderer', 'contents', 0))
        if row_title == 'Category':
            info['category'] = row_content
        elif row_title in ('Song', 'Music'):
            if current_song:
                info['music_list'].append(current_song)
            current_song = {'title': row_content}
        elif row_title == 'Artist':
            current_song['artist'] = row_content
        elif row_title == 'Album':
            current_song['album'] = row_content
        elif row_title == 'Writers':
            current_song['writers'] = row_content
        elif row_title.startswith('Licensed'):
            current_song['licensor'] = row_content
    if current_song:
        info['music_list'].append(current_song)

    return info

def extract_date(date_text):
    if date_text is None:
        return None

    date_text = date_text.replace(',', '').lower()
    parts = date_text.split()
    if len(parts) >= 3:
        month, day, year = parts[-3:]
        month = month_abbreviations.get(month[0:3]) # slicing in case they start writing out the full month name
        if month and (re.fullmatch(r'\d\d?', day) is not None) and (re.fullmatch(r'\d{4}', year) is not None):
            return year + '-' + month + '-' + day

def extract_watch_info_mobile(top_level):
    info = {}
    microformat = deep_get(top_level, 'playerResponse', 'microformat', 'playerMicroformatRenderer', default={})

    family_safe = microformat.get('isFamilySafe')
    if family_safe is None:
        info['age_restricted'] = None
    else:
        info['age_restricted'] = not family_safe
    info['allowed_countries'] = microformat.get('availableCountries', [])
    info['time_published'] = microformat.get('publishDate')

    response = top_level.get('response', {})

    # video info from metadata renderers
    items, _ = extract_items(response, item_types={'slimVideoMetadataRenderer'})
    if items:
        video_info = items[0]['slimVideoMetadataRenderer']
    else:
        print('Failed to extract video metadata')
        video_info = {}

    info.update(extract_metadata_row_info(video_info))
    info['description'] = extract_str(video_info.get('description'), recover_urls=True)
    info['view_count'] = extract_int(extract_str(video_info.get('expandedSubtitle')))
    info['author'] = extract_str(deep_get(video_info, 'owner', 'slimOwnerRenderer', 'title'))
    info['author_id'] = deep_get(video_info, 'owner', 'slimOwnerRenderer', 'navigationEndpoint', 'browseEndpoint', 'browseId')
    info['title'] = extract_str(video_info.get('title'))
    info['live'] = 'watching' in extract_str(video_info.get('expandedSubtitle'), default='')
    info['unlisted'] = False
    for badge in video_info.get('badges', []):
        if deep_get(badge, 'metadataBadgeRenderer', 'label') == 'Unlisted':
            info['unlisted'] = True
    info['like_count'] = None
    info['dislike_count'] = None
    if not info['time_published']:
        info['time_published'] = extract_date(extract_str(video_info.get('dateText', None)))
    for button in video_info.get('buttons', ()):
        button_renderer = button.get('slimMetadataToggleButtonRenderer', {})

        # all the digits can be found in the accessibility data
        count = extract_int(deep_get(button_renderer, 'button', 'toggleButtonRenderer', 'defaultText', 'accessibility', 'accessibilityData', 'label'))

        # this count doesn't have all the digits, it's like 53K for instance
        dumb_count = extract_int(extract_str(deep_get(button_renderer, 'button', 'toggleButtonRenderer', 'defaultText')))

        # the accessibility text will be "No likes" or "No dislikes" or something like that, but dumb count will be 0
        if dumb_count == 0:
            count = 0

        if 'isLike' in button_renderer:
            info['like_count'] = count
        elif 'isDislike' in button_renderer:
            info['dislike_count'] = count

    # comment section info
    items, _ = extract_items(response, item_types={'commentSectionRenderer'})
    if items:
        comment_info = items[0]['commentSectionRenderer']
        comment_count_text = extract_str(deep_get(comment_info, 'header', 'commentSectionHeaderRenderer', 'countText'))
        if comment_count_text == 'Comments':    # just this with no number, means 0 comments
            info['comment_count'] = 0
        else:
            info['comment_count'] = extract_int(comment_count_text)
        info['comments_disabled'] = False
    else:   # no comment section present means comments are disabled
        info['comment_count'] = 0
        info['comments_disabled'] = True

    # check for limited state
    items, _ = extract_items(response, item_types={'limitedStateMessageRenderer'})
    if items:
        info['limited_state'] = True
    else:
        info['limited_state'] = False

    # related videos
    related, _ = extract_items(response)
    info['related_videos'] = [extract_item_info(renderer) for renderer in related]

    return info

month_abbreviations = {'jan':'1', 'feb':'2', 'mar':'3', 'apr':'4', 'may':'5', 'jun':'6', 'jul':'7', 'aug':'8', 'sep':'9', 'oct':'10', 'nov':'11', 'dec':'12'}
def extract_watch_info_desktop(top_level):
    info = {
        'comment_count': None,
        'comments_disabled': None,
        'allowed_countries': None,
        'limited_state': None,
    }

    video_info = {}
    for renderer in deep_get(top_level, 'response', 'contents', 'twoColumnWatchNextResults', 'results', 'results', 'contents', default=()):
        if renderer and list(renderer.keys())[0] in ('videoPrimaryInfoRenderer', 'videoSecondaryInfoRenderer'):
            video_info.update(list(renderer.values())[0])

    info.update(extract_metadata_row_info(video_info))
    info['description'] = extract_str(video_info.get('description', None), recover_urls=True)
    info['time_published'] = extract_date(extract_str(video_info.get('dateText', None)))

    likes_dislikes = deep_get(video_info, 'sentimentBar', 'sentimentBarRenderer', 'tooltip', default='').split('/')
    if len(likes_dislikes) == 2:
        info['like_count'] = extract_int(likes_dislikes[0])
        info['dislike_count'] = extract_int(likes_dislikes[1])
    else:
        info['like_count'] = None
        info['dislike_count'] = None

    info['title'] = extract_str(video_info.get('title', None))
    info['author'] = extract_str(deep_get(video_info, 'owner', 'videoOwnerRenderer', 'title'))
    info['author_id'] = deep_get(video_info, 'owner', 'videoOwnerRenderer', 'navigationEndpoint', 'browseEndpoint', 'browseId')
    info['view_count'] = extract_int(extract_str(deep_get(video_info, 'viewCount', 'videoViewCountRenderer', 'viewCount')))

    related = deep_get(top_level, 'response', 'contents', 'twoColumnWatchNextResults', 'secondaryResults', 'secondaryResults', 'results', default=[])
    info['related_videos'] = [extract_item_info(renderer) for renderer in related]

    return info

def get_caption_url(info, language, format, automatic=False, translation_language=None):
    '''Gets the url for captions with the given language and format. If automatic is True, get the automatic captions for that language. If translation_language is given, translate the captions from `language` to `translation_language`. If automatic is true and translation_language is given, the automatic captions will be translated.'''
    url = info['_captions_base_url']
    url += '&lang=' + language
    url += '&fmt=' + format
    if automatic:
        url += '&kind=asr'
    elif language in info['_manual_caption_language_names']:
        url += '&name=' + urllib.parse.quote(info['_manual_caption_language_names'][language], safe='')

    if translation_language:
        url += '&tlang=' + translation_language
    return url

def extract_formats(info, player_response):
    streaming_data = player_response.get('streamingData', {})
    yt_formats = streaming_data.get('formats', []) + streaming_data.get('adaptiveFormats', [])

    info['formats'] = []

    for yt_fmt in yt_formats:
        fmt = {}
        fmt['ext'] = None
        fmt['audio_bitrate'] = None
        fmt['acodec'] = None
        fmt['vcodec'] = None
        fmt['width'] = yt_fmt.get('width')
        fmt['height'] = yt_fmt.get('height')
        fmt['file_size'] = yt_fmt.get('contentLength')
        fmt['audio_sample_rate'] = yt_fmt.get('audioSampleRate')
        fmt['fps'] = yt_fmt.get('fps')
        cipher = dict(urllib.parse.parse_qsl(yt_fmt.get('cipher', '')))
        if cipher:
            fmt['url'] = cipher.get('url')
        else:
            fmt['url'] = yt_fmt.get('url')
        fmt['s'] = cipher.get('s')
        fmt['sp'] = cipher.get('sp')
        fmt.update(_formats.get(str(yt_fmt.get('itag')), {}))

        info['formats'].append(fmt)

def extract_playability_error(info, player_response, error_prefix=''):
    if info['formats']:
        info['playability_status'] = None
        info['playability_error'] = None
        return

    playability_status = deep_get(player_response, 'playabilityStatus', 'status', default=None)
    info['playability_status'] = playability_status

    playability_reason = extract_str(multi_deep_get(player_response,
        ['playabilityStatus', 'reason'],
        ['playabilityStatus', 'errorScreen', 'playerErrorMessageRenderer', 'reason'],
        default='Could not find playability error')
    )

    if playability_status not in (None, 'OK'):
        info['playability_error'] = error_prefix + playability_reason
    else:
        info['playability_error'] = error_prefix + 'Unknown playability error'

SUBTITLE_FORMATS = ('srv1', 'srv2', 'srv3', 'ttml', 'vtt')
def extract_watch_info(polymer_json):
    info = {'playability_error': None, 'error': None}

    if isinstance(polymer_json, dict):
        top_level = polymer_json
    elif isinstance(polymer_json, (list, tuple)):
        top_level = {}
        for page_part in polymer_json:
            if not isinstance(page_part, dict):
                return {'error': 'Invalid page part'}
            top_level.update(page_part)
    else:
        return {'error': 'Invalid top level polymer data'}

    error = check_missing_keys(top_level,
        ['player', 'args'],
        ['player', 'assets', 'js'],
        ['playerResponse'],
    )
    if error:
        info['playability_error'] = error

    player_args = deep_get(top_level, 'player', 'args', default={})
    player_response = json.loads(player_args['player_response']) if 'player_response' in player_args else {}

    # captions
    info['automatic_caption_languages'] = []
    info['manual_caption_languages'] = []
    info['_manual_caption_language_names'] = {}     # language name written in that language, needed in some cases to create the url
    info['translation_languages'] = []
    captions_info = player_response.get('captions', {})
    info['_captions_base_url'] = normalize_url(deep_get(captions_info, 'playerCaptionsRenderer', 'baseUrl'))
    for caption_track in deep_get(captions_info, 'playerCaptionsTracklistRenderer', 'captionTracks', default=()):
        lang_code = caption_track.get('languageCode')
        if not lang_code:
            continue
        if caption_track.get('kind') == 'asr':
            info['automatic_caption_languages'].append(lang_code)
        else:
            info['manual_caption_languages'].append(lang_code)
        base_url = caption_track.get('baseUrl', '')
        lang_name = deep_get(urllib.parse.parse_qs(urllib.parse.urlparse(base_url).query), 'name', 0)
        if lang_name:
            info['_manual_caption_language_names'][lang_code] = lang_name

    for translation_lang_info in deep_get(captions_info, 'playerCaptionsTracklistRenderer', 'translationLanguages', default=()):
        lang_code = translation_lang_info.get('languageCode')
        if lang_code:
            info['translation_languages'].append(lang_code)
        if translation_lang_info.get('isTranslatable') == False:
            print('WARNING: Found non-translatable caption language')

    # formats
    extract_formats(info, player_response)

    # playability errors
    extract_playability_error(info, player_response)

    # check age-restriction
    info['age_restricted'] = (info['playability_status'] == 'LOGIN_REQUIRED' and info['playability_error'] and ' age' in info['playability_error'])

    # base_js (for decryption of signatures)
    info['base_js'] = deep_get(top_level, 'player', 'assets', 'js')
    if info['base_js']:
        info['base_js'] = normalize_url(info['base_js'])

    mobile = 'singleColumnWatchNextResults' in deep_get(top_level, 'response', 'contents', default={})
    if mobile:
        info.update(extract_watch_info_mobile(top_level))
    else:
        info.update(extract_watch_info_desktop(top_level))

    # stuff from videoDetails. Use liberal_update to prioritize info from videoDetails over existing info
    vd = deep_get(top_level, 'playerResponse', 'videoDetails', default={})
    liberal_update(info, 'title',      extract_str(vd.get('title')))
    liberal_update(info, 'duration',   extract_int(vd.get('lengthSeconds')))
    liberal_update(info, 'view_count', extract_int(vd.get('viewCount')))
    # videos with no description have a blank string
    liberal_update(info, 'description', vd.get('shortDescription'))
    liberal_update(info, 'id',          vd.get('videoId'))
    liberal_update(info, 'author',      vd.get('author'))
    liberal_update(info, 'author_id',   vd.get('channelId'))
    liberal_update(info, 'live',        vd.get('isLiveContent'))
    conservative_update(info, 'unlisted', not vd.get('isCrawlable', True))  #isCrawlable is false on limited state videos even if they aren't unlisted
    liberal_update(info, 'tags',        vd.get('keywords', []))

    # fallback stuff from microformat
    mf = deep_get(top_level, 'playerResponse', 'microformat', 'playerMicroformatRenderer', default={})
    conservative_update(info, 'title',      extract_str(mf.get('title')))
    conservative_update(info, 'duration', extract_int(mf.get('lengthSeconds')))
    # this gives the view count for limited state videos
    conservative_update(info, 'view_count', extract_int(mf.get('viewCount')))
    conservative_update(info, 'description', extract_str(mf.get('description'), recover_urls=True))
    conservative_update(info, 'author', mf.get('ownerChannelName'))
    conservative_update(info, 'author_id', mf.get('externalChannelId'))
    liberal_update(info, 'unlisted', mf.get('isUnlisted'))
    liberal_update(info, 'category', mf.get('category'))
    liberal_update(info, 'time_published', mf.get('publishDate'))
    liberal_update(info, 'time_uploaded', mf.get('uploadDate'))

    # other stuff
    info['author_url'] = 'https://www.youtube.com/channel/' + info['author_id'] if info['author_id'] else None
    return info

def update_with_age_restricted_info(info, video_info_page):
    ERROR_PREFIX = 'Error bypassing age-restriction: '

    video_info = urllib.parse.parse_qs(video_info_page)
    player_response = deep_get(video_info, 'player_response', 0)
    if player_response is None:
        info['playability_error'] = ERROR_PREFIX + 'Could not find player_response in video_info_page'
        return
    try:
        player_response = json.loads(player_response)
    except json.decoder.JSONDecodeError:
        traceback.print_exc()
        info['playability_error'] = ERROR_PREFIX + 'Failed to parse json response'
        return

    extract_formats(info, player_response)
    extract_playability_error(info, player_response, error_prefix=ERROR_PREFIX)
