import base64
from youtube import util, yt_data_extract, html_common, subscriptions

import http_errors
import urllib
import json
from string import Template
import youtube.proto as proto
import html
import math
import gevent
import re
import functools

with open("yt_channel_items_template.html", "r") as file:
    yt_channel_items_template = Template(file.read())

with open("yt_channel_about_template.html", "r") as file:
    yt_channel_about_template = Template(file.read())

'''continuation = Proto(
    Field('optional', 'continuation', 80226972, Proto(
        Field('optional', 'browse_id', 2, String),
        Field('optional', 'params', 3, Base64(Proto(
            Field('optional', 'channel_tab', 2, String),
            Field('optional', 'sort', 3, ENUM
            Field('optional', 'page', 15, String),
        )))
    ))
)'''    
    

'''channel_continuation = Proto(
    Field('optional', 'pointless_nest', 80226972, Proto(
        Field('optional', 'channel_id', 2, String),
        Field('optional', 'continuation_info', 3, Base64(Proto(
            Field('optional', 'channel_tab', 2, String),
            Field('optional', 'sort', 3, ENUM
            Field('optional', 'page', 15, String),
        )))
    ))
)'''

headers_1 = (
    ('Accept', '*/*'),
    ('Accept-Language', 'en-US,en;q=0.5'),
    ('X-YouTube-Client-Name', '1'),
    ('X-YouTube-Client-Version', '2.20180830'),
)
headers_pbj = (
    ('Accept', '*/*'),
    ('Accept-Language', 'en-US,en;q=0.5'),
    ('X-YouTube-Client-Name', '2'),
    ('X-YouTube-Client-Version', '2.20180830'),
)
# https://www.youtube.com/browse_ajax?action_continuation=1&direct_render=1&continuation=4qmFsgJAEhhVQzdVY3M0MkZaeTN1WXpqcnF6T0lIc3caJEVnWjJhV1JsYjNNZ0FEZ0JZQUZxQUhvQk1yZ0JBQSUzRCUzRA%3D%3D
# https://www.youtube.com/browse_ajax?ctoken=4qmFsgJAEhhVQzdVY3M0MkZaeTN1WXpqcnF6T0lIc3caJEVnWjJhV1JsYjNNZ0FEZ0JZQUZxQUhvQk1yZ0JBQSUzRCUzRA%3D%3D&continuation=4qmFsgJAEhhVQzdVY3M0MkZaeTN1WXpqcnF6T0lIc3caJEVnWjJhV1JsYjNNZ0FEZ0JZQUZxQUhvQk1yZ0JBQSUzRCUzRA%3D%3D&itct=CDsQybcCIhMIhZi1krTc2wIVjMicCh2HXQnhKJsc

# grid view: 4qmFsgJAEhhVQzdVY3M0MkZaeTN1WXpqcnF6T0lIc3caJEVnWjJhV1JsYjNNZ0FEZ0JZQUZxQUhvQk1yZ0JBQSUzRCUzRA
# list view: 4qmFsgJCEhhVQzdVY3M0MkZaeTN1WXpqcnF6T0lIc3caJkVnWjJhV1JsYjNNWUF5QUFNQUk0QVdBQmFnQjZBVEs0QVFBJTNE
# SORT:
# videos:
#    Popular - 1
#    Oldest - 2
#    Newest - 3
# playlists:
#    Oldest - 2
#    Newest - 3
#    Last video added - 4

# view:
# grid: 0 or 1
# list: 2
def channel_ctoken(channel_id, page, sort, tab, view=1):  
    
    tab = proto.string(2, tab )
    sort = proto.uint(3, int(sort))
    page = proto.string(15, str(page) )
    # example with shelves in videos tab: https://www.youtube.com/channel/UCNL1ZadSjHpjm4q9j2sVtOA/videos
    shelf_view = proto.uint(4, 0)
    view = proto.uint(6, int(view))
    continuation_info = proto.string( 3, proto.percent_b64encode(tab + view + sort + shelf_view + page) )
    
    channel_id = proto.string(2, channel_id )
    pointless_nest = proto.string(80226972, channel_id + continuation_info)

    return base64.urlsafe_b64encode(pointless_nest).decode('ascii')

def get_channel_tab(channel_id, page="1", sort=3, tab='videos', view=1):
    ctoken = channel_ctoken(channel_id, page, sort, tab, view).replace('=', '%3D')
    url = "https://www.youtube.com/browse_ajax?ctoken=" + ctoken

    print("Sending channel tab ajax request")
    content = util.fetch_url(url, util.desktop_ua + headers_1)
    print("Finished recieving channel tab response")

    '''with open('debug/channel_debug', 'wb') as f:
        f.write(content)'''
    info = json.loads(content)
    return info




def get_number_of_videos(channel_id):
    # Uploads playlist
    playlist_id = 'UU' + channel_id[2:]
    url = 'https://m.youtube.com/playlist?list=' + playlist_id + '&pbj=1'
    print("Getting number of videos")

    # Sometimes retrieving playlist info fails with 403 for no discernable reason
    try:
        response = util.fetch_url(url, util.mobile_ua + headers_pbj)
    except urllib.error.HTTPError as e:
        if e.code != 403:
            raise
        print("Couldn't retrieve number of videos")
        return 1000

    '''with open('debug/playlist_debug_metadata', 'wb') as f:
        f.write(response)'''
    response = response.decode('utf-8')
    print("Got response for number of videos")

    match = re.search(r'"numVideosText":\s*{\s*"runs":\s*\[{"text":\s*"([\d,]*) videos"', response)
    if match:
        return int(match.group(1).replace(',',''))
    else:
        return 0

@functools.lru_cache(maxsize=128)
def get_channel_id(username):
    # method that gives the smallest possible response at ~10 kb
    # needs to be as fast as possible
    url = 'https://m.youtube.com/user/' + username + '/about?ajax=1&disable_polymer=true'
    response = util.fetch_url(url, util.mobile_ua + headers_1).decode('utf-8')
    return re.search(r'"channel_id":\s*"([a-zA-Z0-9_-]*)"', response).group(1)

def grid_items_html(items, additional_info={}):
    result = '''            <nav class="item-grid">\n'''
    for item in items:
        result += html_common.renderer_html(item, additional_info)
    result += '''\n</nav>'''
    return result

def list_items_html(items, additional_info={}):
    result = '''                <nav class="item-list">'''
    for item in items:
        result += html_common.renderer_html(item, additional_info)
    result += '''\n</nav>'''
    return result

channel_tab_template = Template('''\n<a class="tab page-button"$href_attribute>$tab_name</a>''')
channel_search_template = Template('''
                <form class="channel-search" action="$action">
                    <input type="search" name="query" class="search-box" value="$search_box_value">
                    <button type="submit" value="Search" class="search-button">Search</button>
                </form>''')

tabs = ('Videos', 'Playlists', 'About')
def channel_tabs_html(channel_id, current_tab, search_box_value=''):
    result = ''
    for tab_name in tabs:
        if tab_name == current_tab:
            result += channel_tab_template.substitute(
                href_attribute = '',
                tab_name = tab_name,
            )
        else:
            result += channel_tab_template.substitute(
                href_attribute = ' href="' + util.URL_ORIGIN + '/channel/' + channel_id + '/' + tab_name.lower() + '"',
                tab_name = tab_name,
            )
    result += channel_search_template.substitute(
        action = util.URL_ORIGIN + "/channel/" + channel_id + "/search",
        search_box_value = html.escape(search_box_value),
    )
    return result

channel_sort_button_template = Template('''\n<a class="sort-button"$href_attribute>$text</a>''')
sorts = {
    "videos": (('1', 'views'), ('2', 'oldest'), ('3', 'newest'),),
    "playlists": (('2', 'oldest'), ('3', 'newest'), ('4', 'last video added'),),
}
def channel_sort_buttons_html(channel_id, tab, current_sort):
    result = ''
    for sort_number, sort_name in sorts[tab]:
        if sort_number == str(current_sort):
            result += channel_sort_button_template.substitute(
                href_attribute='',
                text = 'Sorted by ' + sort_name
            )
        else:
            result += channel_sort_button_template.substitute(
                href_attribute=' href="' + util.URL_ORIGIN + '/channel/' + channel_id + '/' + tab + '?sort=' + sort_number + '"',
                text = 'Sort by ' + sort_name
            )
    return result


def get_microformat(response):
    try:
        return response['microformat']['microformatDataRenderer']

    # channel doesn't exist or was terminated
    # example terminated channel: https://www.youtube.com/channel/UCnKJeK_r90jDdIuzHXC0Org
    except KeyError:
        if 'alerts' in response and len(response['alerts']) > 0:
            result = ''
            for alert in response['alerts']:
                result += alert['alertRenderer']['text']['simpleText'] + '\n'
            raise http_errors.Code200(result)
        elif 'errors' in response['responseContext']:
            for error in response['responseContext']['errors']['error']:
                if error['code'] == 'INVALID_VALUE' and error['location'] == 'browse_id':
                    raise http_errors.Error404('This channel does not exist')
        raise

# example channel with no videos: https://www.youtube.com/user/jungleace
def get_grid_items(response):
    try:
        return response['continuationContents']['gridContinuation']['items']
    except KeyError:
        try:
            contents = response['contents']
        except KeyError:
            return []

        item_section = tab_with_content(contents['twoColumnBrowseResultsRenderer']['tabs'])['sectionListRenderer']['contents'][0]['itemSectionRenderer']['contents'][0]
        try:
            return item_section['gridRenderer']['items']
        except KeyError:
            if "messageRenderer" in item_section:
                return []
            else:
                raise


def channel_videos_html(polymer_json, current_page=1, current_sort=3, number_of_videos = 1000, current_query_string=''):
    response = polymer_json[1]['response']
    microformat = get_microformat(response)
    channel_url = microformat['urlCanonical'].rstrip('/')
    channel_id = channel_url[channel_url.rfind('/')+1:]
    if subscriptions.is_subscribed(channel_id):
        action_name = 'Unsubscribe'
        action = 'unsubscribe'
    else:
        action_name = 'Subscribe'
        action = 'subscribe'

    items = get_grid_items(response)
    items_html = grid_items_html(items, {'author': microformat['title']})
    
    return yt_channel_items_template.substitute(
        header              = html_common.get_header(),
        channel_title       = microformat['title'],
        channel_id          = channel_id,
        channel_tabs        = channel_tabs_html(channel_id, 'Videos'),
        sort_buttons        = channel_sort_buttons_html(channel_id, 'videos', current_sort),
        avatar              = '/' + microformat['thumbnail']['thumbnails'][0]['url'],
        page_title          = microformat['title'] + ' - Channel',
        items               = items_html,
        page_buttons        = html_common.page_buttons_html(current_page, math.ceil(number_of_videos/30), util.URL_ORIGIN + "/channel/" + channel_id + "/videos", current_query_string),
        number_of_results   = '{:,}'.format(number_of_videos) + " videos",
        action_name = action_name,
        action = action,
    )

def channel_playlists_html(polymer_json, current_sort=3):
    response = polymer_json[1]['response']
    microformat = get_microformat(response)
    channel_url = microformat['urlCanonical'].rstrip('/')
    channel_id = channel_url[channel_url.rfind('/')+1:]

    if subscriptions.is_subscribed(channel_id):
        action_name = 'Unsubscribe'
        action = 'unsubscribe'
    else:
        action_name = 'Subscribe'
        action = 'subscribe'

    items = get_grid_items(response)
    items_html = grid_items_html(items, {'author': microformat['title']})
    
    return yt_channel_items_template.substitute(
        header              = html_common.get_header(),
        channel_title       = microformat['title'],
        channel_id          = channel_id,
        channel_tabs        = channel_tabs_html(channel_id, 'Playlists'),
        sort_buttons        = channel_sort_buttons_html(channel_id, 'playlists', current_sort),
        avatar              = '/' + microformat['thumbnail']['thumbnails'][0]['url'],
        page_title          = microformat['title'] + ' - Channel',
        items               = items_html,
        page_buttons        = '',
        number_of_results   = '',
        action_name = action_name,
        action = action,
    )

# Example channel where tabs do not have definite index: https://www.youtube.com/channel/UC4gQ8i3FD7YbhOgqUkeQEJg
def tab_with_content(tabs):
    for tab in tabs:
        try:
            renderer = tab['tabRenderer']
        except KeyError:
            renderer = tab['expandableTabRenderer']
        try:
            return renderer['content']
        except KeyError:
            pass

    raise Exception("No tabs found with content")

channel_link_template = Template('''
<li><a href="$url">$text</a></li>''')
stat_template = Template('''
<li>$stat_value</li>''')
def channel_about_page(polymer_json):
    microformat = get_microformat(polymer_json[1]['response'])
    avatar = '/' + microformat['thumbnail']['thumbnails'][0]['url']
    # my goodness...
    channel_metadata = tab_with_content(polymer_json[1]['response']['contents']['twoColumnBrowseResultsRenderer']['tabs'])['sectionListRenderer']['contents'][0]['itemSectionRenderer']['contents'][0]['channelAboutFullMetadataRenderer']
    channel_links = ''
    for link_json in channel_metadata.get('primaryLinks', ()):
        url = link_json['navigationEndpoint']['urlEndpoint']['url']
        if url.startswith("/redirect"):
            query_string = url[url.find('?')+1: ]
            url = urllib.parse.parse_qs(query_string)['q'][0]

        channel_links += channel_link_template.substitute(
            url     = html.escape(url),
            text    = yt_data_extract.get_plain_text(link_json['title']),
        )

    stats = ''
    for stat_name in ('subscriberCountText', 'joinedDateText', 'viewCountText', 'country'):
        try:
            stat_value = yt_data_extract.get_plain_text(channel_metadata[stat_name])
        except KeyError:
            continue
        else:
            stats += stat_template.substitute(stat_value=stat_value)


    channel_id = channel_metadata['channelId']
    if subscriptions.is_subscribed(channel_id):
        action_name = 'Unsubscribe'
        action = 'unsubscribe'
    else:
        action_name = 'Subscribe'
        action = 'subscribe'

    try:
        description = yt_data_extract.format_text_runs(yt_data_extract.get_formatted_text(channel_metadata['description']))
    except KeyError:
        description = ''
    return yt_channel_about_template.substitute(
        header              = html_common.get_header(),
        page_title          = yt_data_extract.get_plain_text(channel_metadata['title']) + ' - About',
        channel_title       = yt_data_extract.get_plain_text(channel_metadata['title']),
        avatar              = html.escape(avatar),
        description         = description,
        links               = channel_links,
        stats               = stats,
        channel_id          = channel_id,
        channel_tabs        = channel_tabs_html(channel_metadata['channelId'], 'About'),
        action_name = action_name,
        action = action,
    )

def channel_search_page(polymer_json, query, current_page=1, number_of_videos = 1000, current_query_string=''):
    response = polymer_json[1]['response']
    microformat = get_microformat(response)
    channel_url = microformat['urlCanonical'].rstrip('/')
    channel_id = channel_url[channel_url.rfind('/')+1:]

    if subscriptions.is_subscribed(channel_id):
        action_name = 'Unsubscribe'
        action = 'unsubscribe'
    else:
        action_name = 'Subscribe'
        action = 'subscribe'


    try:
        items = tab_with_content(response['contents']['twoColumnBrowseResultsRenderer']['tabs'])['sectionListRenderer']['contents']
    except KeyError:
        items = response['continuationContents']['sectionListContinuation']['contents']

    items_html = list_items_html(items)

    return yt_channel_items_template.substitute(
        header              = html_common.get_header(),
        channel_title       = html.escape(microformat['title']),
        channel_id          = channel_id,
        channel_tabs        = channel_tabs_html(channel_id, '', query),
        avatar              = '/' + microformat['thumbnail']['thumbnails'][0]['url'],
        page_title          = html.escape(query + ' - Channel search'),
        items               = items_html,
        page_buttons        = html_common.page_buttons_html(current_page, math.ceil(number_of_videos/29), util.URL_ORIGIN + "/channel/" + channel_id + "/search", current_query_string),
        number_of_results   = '',
        sort_buttons        = '',
        action_name = action_name,
        action = action,
    )
def get_channel_search_json(channel_id, query, page):
    params = proto.string(2, 'search') + proto.string(15, str(page))
    params = proto.percent_b64encode(params)
    ctoken = proto.string(2, channel_id) + proto.string(3, params) + proto.string(11, query)
    ctoken = base64.urlsafe_b64encode(proto.nested(80226972, ctoken)).decode('ascii')

    polymer_json = util.fetch_url("https://www.youtube.com/browse_ajax?ctoken=" + ctoken, util.desktop_ua + headers_1)
    '''with open('debug/channel_search_debug', 'wb') as f:
        f.write(polymer_json)'''
    polymer_json = json.loads(polymer_json)

    return polymer_json
    
playlist_sort_codes = {'2': "da", '3': "dd", '4': "lad"}
def get_channel_page(env, start_response):
    path_parts = env['path_parts']
    channel_id = path_parts[1]
    try:
        tab = path_parts[2]
    except IndexError:
        tab = 'videos'
    
    parameters = env['parameters']
    page_number = int(util.default_multi_get(parameters, 'page', 0, default='1'))
    sort = util.default_multi_get(parameters, 'sort', 0, default='3')
    view = util.default_multi_get(parameters, 'view', 0, default='1')
    query = util.default_multi_get(parameters, 'query', 0, default='')

    if tab == 'videos':
        tasks = (
            gevent.spawn(get_number_of_videos, channel_id ), 
            gevent.spawn(get_channel_tab, channel_id, page_number, sort, 'videos', view)
        )
        gevent.joinall(tasks)
        number_of_videos, polymer_json = tasks[0].value, tasks[1].value

        result = channel_videos_html(polymer_json, page_number, sort, number_of_videos, env['QUERY_STRING'])
    elif tab == 'about':
        polymer_json = util.fetch_url('https://www.youtube.com/channel/' + channel_id + '/about?pbj=1', util.desktop_ua + headers_1)
        polymer_json = json.loads(polymer_json)
        result = channel_about_page(polymer_json)
    elif tab == 'playlists':
        polymer_json = util.fetch_url('https://www.youtube.com/channel/' + channel_id + '/playlists?pbj=1&view=1&sort=' + playlist_sort_codes[sort], util.desktop_ua + headers_1)
        '''with open('debug/channel_playlists_debug', 'wb') as f:
            f.write(polymer_json)'''
        polymer_json = json.loads(polymer_json)
        result = channel_playlists_html(polymer_json, sort)
    elif tab == 'search':
        tasks = (
            gevent.spawn(get_number_of_videos, channel_id ), 
            gevent.spawn(get_channel_search_json, channel_id, query, page_number)
        )
        gevent.joinall(tasks)
        number_of_videos, polymer_json = tasks[0].value, tasks[1].value

        result = channel_search_page(polymer_json, query, page_number, number_of_videos, env['QUERY_STRING'])
    else:
        start_response('404 Not Found', [('Content-type', 'text/plain'),])
        return b'Unknown channel tab: ' + tab.encode('utf-8')

    start_response('200 OK', [('Content-type','text/html'),])
    return result.encode('utf-8')

# youtube.com/user/[username]/[page]
# youtube.com/c/[custom]/[page]
# youtube.com/[custom]/[page]
def get_channel_page_general_url(env, start_response):
    path_parts = env['path_parts']

    is_toplevel = not path_parts[0] in ('user', 'c')

    if len(path_parts) + int(is_toplevel) == 3:       # has /[page] after it
        page = path_parts[2]
        base_url = 'https://www.youtube.com/' + '/'.join(path_parts[0:-1])
    elif len(path_parts) + int(is_toplevel) == 2:     # does not have /[page] after it, use /videos by default
        page = 'videos'
        base_url = 'https://www.youtube.com/' + '/'.join(path_parts)
    else:
        start_response('404 Not Found', [('Content-type', 'text/plain'),])
        return b'Invalid channel url'

    if page == 'videos':
        polymer_json = util.fetch_url(base_url + '/videos?pbj=1&view=0', util.desktop_ua + headers_1)
        '''with open('debug/user_page_videos', 'wb') as f:
            f.write(polymer_json)'''
        polymer_json = json.loads(polymer_json)
        result = channel_videos_html(polymer_json)
    elif page == 'about':
        polymer_json = util.fetch_url(base_url + '/about?pbj=1', util.desktop_ua + headers_1)
        polymer_json = json.loads(polymer_json)
        result = channel_about_page(polymer_json)
    elif page == 'playlists':
        polymer_json = util.fetch_url(base_url+ '/playlists?pbj=1&view=1', util.desktop_ua + headers_1)
        polymer_json = json.loads(polymer_json)
        result = channel_playlists_html(polymer_json)
    elif page == 'search':
        raise NotImplementedError()
        '''polymer_json = util.fetch_url('https://www.youtube.com/user' + username +  '/search?pbj=1&' + query_string, util.desktop_ua + headers_1)
        polymer_json = json.loads(polymer_json)
        return channel_search_page('''
    else:
        start_response('404 Not Found', [('Content-type', 'text/plain'),])
        return b'Unknown channel page: ' + page.encode('utf-8')

    start_response('200 OK', [('Content-type','text/html'),])
    return result.encode('utf-8')
