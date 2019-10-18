from youtube import util, proto

import html
import json
import re
import urllib
import collections
from math import ceil
import traceback

# videos (all of type str):

# id
# title
# url
# author
# author_url
# thumbnail
# description
# published
# duration
# likes
# dislikes
# views
# playlist_index

# playlists:

# id
# title
# url
# author
# author_url
# thumbnail
# description
# updated
# size
# first_video_id

# from https://github.com/ytdl-org/youtube-dl/blob/master/youtube_dl/extractor/youtube.py
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
    '82': {'ext': 'mp4', 'height': 360, 'format_note': '3D', 'acodec': 'aac', 'abr': 128, 'vcodec': 'h264'},
    '83': {'ext': 'mp4', 'height': 480, 'format_note': '3D', 'acodec': 'aac', 'abr': 128, 'vcodec': 'h264'},
    '84': {'ext': 'mp4', 'height': 720, 'format_note': '3D', 'acodec': 'aac', 'abr': 192, 'vcodec': 'h264'},
    '85': {'ext': 'mp4', 'height': 1080, 'format_note': '3D', 'acodec': 'aac', 'abr': 192, 'vcodec': 'h264'},
    '100': {'ext': 'webm', 'height': 360, 'format_note': '3D', 'acodec': 'vorbis', 'abr': 128, 'vcodec': 'vp8'},
    '101': {'ext': 'webm', 'height': 480, 'format_note': '3D', 'acodec': 'vorbis', 'abr': 192, 'vcodec': 'vp8'},
    '102': {'ext': 'webm', 'height': 720, 'format_note': '3D', 'acodec': 'vorbis', 'abr': 192, 'vcodec': 'vp8'},

    # Apple HTTP Live Streaming
    '91': {'ext': 'mp4', 'height': 144, 'format_note': 'HLS', 'acodec': 'aac', 'abr': 48, 'vcodec': 'h264'},
    '92': {'ext': 'mp4', 'height': 240, 'format_note': 'HLS', 'acodec': 'aac', 'abr': 48, 'vcodec': 'h264'},
    '93': {'ext': 'mp4', 'height': 360, 'format_note': 'HLS', 'acodec': 'aac', 'abr': 128, 'vcodec': 'h264'},
    '94': {'ext': 'mp4', 'height': 480, 'format_note': 'HLS', 'acodec': 'aac', 'abr': 128, 'vcodec': 'h264'},
    '95': {'ext': 'mp4', 'height': 720, 'format_note': 'HLS', 'acodec': 'aac', 'abr': 256, 'vcodec': 'h264'},
    '96': {'ext': 'mp4', 'height': 1080, 'format_note': 'HLS', 'acodec': 'aac', 'abr': 256, 'vcodec': 'h264'},
    '132': {'ext': 'mp4', 'height': 240, 'format_note': 'HLS', 'acodec': 'aac', 'abr': 48, 'vcodec': 'h264'},
    '151': {'ext': 'mp4', 'height': 72, 'format_note': 'HLS', 'acodec': 'aac', 'abr': 24, 'vcodec': 'h264'},

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

    # av01 video only formats sometimes served with "unknown" codecs
    '394': {'vcodec': 'av01.0.05M.08'},
    '395': {'vcodec': 'av01.0.05M.08'},
    '396': {'vcodec': 'av01.0.05M.08'},
    '397': {'vcodec': 'av01.0.05M.08'},
}


def get_plain_text(node):
    try:
        return node['simpleText']
    except KeyError:
        return ''.join(text_run['text'] for text_run in node['runs'])

def format_text_runs(runs):
    if isinstance(runs, str):
        return runs
    result = ''
    for text_run in runs:
        if text_run.get("bold", False):
            result += "<b>" + html.escape(text_run["text"]) + "</b>"
        elif text_run.get('italics', False):
            result += "<i>" + html.escape(text_run["text"]) + "</i>"
        else:
            result += html.escape(text_run["text"])
    return result

def default_get(object, key, default=None, types=()):
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



def default_multi_get(object, *keys, default=None, types=()):
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

def multi_default_multi_get(object, *key_sequences, default=None, types=()):
    '''Like default_multi_get, but can try different key sequences in case one fails.
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

def remove_redirect(url):
    if re.fullmatch(r'(((https?:)?//)?(www.)?youtube.com)?/redirect\?.*', url) is not None: # youtube puts these on external links to do tracking
        query_string = url[url.find('?')+1: ]
        return urllib.parse.parse_qs(query_string)['q'][0]
    return url

def get_url(node):
    try:
        return node['runs'][0]['navigationEndpoint']['commandMetadata']['webCommandMetadata']['url']
    except KeyError:
        return node['navigationEndpoint']['commandMetadata']['webCommandMetadata']['url']


def get_text(node):
    if node == {}:
        return ''
    try:
        return node['simpleText']
    except KeyError:
        pass
    try:
        return node['runs'][0]['text']
    except IndexError: # empty text runs
        return ''
    except KeyError:
        print(node)
        raise

def get_formatted_text(node):
    try:
        return node['runs']
    except KeyError:
        return node['simpleText']

def get_badges(node):
    badges = []
    for badge_node in node:
        badge = badge_node['metadataBadgeRenderer']['label']
        badges.append(badge)
    return badges

def get_thumbnail(node):
    try:
        return node['thumbnails'][0]['url']     # polymer format
    except KeyError:
        return node['url']     # ajax format

dispatch = {

# polymer format    
    'title':                ('title',       get_text),
    'publishedTimeText':    ('published',   get_text),
    'videoId':              ('id',          lambda node: node),
    'descriptionSnippet':   ('description', get_formatted_text),
    'lengthText':           ('duration',    get_text),
    'thumbnail':            ('thumbnail',   get_thumbnail),
    'thumbnails':           ('thumbnail',   lambda node: node[0]['thumbnails'][0]['url']),

    'viewCountText':        ('views',       get_text),
    'numVideosText':        ('size',        lambda node: get_text(node).split(' ')[0]),     # the format is "324 videos"
    'videoCountText':       ('size',        get_text),
    'playlistId':           ('id',          lambda node: node),
    'descriptionText':      ('description', get_formatted_text),

    'subscriberCountText':  ('subscriber_count',    get_text),
    'channelId':            ('id',          lambda node: node),
    'badges':               ('badges',      get_badges),

# ajax format
    'view_count_text':  ('views',       get_text),
    'num_videos_text':  ('size',        lambda node: get_text(node).split(' ')[0]),
    'owner_text':       ('author',      get_text),
    'owner_endpoint':   ('author_url',  lambda node: node['url']),
    'description':      ('description', get_formatted_text),
    'index':            ('playlist_index', get_text),
    'short_byline':     ('author',      get_text),
    'length':           ('duration',    get_text),
    'video_id':         ('id',          lambda node: node),

}

def ajax_info(item_json):
    try:
        info = {}          
        for key, node in item_json.items():
            try:
                simple_key, function = dispatch[key]
            except KeyError:
                continue
            info[simple_key] = function(node)
        return info
    except KeyError:
        print(item_json)
        raise


youtube_url_re = re.compile(r'^(?:(?:(?:https?:)?//)?(?:www\.)?youtube\.com)?(/.*)$')
def normalize_url(url):
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
        item['url'] = util.URL_ORIGIN + '/watch?v=' + item['id']

        video_info = {}
        for key in ('id', 'title', 'author', 'duration'):
            try:
                video_info[key] = item[key]
            except KeyError:
                video_info[key] = ''

        item['video_info'] = json.dumps(video_info)

    elif item['type'] == 'playlist':
        item['url'] = util.URL_ORIGIN + '/playlist?list=' + item['id']
    elif item['type'] == 'channel':
        item['url'] = util.URL_ORIGIN + "/channel/" + item['id']


def renderer_info(renderer, additional_info={}):
    type = list(renderer.keys())[0]
    renderer = renderer[type]
    info = {}
    if type in ('itemSectionRenderer', 'compactAutoplayRenderer'):
        return renderer_info(renderer['contents'][0], additional_info)

    if type in ('movieRenderer', 'clarificationRenderer'):
        info['type'] = 'unsupported'
        return info

    info.update(additional_info)


    if type in ('compactVideoRenderer', 'videoRenderer', 'playlistVideoRenderer', 'gridVideoRenderer'):
        info['type'] = 'video'
    elif type in ('playlistRenderer', 'compactPlaylistRenderer', 'gridPlaylistRenderer',
                  'radioRenderer', 'compactRadioRenderer', 'gridRadioRenderer',
                  'showRenderer', 'compactShowRenderer', 'gridShowRenderer'):
        info['type'] = 'playlist'
    elif type == 'channelRenderer':
        info['type'] = 'channel'
    elif type == 'playlistHeaderRenderer':
        info['type'] = 'playlist_metadata'
    else:
        info['type'] = 'unsupported'
        return info

    try:
        if 'viewCountText' in renderer:     # prefer this one as it contains all the digits
            info['views'] = get_text(renderer['viewCountText'])
        elif 'shortViewCountText' in renderer:
            info['views'] = get_text(renderer['shortViewCountText'])

        if 'ownerText' in renderer:
            info['author'] = renderer['ownerText']['runs'][0]['text']
            info['author_url'] = normalize_url(renderer['ownerText']['runs'][0]['navigationEndpoint']['commandMetadata']['webCommandMetadata']['url'])
        try:
            overlays = renderer['thumbnailOverlays']
        except KeyError:
            pass
        else:
            for overlay in overlays:
                if 'thumbnailOverlayTimeStatusRenderer' in overlay:
                    info['duration'] = get_text(overlay['thumbnailOverlayTimeStatusRenderer']['text'])
                # show renderers don't have videoCountText
                elif 'thumbnailOverlayBottomPanelRenderer' in overlay:
                    info['size'] = get_text(overlay['thumbnailOverlayBottomPanelRenderer']['text'])

        # show renderers don't have playlistId, have to dig into the url to get it
        try:
            info['id'] = renderer['navigationEndpoint']['watchEndpoint']['playlistId']
        except KeyError:
            pass
        for key, node in renderer.items():
            if key in ('longBylineText', 'shortBylineText'):
                info['author'] = get_text(node)
                try:
                    info['author_url'] = normalize_url(get_url(node))
                except KeyError:
                    pass

            # show renderers don't have thumbnail key at top level, dig into thumbnailRenderer
            elif key == 'thumbnailRenderer' and 'showCustomThumbnailRenderer' in node:
                info['thumbnail'] = node['showCustomThumbnailRenderer']['thumbnail']['thumbnails'][0]['url']
            else:
                try:
                    simple_key, function = dispatch[key]
                except KeyError:
                    continue
                info[simple_key] = function(node)
        if info['type'] == 'video' and 'duration' not in info:
            info['duration'] = 'Live'

        return info
    except KeyError:
        print(renderer)
        raise


def parse_info_prepare_for_html(renderer, additional_info={}):
    item = renderer_info(renderer, additional_info)
    prefix_urls(item)
    add_extra_html_info(item)

    return item

def extract_response(polymer_json):
    '''return response, error'''
    response = multi_default_multi_get(polymer_json, [1, 'response'], ['response'], default=None, types=dict)
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
    for tab in default_get(renderer, 'tabs', (), types=(list, tuple)):
        tab_renderer = multi_default_multi_get(tab, ['tabRenderer'], ['expandableTabRenderer'], default=None, types=dict)
        if tab_renderer is None:
            continue
        if tab_renderer.get('selected', False):
            return default_get(tab_renderer, 'content', {}, types=(dict))
    print('Could not find tab with content')
    return {}

def traverse_standard_list(renderer):
    renderer_list = multi_default_multi_get(renderer, ['contents'], ['items'], default=(), types=(list, tuple))
    continuation = default_multi_get(renderer, 'continuations', 0, 'nextContinuationData', 'continuation')
    return renderer_list, continuation

# these renderers contain one inside them
nested_renderer_dispatch = {
    'singleColumnBrowseResultsRenderer': traverse_browse_renderer,
    'twoColumnBrowseResultsRenderer': traverse_browse_renderer,
    'twoColumnSearchResultsRenderer': lambda renderer: default_get(renderer, 'primaryContents', {}, types=dict),
}

# these renderers contain a list of renderers in side them
nested_renderer_list_dispatch = {
    'sectionListRenderer': traverse_standard_list,
    'itemSectionRenderer': traverse_standard_list,
    'gridRenderer': traverse_standard_list,
    'playlistVideoListRenderer': traverse_standard_list,
    'singleColumnWatchNextResults': lambda r: (default_multi_get(r, 'results', 'results', 'contents', default=[], types=(list, tuple)), None),
}

def extract_items(response, item_types=item_types):
    '''return items, ctoken'''
    if 'continuationContents' in response:
        # always has just the one [something]Continuation key, but do this just in case they add some tracking key or something
        for key, renderer_continuation in default_get(response, 'continuationContents', {}, types=dict).items():
            if key.endswith('Continuation'):    # e.g. commentSectionContinuation, playlistVideoListContinuation
                items = multi_default_multi_get(renderer_continuation, ['contents'], ['items'], default=None, types=(list, tuple))
                ctoken = default_multi_get(renderer_continuation, 'continuations', 0, 'nextContinuationData', 'continuation', default=None, types=str)
                return items, ctoken
        return [], None
    elif 'contents' in response:
        ctoken = None
        items = []

        iter_stack = collections.deque()
        current_iter = iter(())

        renderer = default_get(response, 'contents', {}, types=dict)

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
        info['items'] = [renderer_info(renderer, additional_info) for renderer in items]

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

            text = get_plain_text(link_json['title'])

            info['links'].append( (text, url) )


        info['stats'] = []
        for stat_name in ('subscriberCountText', 'joinedDateText', 'viewCountText', 'country'):
            try:
                stat = channel_metadata[stat_name]
            except KeyError:
                continue
            info['stats'].append(get_plain_text(stat))

        if 'description' in channel_metadata:
            info['description'] = get_text(channel_metadata['description'])
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

        item_info = renderer_info(renderer)
        if item_info['type'] != 'unsupported':
            info['items'].append(item_info)


    return info

def extract_playlist_metadata(polymer_json):
    response, err = extract_response(polymer_json)
    if err:
        return {'error': err}
    metadata = renderer_info(response['header'])
    metadata['error'] = None

    if 'description' not in metadata:
        metadata['description'] = ''

    metadata['size'] = int(metadata['size'].replace(',', ''))

    return metadata

def extract_playlist_info(polymer_json):
    response, err = extract_response(polymer_json)
    if err:
        return {'error': err}
    info = {'error': None}
    first_page = 'continuationContents' not in response
    video_list, _ = extract_items(response)

    info['items'] = [renderer_info(renderer) for renderer in video_list]

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
                    view_replies_text = get_plain_text(comment_thread['replies']['commentRepliesRenderer']['moreText'])
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
                'likes': comment_renderer['likeCount'],
                'published': get_plain_text(comment_renderer['publishedTimeText']),
                'text': comment_renderer['contentText'].get('runs', ''),
                'number_of_replies': number_of_replies,
                'comment_id': comment_renderer['commentId'],
            }

            if 'authorText' in comment_renderer:     # deleted channels have no name or channel link
                comment['author'] = get_plain_text(comment_renderer['authorText'])
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
                _object = object[key]
        except (KeyError, IndexError, TypeError):
            return 'Could not find ' + key

    return None

def extract_plain_text(node, default=None):
    if isinstance(node, str):
        return node

    try:
        return node['simpleText']
    except (KeyError, TypeError):
        pass

    try:
        return ''.join(text_run['text'] for text_run in node['runs'])
    except (KeyError, TypeError):
        pass

    return default

def extract_formatted_text(node):
    try:
        result = []
        runs = node['runs']
        for run in runs:
            url = default_multi_get(run, 'navigationEndpoint', 'urlEndpoint', 'url')
            if url is not None:
                run['url'] = remove_redirect(url)
                run['text'] = run['url'] # youtube truncates the url text, we don't want that nonsense
        return runs
    except (KeyError, TypeError):
        traceback.print_exc()
        pass

    try:
        return [{'text': node['simpleText']}]
    except (KeyError, TypeError):
        pass

    return []

def extract_integer(string):
    if not isinstance(string, str):
        return None
    match = re.search(r'(\d+)', string.replace(',', ''))
    if match is None:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None

def extract_metadata_row_info(video_renderer_info):
    # extract category and music list
    info = {
        'category': None,
        'music_list': [],
    }

    current_song = {}
    for row in default_multi_get(video_renderer_info, 'metadataRowContainer', 'metadataRowContainerRenderer', 'rows', default=[]):
        row_title = extract_plain_text(default_multi_get(row, 'metadataRowRenderer', 'title'), default='')
        row_content = extract_plain_text(default_multi_get(row, 'metadataRowRenderer', 'contents', 0))
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


def extract_watch_info_mobile(top_level):
    info = {}
    microformat = default_multi_get(top_level, 'playerResponse', 'microformat', 'playerMicroformatRenderer', default={})

    info['allowed_countries'] = microformat.get('availableCountries', [])
    info['published_date'] = microformat.get('publishDate')

    response = top_level.get('response', {})

    # video info from metadata renderers
    items, _ = extract_items(response, item_types={'slimVideoMetadataRenderer'})
    if items:
        video_info = items[0]['slimVideoMetadataRenderer']
    else:
        print('Failed to extract video metadata')
        video_info = {}

    info.update(extract_metadata_row_info(video_info))
    #info['description'] = extract_formatted_text(video_info.get('description'))
    info['like_count'] = None
    info['dislike_count'] = None
    for button in video_info.get('buttons', ()):
        button_renderer = button.get('slimMetadataToggleButtonRenderer', {})

        # all the digits can be found in the accessibility data
        count = extract_integer(default_multi_get(button_renderer, 'button', 'toggleButtonRenderer', 'defaultText', 'accessibility', 'accessibilityData', 'label'))

        # this count doesn't have all the digits, it's like 53K for instance
        dumb_count = extract_integer(extract_plain_text(default_multi_get(button_renderer, 'button', 'toggleButtonRenderer', 'defaultText')))

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
        comment_count_text = extract_plain_text(default_multi_get(comment_info, 'header', 'commentSectionHeaderRenderer', 'countText'))
        if comment_count_text == 'Comments':    # just this with no number, means 0 comments
            info['comment_count'] = 0
        else:
            info['comment_count'] = extract_integer(comment_count_text)
        info['comments_disabled'] = False
    else:   # no comment section present means comments are disabled
        info['comment_count'] = 0
        info['comments_disabled'] = True

    # related videos
    related, _ = extract_items(response)
    info['related_videos'] = [renderer_info(renderer) for renderer in related]

    return info

month_abbreviations = {'jan':'1', 'feb':'2', 'mar':'3', 'apr':'4', 'may':'5', 'jun':'6', 'jul':'7', 'aug':'8', 'sep':'9', 'oct':'10', 'nov':'11', 'dec':'12'}
def extract_watch_info_desktop(top_level):
    info = {
        'comment_count': None,
        'comments_disabled': None,
        'allowed_countries': None,
    }

    video_info = {}
    for renderer in default_multi_get(top_level, 'response', 'contents', 'twoColumnWatchNextResults', 'results', 'results', 'contents', default=()):
        if renderer and list(renderer.keys())[0] in ('videoPrimaryInfoRenderer', 'videoSecondaryInfoRenderer'):
            video_info.update(list(renderer.values())[0])

    info.update(extract_metadata_row_info(video_info))
    #info['description'] = extract_formatted_text(video_info.get('description', None))
    info['published_date'] = None
    date_text = extract_plain_text(video_info.get('dateText', None))
    if date_text is not None:
        date_text = util.left_remove(date_text.lower(), 'published on ').replace(',', '')
        parts = date_text.split()
        if len(parts) == 3:
            month, day, year = date_text.split()
            month = month_abbreviations.get(month[0:3]) # slicing in case they start writing out the full month name
            if month and (re.fullmatch(r'\d\d?', day) is not None) and (re.fullmatch(r'\d{4}', year) is not None):
                info['published_date'] = year + '-' + month + '-' + day

    likes_dislikes = default_multi_get(video_info, 'sentimentBar', 'sentimentBarRenderer', 'tooltip', default='').split('/')
    if len(likes_dislikes) == 2:
        info['like_count'] = extract_integer(likes_dislikes[0])
        info['dislike_count'] = extract_integer(likes_dislikes[1])
    else:
        info['like_count'] = None
        info['dislike_count'] = None

    #info['title'] = extract_plain_text(video_info.get('title', None))
    #info['author'] = extract_plain_text(default_multi_get(video_info, 'owner', 'videoOwnerRenderer', 'title'))
    #info['author_id'] = default_multi_get(video_info, 'owner', 'videoOwnerRenderer', 'navigationEndpoint', 'browseEndpoint', 'browseId')
    #info['view_count'] = extract_integer(extract_plain_text(default_multi_get(video_info, 'viewCount', 'videoViewCountRenderer', 'viewCount')))

    related = default_multi_get(top_level, 'response', 'contents', 'twoColumnWatchNextResults', 'secondaryResults', 'secondaryResults', 'results', default=[])
    info['related_videos'] = [renderer_info(renderer) for renderer in related]

    return info


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
        ['playerResponse'],
    )
    if error:
        return {'error': error}

    error = check_missing_keys(top_level,
        ['player', 'args'],
        ['player', 'assets', 'js'],
    )
    if error:
        info['playability_error'] = error


    player_args = default_multi_get(top_level, 'player', 'args', default={})
    parsed_formats = []

    if 'url_encoded_fmt_stream_map' in player_args:
        string_formats = player_args['url_encoded_fmt_stream_map'].split(',')
        parsed_formats += [dict(urllib.parse.parse_qsl(fmt_string)) for fmt_string in string_formats if fmt_string]

    if 'adaptive_fmts' in player_args:
        string_formats = player_args['adaptive_fmts'].split(',')
        parsed_formats += [dict(urllib.parse.parse_qsl(fmt_string)) for fmt_string in string_formats if fmt_string]

    info['formats'] = []

    for parsed_fmt in parsed_formats:
        # start with defaults from the big table at the top
        if 'itag' in parsed_fmt:
            fmt = _formats.get(parsed_fmt['itag'], {}).copy()
        else:
            fmt = {}

        # then override them
        fmt.update(parsed_fmt)
        try:
            fmt['width'], fmt['height'] = map(int, fmt['size'].split('x'))
        except (KeyError, ValueError, TypeError):
            pass

        fmt['file_size'] = None
        if 'clen' in fmt:
            fmt['file_size'] = int(fmt.get('clen'))
        else:
            match = re.search(r'&clen=(\d+)', fmt.get('url'))
            if match:
                fmt['file_size'] = int(match.group(1))
        info['formats'].append(fmt)

    info['base_js'] = default_multi_get(top_level, 'player', 'assets', 'js')
    if info['base_js']:
        info['base_js'] = normalize_url(info['base_js'])

    mobile = 'singleColumnWatchNextResults' in default_multi_get(top_level, 'response', 'contents', default={})
    if mobile:
        info.update(extract_watch_info_mobile(top_level))
    else:
        info.update(extract_watch_info_desktop(top_level))

    # stuff from videoDetails
    video_details = default_multi_get(top_level, 'playerResponse', 'videoDetails', default={})
    info['title'] =      extract_plain_text(video_details.get('title'))
    info['duration'] =   extract_integer(video_details.get('lengthSeconds'))
    info['view_count'] = extract_integer(video_details.get('viewCount'))
    # videos with no description have a blank string
    info['description'] = video_details.get('shortDescription')
    info['id'] =          video_details.get('videoId')
    info['author'] =      video_details.get('author')
    info['author_id'] =   video_details.get('channelId')
    info['live'] =        video_details.get('isLiveContent')
    info['unlisted'] = not video_details.get('isCrawlable', True)
    info['tags'] =        video_details.get('keywords', [])

    # other stuff
    info['author_url'] = 'https://www.youtube.com/channel/' + info['author_id'] if info['author_id'] else None
    info['subtitles'] = {}  # TODO

    return info
