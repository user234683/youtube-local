from youtube import util

import html
import json

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
        if badge.lower() != 'new':
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



def prefix_urls(item):
    try:
        item['thumbnail'] = '/' + item['thumbnail'].lstrip('/')
    except KeyError:
        pass

    try:
        item['author_url'] = util.URL_ORIGIN + item['author_url']
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
    if type == 'itemSectionRenderer':
        return renderer_info(renderer['contents'][0], additional_info)
    
    if type in ('movieRenderer', 'clarificationRenderer'):
        info['type'] = 'unsupported'
        return info

    info.update(additional_info)

    if type.startswith('compact') or type.startswith('playlist'):
        info['item_size'] = 'small'
    else:
        info['item_size'] = 'medium'

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
            info['author_url'] = renderer['ownerText']['runs'][0]['navigationEndpoint']['commandMetadata']['webCommandMetadata']['url']
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
                    info['author_url'] = get_url(node)
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


