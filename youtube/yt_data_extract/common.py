import re
import urllib.parse
import collections
import collections.abc

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


def _is_empty(value):
    '''Determines if value is None or an empty iterable, such as '' and []'''
    if value is None:
        return True
    elif isinstance(value, collections.abc.Iterable) and not value:
        return True
    return False


def liberal_update(obj, key, value):
    '''Updates obj[key] with value as long as value is not None or empty.
    Ensures obj[key] will at least get an empty value, however'''
    if (not _is_empty(value)) or (key not in obj):
        obj[key] = value

def conservative_update(obj, key, value):
    '''Only updates obj if it doesn't have key or obj[key] is None/empty'''
    if _is_empty(obj.get(key)):
        obj[key] = value


def liberal_dict_update(dict1, dict2):
    '''Update dict1 with keys from dict2 using liberal_update'''
    for key, value in dict2.items():
        liberal_update(dict1, key, value)


def conservative_dict_update(dict1, dict2):
    '''Update dict1 with keys from dict2 using conservative_update'''
    for key, value in dict2.items():
        conservative_update(dict1, key, value)


def concat_or_none(*strings):
    '''Concatenates strings. Returns None if any of the arguments are None'''
    result = ''
    for string in strings:
        if string is None:
            return None
        result += string
    return result

def remove_redirect(url):
    if url is None:
        return None
    if re.fullmatch(r'(((https?:)?//)?(www.)?youtube.com)?/redirect\?.*', url) is not None: # youtube puts these on external links to do tracking
        query_string = url[url.find('?')+1: ]
        return urllib.parse.parse_qs(query_string)['q'][0]
    return url

norm_url_re = re.compile(r'^(?:(?:https?:)?//)?((?:[\w-]+\.)+[\w-]+)?(/.*)$')
def normalize_url(url):
    '''Insert https, resolve relative paths for youtube.com, and put www. infront of youtube.com'''
    if url is None:
        return None
    match = norm_url_re.fullmatch(url)
    if match is None:
        raise Exception(url)

    domain = match.group(1) or 'www.youtube.com'
    if domain == 'youtube.com':
        domain = 'www.youtube.com'

    return 'https://' + domain + match.group(2)

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

def extract_int(string, default=None, whole_word=True):
    if isinstance(string, int):
        return string
    if not isinstance(string, str):
        string = extract_str(string)
    if not string:
        return default
    if whole_word:
        match = re.search(r'\b(\d+)\b', string.replace(',', ''))
    else:
        match = re.search(r'(\d+)', string.replace(',', ''))
    if match is None:
        return default
    try:
        return int(match.group(1))
    except ValueError:
        return default

def extract_approx_int(string):
    '''e.g. "15.1M" from "15.1M subscribers"'''
    if not isinstance(string, str):
        string = extract_str(string)
    if not string:
        return None
    match = re.search(r'\b(\d+(?:\.\d+)?[KMBTkmbt]?)\b', string.replace(',', ''))
    if match is None:
        return None
    return match.group(1)

MONTH_ABBREVIATIONS = {'jan':'1', 'feb':'2', 'mar':'3', 'apr':'4', 'may':'5', 'jun':'6', 'jul':'7', 'aug':'8', 'sep':'9', 'oct':'10', 'nov':'11', 'dec':'12'}
def extract_date(date_text):
    '''Input: "Mar 9, 2019". Output: "2019-3-9"'''
    if not isinstance(date_text, str):
        date_text = extract_str(date_text)
    if date_text is None:
        return None

    date_text = date_text.replace(',', '').lower()
    parts = date_text.split()
    if len(parts) >= 3:
        month, day, year = parts[-3:]
        month = MONTH_ABBREVIATIONS.get(month[0:3]) # slicing in case they start writing out the full month name
        if month and (re.fullmatch(r'\d\d?', day) is not None) and (re.fullmatch(r'\d{4}', year) is not None):
            return year + '-' + month + '-' + day
    return None

def check_missing_keys(object, *key_sequences):
    for key_sequence in key_sequences:
        _object = object
        try:
            for key in key_sequence:
                _object = _object[key]
        except (KeyError, IndexError, TypeError):
            return 'Could not find ' + key

    return None

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

    # type looks like e.g. 'compactVideoRenderer' or 'gridVideoRenderer'
    # camelCase split, https://stackoverflow.com/a/37697078
    type_parts = [s.lower() for s in re.sub(r'([A-Z][a-z]+)', r' \1', type).split()]
    if len(type_parts) < 2:
        info['type'] = 'unsupported'
        return
    primary_type = type_parts[-2]
    if primary_type == 'video':
        info['type'] = 'video'
    elif type_parts[0] == 'reel': # shorts
        info['type'] = 'video'
        primary_type = 'video'
    elif primary_type in ('playlist', 'radio', 'show'):
        info['type'] = 'playlist'
        info['playlist_type'] = primary_type
    elif primary_type == 'channel':
        info['type'] = 'channel'
    elif type == 'videoWithContextRenderer': # stupid exception
        info['type'] = 'video'
        primary_type = 'video'
    else:
        info['type'] = 'unsupported'

    # videoWithContextRenderer changes it to 'headline' just to be annoying
    info['title'] = extract_str(multi_get(item, 'title', 'headline'))
    if primary_type != 'channel':
        info['author'] = extract_str(multi_get(item, 'longBylineText', 'shortBylineText', 'ownerText'))
        info['author_id'] = extract_str(multi_deep_get(item,
            ['longBylineText', 'runs', 0, 'navigationEndpoint', 'browseEndpoint', 'browseId'],
            ['shortBylineText', 'runs', 0, 'navigationEndpoint', 'browseEndpoint', 'browseId'],
            ['ownerText', 'runs', 0, 'navigationEndpoint', 'browseEndpoint', 'browseId']
        ))
        info['author_url'] = ('https://www.youtube.com/channel/' + info['author_id']) if info['author_id'] else None
    info['description'] = extract_formatted_text(multi_deep_get(
        item,
        ['descriptionText'], ['descriptionSnippet'],
        ['detailedMetadataSnippets', 0, 'snippetText'],
    ))
    info['thumbnail'] = normalize_url(multi_deep_get(item,
        ['thumbnail', 'thumbnails', 0, 'url'],      # videos
        ['thumbnails', 0, 'thumbnails', 0, 'url'],  # playlists
        ['thumbnailRenderer', 'showCustomThumbnailRenderer', 'thumbnail', 'thumbnails', 0, 'url'], # shows
    ))

    info['badges'] = []
    for badge_node in multi_get(item, 'badges', 'ownerBadges', default=()):
        badge = deep_get(badge_node, 'metadataBadgeRenderer', 'label')
        if badge:
            info['badges'].append(badge)

    if primary_type in ('video', 'playlist'):
        info['time_published'] = None
        timestamp = re.search(r'(\d+ \w+ ago)',
            extract_str(item.get('publishedTimeText'), default=''))
        if timestamp:
            info['time_published'] = timestamp.group(1)

    if primary_type == 'video':
        info['id'] = multi_deep_get(item,
            ['videoId'],
            ['navigationEndpoint', 'watchEndpoint', 'videoId'],
            ['navigationEndpoint', 'reelWatchEndpoint', 'videoId'] # shorts
        )
        info['view_count'] = extract_int(item.get('viewCountText'))

        # dig into accessibility data to get view_count for videos marked as recommended, and to get time_published
        accessibility_label = multi_deep_get(item,
            ['title', 'accessibility', 'accessibilityData', 'label'],
            ['headline', 'accessibility', 'accessibilityData', 'label'],
            default='')
        timestamp = re.search(r'(\d+ \w+ ago)', accessibility_label)
        if timestamp:
            conservative_update(info, 'time_published', timestamp.group(1))
        view_count = re.search(r'(\d+) views', accessibility_label.replace(',', ''))
        if view_count:
            conservative_update(info, 'view_count', int(view_count.group(1)))

        if info['view_count']:
            info['approx_view_count'] = '{:,}'.format(info['view_count'])
        else:
            info['approx_view_count'] = extract_approx_int(multi_get(item,
                'shortViewCountText',
                'viewCountText' # shorts
            ))

        # handle case where it is "No views"
        if not info['approx_view_count']:
            if ('No views' in item.get('shortViewCountText', '')
                    or 'no views' in accessibility_label.lower()
                    or 'No views' in extract_str(item.get('viewCountText', '')) # shorts
            ):
                info['view_count'] = 0
                info['approx_view_count'] = '0'

        info['duration'] = extract_str(item.get('lengthText'))

        # dig into accessibility data to get duration for shorts
        accessibility_label = deep_get(item,
            'accessibility', 'accessibilityData', 'label',
            default='')
        duration = re.search(r'(\d+) (second|seconds|minute) - play video$',
                            accessibility_label)
        if duration:
            if duration.group(2) == 'minute':
                conservative_update(info, 'duration', '1:00')
            else:
                conservative_update(info,
                    'duration', '0:' + duration.group(1).zfill(2))

        # if it's an item in a playlist, get its index
        if 'index' in item: # url has wrong index on playlist page
            info['index'] = extract_int(item.get('index'))
        elif 'indexText' in item:
            # Current item in playlist has ▶ instead of the actual index, must
            # dig into url
            match = re.search(r'index=(\d+)', deep_get(item,
                'navigationEndpoint', 'commandMetadata', 'webCommandMetadata',
                'url', default=''))
            if match is None:   # worth a try then
                info['index'] = extract_int(item.get('indexText'))
            else:
                info['index'] = int(match.group(1))
        else:
            info['index'] = None

    elif primary_type in ('playlist', 'radio'):
        info['id'] = item.get('playlistId')
        info['video_count'] = extract_int(item.get('videoCount'))
        info['first_video_id'] = deep_get(item, 'navigationEndpoint',
                                          'watchEndpoint', 'videoId')
    elif primary_type == 'channel':
        info['id'] = item.get('channelId')
        info['approx_subscriber_count'] = extract_approx_int(item.get('subscriberCountText'))
    elif primary_type == 'show':
        info['id'] = deep_get(item, 'navigationEndpoint', 'watchEndpoint', 'playlistId')
        info['first_video_id'] = deep_get(item, 'navigationEndpoint',
                                          'watchEndpoint', 'videoId')

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

    info.update(additional_info)

    return info

def extract_response(polymer_json):
    '''return response, error'''
    # /youtubei/v1/browse endpoint returns response directly
    if isinstance(polymer_json, dict) and 'responseContext' in polymer_json:
        # this is the response
        return polymer_json, None

    response = multi_deep_get(polymer_json, [1, 'response'], ['response'])
    if response is None:
        return None, 'Failed to extract response'
    else:
        return response, None


_item_types = {
    'movieRenderer',
    'didYouMeanRenderer',
    'showingResultsForRenderer',

    'videoRenderer',
    'compactVideoRenderer',
    'compactAutoplayRenderer',
    'videoWithContextRenderer',
    'gridVideoRenderer',
    'playlistVideoRenderer',

    'reelItemRenderer',

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
}

def _traverse_browse_renderer(renderer):
    for tab in get(renderer, 'tabs', ()):
        tab_renderer = multi_get(tab, 'tabRenderer', 'expandableTabRenderer')
        if tab_renderer is None:
            continue
        if tab_renderer.get('selected', False):
            return get(tab_renderer, 'content', {})
    print('Could not find tab with content')
    return {}

def _traverse_standard_list(renderer):
    renderer_list = multi_get(renderer, 'contents', 'items', default=())
    continuation = deep_get(renderer, 'continuations', 0, 'nextContinuationData', 'continuation')
    return renderer_list, continuation

# these renderers contain one inside them
nested_renderer_dispatch = {
    'singleColumnBrowseResultsRenderer': _traverse_browse_renderer,
    'twoColumnBrowseResultsRenderer': _traverse_browse_renderer,
    'twoColumnSearchResultsRenderer': lambda r: get(r, 'primaryContents', {}),
    'richItemRenderer': lambda r: get(r, 'content', {}),
    'engagementPanelSectionListRenderer': lambda r: get(r, 'content', {}),
}

# these renderers contain a list of renderers inside them
nested_renderer_list_dispatch = {
    'sectionListRenderer': _traverse_standard_list,
    'itemSectionRenderer': _traverse_standard_list,
    'gridRenderer': _traverse_standard_list,
    'richGridRenderer': _traverse_standard_list,
    'playlistVideoListRenderer': _traverse_standard_list,
    'structuredDescriptionContentRenderer': _traverse_standard_list,
    'slimVideoMetadataSectionRenderer': _traverse_standard_list,
    'singleColumnWatchNextResults': lambda r: (deep_get(r, 'results', 'results', 'contents', default=[]), None),
}
def get_nested_renderer_list_function(key):
    if key in nested_renderer_list_dispatch:
        return nested_renderer_list_dispatch[key]
    elif key.endswith('Continuation'):
        return _traverse_standard_list
    return None

def extract_items_from_renderer(renderer, item_types=_item_types):
    ctoken = None
    items = []

    iter_stack = collections.deque()
    current_iter = iter(())

    while True:
        # mode 1: get a new renderer by iterating.
        # goes down the stack for an iterator if one has been exhausted
        if not renderer:
            try:
                renderer = current_iter.__next__()
            except StopIteration:
                try:
                    current_iter = iter_stack.pop()
                except IndexError:
                    return items, ctoken
            # Get new renderer or check that the one we got is good before
            # proceeding to mode 2
            continue


        # mode 2: dig into the current renderer
        key, value = list(renderer.items())[0]

        # the renderer is an item
        if key in item_types:
            items.append(renderer)

        # ctoken sometimes placed in these renderers, e.g. channel playlists
        elif key == 'continuationItemRenderer':
            cont = deep_get(
                value, 'continuationEndpoint', 'continuationCommand', 'token'
            )
            if cont:
                ctoken = cont

        # has a list in it, add it to the iter stack
        elif get_nested_renderer_list_function(key):
            renderer_list, cont = get_nested_renderer_list_function(key)(value)
            if renderer_list:
                iter_stack.append(current_iter)
                current_iter = iter(renderer_list)
                if cont:
                    ctoken = cont

        # new renderer nested inside this one
        elif key in nested_renderer_dispatch:
            renderer = nested_renderer_dispatch[key](value)
            continue    # don't reset renderer to None

        renderer = None


def extract_items_from_renderer_list(renderers, item_types=_item_types):
    '''Same as extract_items_from_renderer, but provide a list of renderers'''
    items = []
    ctoken = None
    for renderer in renderers:
        new_items, new_ctoken = extract_items_from_renderer(
            renderer,
            item_types=item_types)
        items += new_items
        # prioritize ctoken associated with items
        if (not ctoken) or (new_ctoken and new_items):
            ctoken = new_ctoken
    return items, ctoken


def extract_items(response, item_types=_item_types,
                  search_engagement_panels=False):
    '''return items, ctoken'''
    items = []
    ctoken = None
    if 'continuationContents' in response:
        # sometimes there's another, empty, junk [something]Continuation key
        # find real one
        for key, renderer_cont in get(response,
                'continuationContents', {}).items():
            # e.g. commentSectionContinuation, playlistVideoListContinuation
            if key.endswith('Continuation'):
                items, ctoken = extract_items_from_renderer(
                    {key: renderer_cont},
                    item_types=item_types)
                if items:
                    break
    elif ('onResponseReceivedEndpoints' in response
          or 'onResponseReceivedActions' in response):
        for endpoint in multi_get(response,
                                  'onResponseReceivedEndpoints',
                                  'onResponseReceivedActions',
                                  []):
            items, ctoken = extract_items_from_renderer_list(
                multi_deep_get(
                    endpoint,
                    ['reloadContinuationItemsCommand', 'continuationItems'],
                    ['appendContinuationItemsAction', 'continuationItems'],
                    default=[]
                ),
                item_types=item_types,
            )
            if items:
                break
    elif 'contents' in response:
        renderer = get(response, 'contents', {})
        items, ctoken = extract_items_from_renderer(
            renderer,
            item_types=item_types)

    if search_engagement_panels and 'engagementPanels' in response:
        new_items, new_ctoken = extract_items_from_renderer_list(
            response['engagementPanels'], item_types=item_types
        )
        items += new_items
        if (not ctoken) or (new_ctoken and new_items):
            ctoken = new_ctoken

    return items, ctoken
