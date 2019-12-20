import re
import urllib.parse
import collections

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

youtube_url_re = re.compile(r'^(?:(?:(?:https?:)?//)?(?:www\.)?youtube\.com)?(/.*)$')
def normalize_url(url):
    if url is None:
        return None
    match = youtube_url_re.fullmatch(url)
    if match is None:
        raise Exception()

    return 'https://www.youtube.com' + match.group(1)

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

def extract_int(string, default=None):
    if isinstance(string, int):
        return string
    if not isinstance(string, str):
        string = extract_str(string)
    if not string:
        return default
    match = re.search(r'(\d+)', string.replace(',', ''))
    if match is None:
        return default
    try:
        return int(match.group(1))
    except ValueError:
        return default

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

def extract_date(date_text):
    '''Input: "Mar 9, 2019". Output: "2019-3-9"'''
    if date_text is None:
        return None

    date_text = date_text.replace(',', '').lower()
    parts = date_text.split()
    if len(parts) >= 3:
        month, day, year = parts[-3:]
        month = month_abbreviations.get(month[0:3]) # slicing in case they start writing out the full month name
        if month and (re.fullmatch(r'\d\d?', day) is not None) and (re.fullmatch(r'\d{4}', year) is not None):
            return year + '-' + month + '-' + day

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

# these renderers contain a list of renderers inside them
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
                items = multi_deep_get(renderer_continuation, ['contents'], ['items'], default=[], types=(list, tuple))
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
