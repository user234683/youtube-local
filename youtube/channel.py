import base64
import youtube.common as common
from youtube.common import default_multi_get, URL_ORIGIN, get_thumbnail_url, video_id
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
    ('X-YouTube-Client-Version', '2.20180614'),
)
# https://www.youtube.com/browse_ajax?action_continuation=1&direct_render=1&continuation=4qmFsgJAEhhVQzdVY3M0MkZaeTN1WXpqcnF6T0lIc3caJEVnWjJhV1JsYjNNZ0FEZ0JZQUZxQUhvQk1yZ0JBQSUzRCUzRA%3D%3D
# https://www.youtube.com/browse_ajax?ctoken=4qmFsgJAEhhVQzdVY3M0MkZaeTN1WXpqcnF6T0lIc3caJEVnWjJhV1JsYjNNZ0FEZ0JZQUZxQUhvQk1yZ0JBQSUzRCUzRA%3D%3D&continuation=4qmFsgJAEhhVQzdVY3M0MkZaeTN1WXpqcnF6T0lIc3caJEVnWjJhV1JsYjNNZ0FEZ0JZQUZxQUhvQk1yZ0JBQSUzRCUzRA%3D%3D&itct=CDsQybcCIhMIhZi1krTc2wIVjMicCh2HXQnhKJsc

# grid view: 4qmFsgJAEhhVQzdVY3M0MkZaeTN1WXpqcnF6T0lIc3caJEVnWjJhV1JsYjNNZ0FEZ0JZQUZxQUhvQk1yZ0JBQSUzRCUzRA
# list view: 4qmFsgJCEhhVQzdVY3M0MkZaeTN1WXpqcnF6T0lIc3caJkVnWjJhV1JsYjNNWUF5QUFNQUk0QVdBQmFnQjZBVEs0QVFBJTNE
# SORT:
# Popular - 1
# Oldest - 2
# Newest - 3

# view:
# grid: 0 or 1
# list: 2
def channel_ctoken(channel_id, page, sort, tab, view=1):  
    
    tab = proto.string(2, tab )
    sort = proto.uint(3, int(sort))
    page = proto.string(15, str(page) )
    view = proto.uint(6, int(view))
    continuation_info = proto.string( 3, proto.percent_b64encode(tab + view + sort + page) )
    
    channel_id = proto.string(2, channel_id )
    pointless_nest = proto.string(80226972, channel_id + continuation_info)

    return base64.urlsafe_b64encode(pointless_nest).decode('ascii')

def get_channel_tab(channel_id, page="1", sort=3, tab='videos', view=1):
    ctoken = channel_ctoken(channel_id, page, sort, tab, view).replace('=', '%3D')
    url = "https://www.youtube.com/browse_ajax?ctoken=" + ctoken

    print("Sending channel tab ajax request")
    content = common.fetch_url(url, headers_1)
    print("Finished recieving channel tab response")

    '''with open('debug/channel_debug', 'wb') as f:
        f.write(content)'''
    info = json.loads(content)
    return info




def get_number_of_videos(channel_id):
    # Uploads playlist
    playlist_id = 'UU' + channel_id[2:]
    url = 'https://m.youtube.com/playlist?list=' + playlist_id + '&ajax=1&disable_polymer=true'
    print("Getting number of videos")
    response = common.fetch_url(url, common.mobile_ua + headers_1)
    '''with open('debug/playlist_debug_metadata', 'wb') as f:
        f.write(response)'''
    response = response.decode('utf-8')
    print("Got response for number of videos")
    match = re.search(r'"num_videos_text":\s*{(?:"item_type":\s*"formatted_string",)?\s*"runs":\s*\[{"text":\s*"([\d,]*) videos"', response)
    if match:
        return int(match.group(1).replace(',',''))
    else:
        return 0

@functools.lru_cache(maxsize=128)
def get_channel_id(username):
    # method that gives the smallest possible response at ~10 kb
    # needs to be as fast as possible
    url = 'https://m.youtube.com/user/' + username + '/about?ajax=1&disable_polymer=true'
    response = common.fetch_url(url, common.mobile_ua + headers_1).decode('utf-8')
    return re.search(r'"channel_id":\s*"([a-zA-Z0-9_-]*)"', response).group(1)

def grid_items_html(items, additional_info={}):
    result = '''            <nav class="item-grid">\n'''
    for item in items:
        result += common.renderer_html(item, additional_info)
    result += '''\n</nav>'''
    return result

def list_items_html(items, additional_info={}):
    result = '''                <nav class="item-list">'''
    for item in items:
        result += common.renderer_html(item, additional_info)
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
                href_attribute = 'href="' + URL_ORIGIN + "/channel/" + channel_id + "/" + tab_name.lower() + '"',
                tab_name = tab_name,
            )
    result += channel_search_template.substitute(
        action = URL_ORIGIN + "/channel/" + channel_id + "/search",
        search_box_value = html.escape(search_box_value),
    )
    return result
            



def channel_videos_html(polymer_json, current_page=1, number_of_videos = 1000, current_query_string=''):
    microformat = polymer_json[1]['response']['microformat']['microformatDataRenderer']
    channel_url = microformat['urlCanonical'].rstrip('/')
    channel_id = channel_url[channel_url.rfind('/')+1:]
    try:
        items = polymer_json[1]['response']['continuationContents']['gridContinuation']['items']
    except KeyError:
        response = polymer_json[1]['response']
        try:
            contents = response['contents']
        except KeyError:
            items = []
        else:
            items = contents['twoColumnBrowseResultsRenderer']['tabs'][1]['tabRenderer']['content']['sectionListRenderer']['contents'][0]['itemSectionRenderer']['contents'][0]['gridRenderer']['items']
    items_html = grid_items_html(items, {'author': microformat['title']})
    
    return yt_channel_items_template.substitute(
        header              = common.get_header(),
        channel_title       = microformat['title'],
        channel_tabs        = channel_tabs_html(channel_id, 'Videos'),
        avatar              = '/' + microformat['thumbnail']['thumbnails'][0]['url'],
        page_title          = microformat['title'] + ' - Channel',
        items               = items_html,
        page_buttons        = common.page_buttons_html(current_page, math.ceil(number_of_videos/30), URL_ORIGIN + "/channel/" + channel_id + "/videos", current_query_string),
        number_of_results   = '{:,}'.format(number_of_videos) + " videos",
    )

def channel_playlists_html(polymer_json):
    microformat = polymer_json[1]['response']['microformat']['microformatDataRenderer']
    channel_url = microformat['urlCanonical'].rstrip('/')
    channel_id = channel_url[channel_url.rfind('/')+1:]
    try:
        items = polymer_json[1]['response']['continuationContents']['gridContinuation']['items']
    except KeyError:
        response = polymer_json[1]['response']
        try:
            contents = response['contents']
        except KeyError:
            items = []
        else:
            item_section = contents['twoColumnBrowseResultsRenderer']['tabs'][2]['tabRenderer']['content']['sectionListRenderer']['contents'][0]['itemSectionRenderer']['contents'][0]
            try:
                items = item_section['gridRenderer']['items']
            except KeyError:
                if "messageRenderer" in item_section:
                    items = []
                else:
                    raise

    items_html = grid_items_html(items, {'author': microformat['title']})
    
    return yt_channel_items_template.substitute(
        header              = common.get_header(),
        channel_title       = microformat['title'],
        channel_tabs        = channel_tabs_html(channel_id, 'Playlists'),
        avatar              = '/' + microformat['thumbnail']['thumbnails'][0]['url'],
        page_title          = microformat['title'] + ' - Channel',
        items               = items_html,
        page_buttons        = '',
        number_of_results   = '',
    )

channel_link_template = Template('''
<a href="$url">$text</a>''')
stat_template = Template('''
<li>$stat_value</li>''')
def channel_about_page(polymer_json):
    avatar = '/' + polymer_json[1]['response']['microformat']['microformatDataRenderer']['thumbnail']['thumbnails'][0]['url']
    # my goodness...
    channel_metadata = polymer_json[1]['response']['contents']['twoColumnBrowseResultsRenderer']['tabs'][5]['tabRenderer']['content']['sectionListRenderer']['contents'][0]['itemSectionRenderer']['contents'][0]['channelAboutFullMetadataRenderer']
    channel_links = ''
    for link_json in channel_metadata['primaryLinks']:
        channel_links += channel_link_template.substitute(
            url     = html.escape(link_json['navigationEndpoint']['urlEndpoint']['url']),
            text    = common.get_plain_text(link_json['title']),
        )

    stats = ''
    for stat_name in ('subscriberCountText', 'joinedDateText', 'viewCountText', 'country'):
        try:
            stat_value = common.get_plain_text(channel_metadata[stat_name])
        except KeyError:
            continue
        else:
            stats += stat_template.substitute(stat_value=stat_value)
    try:
        description = common.format_text_runs(common.get_formatted_text(channel_metadata['description']))
    except KeyError:
        description = ''
    return yt_channel_about_template.substitute(
        header              = common.get_header(),
        page_title          = common.get_plain_text(channel_metadata['title']) + ' - About',
        channel_title       = common.get_plain_text(channel_metadata['title']),
        avatar              = html.escape(avatar),
        description         = description,
        links               = channel_links,
        stats               = stats,
        channel_tabs        = channel_tabs_html(channel_metadata['channelId'], 'About'),
    )

def channel_search_page(polymer_json, query, current_page=1, number_of_videos = 1000, current_query_string=''):
    microformat = polymer_json[1]['response']['microformat']['microformatDataRenderer']
    channel_url = microformat['urlCanonical'].rstrip('/')
    channel_id = channel_url[channel_url.rfind('/')+1:]

    response = polymer_json[1]['response']
    try:
        items = response['contents']['twoColumnBrowseResultsRenderer']['tabs'][6]['expandableTabRenderer']['content']['sectionListRenderer']['contents']
    except KeyError:
        items = response['continuationContents']['sectionListContinuation']['contents']

    items_html = list_items_html(items)

    return yt_channel_items_template.substitute(
        header              = common.get_header(),
        channel_title       = html.escape(query + ' - Channel search'),
        channel_tabs        = channel_tabs_html(channel_id, '', query),
        avatar              = '/' + microformat['thumbnail']['thumbnails'][0]['url'],
        page_title          = microformat['title'] + ' - Channel',
        items               = items_html,
        page_buttons        = common.page_buttons_html(current_page, math.ceil(number_of_videos/29), URL_ORIGIN + "/channel/" + channel_id + "/search", current_query_string),
        number_of_results   = '',
    )
def get_channel_search_json(channel_id, query, page):
    params = proto.string(2, 'search') + proto.string(15, str(page))
    params = proto.percent_b64encode(params)
    ctoken = proto.string(2, channel_id) + proto.string(3, params) + proto.string(11, query)
    ctoken = base64.urlsafe_b64encode(proto.nested(80226972, ctoken)).decode('ascii')

    polymer_json = common.fetch_url("https://www.youtube.com/browse_ajax?ctoken=" + ctoken, headers_1)
    '''with open('debug/channel_search_debug', 'wb') as f:
        f.write(polymer_json)'''
    polymer_json = json.loads(polymer_json)

    return polymer_json
    

def get_channel_page(url, query_string=''):
    path_components = url.rstrip('/').lstrip('/').split('/')
    channel_id = path_components[0]
    try:
        tab = path_components[1]
    except IndexError:
        tab = 'videos'
    
    parameters = urllib.parse.parse_qs(query_string)
    page_number = int(common.default_multi_get(parameters, 'page', 0, default='1'))
    sort = common.default_multi_get(parameters, 'sort', 0, default='3')
    view = common.default_multi_get(parameters, 'view', 0, default='1')
    query = common.default_multi_get(parameters, 'query', 0, default='')

    if tab == 'videos':
        tasks = (
            gevent.spawn(get_number_of_videos, channel_id ), 
            gevent.spawn(get_channel_tab, channel_id, page_number, sort, 'videos', view)
        )
        gevent.joinall(tasks)
        number_of_videos, polymer_json = tasks[0].value, tasks[1].value

        return channel_videos_html(polymer_json, page_number, number_of_videos, query_string)
    elif tab == 'about':
        polymer_json = common.fetch_url('https://www.youtube.com/channel/' + channel_id + '/about?pbj=1', headers_1)
        polymer_json = json.loads(polymer_json)
        return channel_about_page(polymer_json)
    elif tab == 'playlists':
        polymer_json = common.fetch_url('https://www.youtube.com/channel/' + channel_id + '/playlists?pbj=1&view=1', headers_1)
        '''with open('debug/channel_playlists_debug', 'wb') as f:
            f.write(polymer_json)'''
        polymer_json = json.loads(polymer_json)
        return channel_playlists_html(polymer_json)
    elif tab == 'search':
        tasks = (
            gevent.spawn(get_number_of_videos, channel_id ), 
            gevent.spawn(get_channel_search_json, channel_id, query, page_number)
        )
        gevent.joinall(tasks)
        number_of_videos, polymer_json = tasks[0].value, tasks[1].value

        return channel_search_page(polymer_json, query, page_number, number_of_videos, query_string)
    else:
        raise ValueError('Unknown channel tab: ' + tab)
    
def get_user_page(url, query_string=''):
    path_components = url.rstrip('/').lstrip('/').split('/')
    username = path_components[0]
    try:
        page = path_components[1]
    except IndexError:
        page = 'videos'
    if page == 'videos':
        polymer_json = common.fetch_url('https://www.youtube.com/user/' + username + '/videos?pbj=1', headers_1)
        polymer_json = json.loads(polymer_json)
        return channel_videos_html(polymer_json)
    elif page == 'about':
        polymer_json = common.fetch_url('https://www.youtube.com/user/' + username + '/about?pbj=1', headers_1)
        polymer_json = json.loads(polymer_json)
        return channel_about_page(polymer_json)
    elif page == 'playlists':
        polymer_json = common.fetch_url('https://www.youtube.com/user/' + username + '/playlists?pbj=1&view=1', headers_1)
        polymer_json = json.loads(polymer_json)
        return channel_playlists_html(polymer_json)
    elif page == 'search':
        raise NotImplementedError()
        '''polymer_json = common.fetch_url('https://www.youtube.com/user' + username +  '/search?pbj=1&' + query_string, headers_1)
        polymer_json = json.loads(polymer_json)
        return channel_search_page('''
    else:
        raise ValueError('Unknown channel page: ' + page)