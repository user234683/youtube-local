from youtube import util, proto

import html
import json
import re
import urllib
from math import ceil

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


def default_multi_get(object, *keys, default):
    ''' Like dict.get(), but for nested dictionaries/sequences, supporting keys or indices. Last argument is the default value to use in case of any IndexErrors or KeyErrors '''
    try:
        for key in keys:
            object = object[key]
        return object
    except (IndexError, KeyError):
        return default


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
    if type == 'itemSectionRenderer':
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

def get_response(polymer_json):
    '''return response, error'''

    # responses returned for desktop version
    try:
        return polymer_json[1]['response'], None
    except (TypeError, KeyError, IndexError):
        pass

    # responses returned for mobile version
    try:
        return polymer_json['response'], None
    except (TypeError, KeyError):
        pass

    return None, 'Failed to extract response'


def extract_channel_info(polymer_json, tab):
    response, err = get_response(polymer_json)
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


    # find the tab with content
    # example channel where tabs do not have definite index: https://www.youtube.com/channel/UC4gQ8i3FD7YbhOgqUkeQEJg
    # TODO: maybe use the 'selected' attribute for this?
    if 'continuationContents' not in response:
        tab_renderer = None
        tab_content = None
        for tab_json in response['contents']['twoColumnBrowseResultsRenderer']['tabs']:
            try:
                tab_renderer = tab_json['tabRenderer']
            except KeyError:
                tab_renderer = tab_json['expandableTabRenderer']
            try:
                tab_content = tab_renderer['content']
                break
            except KeyError:
                pass
        else:   # didn't break
            raise Exception("No tabs found with content")
        assert tab == tab_renderer['title'].lower()


    # extract tab-specific info
    if tab in ('videos', 'playlists', 'search'):    # find the list of items
        if 'continuationContents' in response:
            try:
                items = response['continuationContents']['gridContinuation']['items']
            except KeyError:
                items = response['continuationContents']['sectionListContinuation']['contents']     # for search
        else:
            contents = tab_content['sectionListRenderer']['contents']
            if 'itemSectionRenderer' in contents[0]:
                item_section = contents[0]['itemSectionRenderer']['contents'][0]
                try:
                    items = item_section['gridRenderer']['items']
                except KeyError:
                    if "messageRenderer" in item_section:
                        items = []
                    else:
                        raise Exception('gridRenderer missing but messageRenderer not found')
            else:
                items = contents    # for search

        additional_info = {'author': info['channel_name'], 'author_url': 'https://www.youtube.com/channel/' + channel_id}
        info['items'] = [renderer_info(renderer, additional_info) for renderer in items]

    elif tab == 'about':
        channel_metadata = tab_content['sectionListRenderer']['contents'][0]['itemSectionRenderer']['contents'][0]['channelAboutFullMetadataRenderer']


        info['links'] = []
        for link_json in channel_metadata.get('primaryLinks', ()):
            url = link_json['navigationEndpoint']['urlEndpoint']['url']
            if url.startswith('/redirect'):     # youtube puts these on external links to do tracking
                query_string = url[url.find('?')+1: ]
                url = urllib.parse.parse_qs(query_string)['q'][0]

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
    response, err = get_response(polymer_json)
    if err:
        return {'error': err}
    info = {'error': None}
    info['estimated_results'] = int(response['estimatedResults'])
    info['estimated_pages'] = ceil(info['estimated_results']/20)

    # almost always is the first "section", but if there's an advertisement for a google product like Stadia or Home in the search results, then that becomes the first "section" and the search results are in the second. So just join all of them for resiliency
    results = []
    for section in response['contents']['twoColumnSearchResultsRenderer']['primaryContents']['sectionListRenderer']['contents']:
        results += section['itemSectionRenderer']['contents']

    info['items'] = []
    info['corrections'] = {'type': None}
    for renderer in results:
        type = list(renderer.keys())[0]
        if type == 'shelfRenderer':
            continue
        if type == 'didYouMeanRenderer':
            renderer = renderer[type]
            corrected_query_string = request.args.to_dict(flat=False)
            corrected_query_string['query'] = [renderer['correctedQueryEndpoint']['searchEndpoint']['query']]
            corrected_query_url = util.URL_ORIGIN + '/search?' + urllib.parse.urlencode(corrected_query_string, doseq=True)

            info['corrections'] = {
                'type': 'did_you_mean',
                'corrected_query': yt_data_extract.format_text_runs(renderer['correctedQuery']['runs']),
                'corrected_query_url': corrected_query_url,
            }
            continue
        if type == 'showingResultsForRenderer':
            renderer = renderer[type]
            no_autocorrect_query_string = request.args.to_dict(flat=False)
            no_autocorrect_query_string['autocorrect'] = ['0']
            no_autocorrect_query_url = util.URL_ORIGIN + '/search?' + urllib.parse.urlencode(no_autocorrect_query_string, doseq=True)

            info['corrections'] = {
                'type': 'showing_results_for',
                'corrected_query': yt_data_extract.format_text_runs(renderer['correctedQuery']['runs']),
                'original_query_url': no_autocorrect_query_url,
                'original_query': renderer['originalQuery']['simpleText'],
            }
            continue

        item_info = renderer_info(renderer)
        if item_info['type'] != 'unsupported':
            info['items'].append(item_info)


    return info

def extract_playlist_metadata(polymer_json):
    response, err = get_response(polymer_json)
    if err:
        return {'error': err}
    metadata = renderer_info(response['header'])
    metadata['error'] = None

    if 'description' not in metadata:
        metadata['description'] = ''

    metadata['size'] = int(metadata['size'].replace(',', ''))

    return metadata

def extract_playlist_info(polymer_json):
    response, err = get_response(polymer_json)
    if err:
        return {'error': err}
    info = {'error': None}
    try:    # first page
        video_list = response['contents']['singleColumnBrowseResultsRenderer']['tabs'][0]['tabRenderer']['content']['sectionListRenderer']['contents'][0]['itemSectionRenderer']['contents'][0]['playlistVideoListRenderer']['contents']
        first_page = True
    except KeyError:    # other pages
        video_list = response['continuationContents']['playlistVideoListContinuation']['contents']
        first_page = False

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
        response, err = get_response(polymer_json)
        if err:
            raise Exception(err)

        try:
            url = polymer_json[1]['url']
        except (TypeError, IndexError, KeyError):
            url = polymer_json['url']

        ctoken = urllib.parse.parse_qs(url[url.find('?')+1:])['ctoken'][0]
        metadata = ctoken_metadata(ctoken)

        try:
            comments_raw = response['continuationContents']['commentSectionContinuation']['items']
        except KeyError:
            comments_raw = response['continuationContents']['commentRepliesContinuation']['contents']

        ctoken = default_multi_get(response, 'continuationContents', 'commentSectionContinuation', 'continuations', 0, 'nextContinuationData', 'continuation', default='')

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



