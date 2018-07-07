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


grid_video_item_template = Template('''
                <div class="small-item-box">
                    <div class="small-item">
                        <a class="video-thumbnail-box" href="$url" title="$title">
                            <img class="video-thumbnail-img" src="$thumbnail">
                            <span class="video-duration">$duration</span>
                        </a>
                        <a class="title" href="$url" title="$title">$title</a>
                        
                        <span class="views">$views</span>
                        <time datetime="$datetime">Uploaded $published</time>
                        
                    </div>
                    <input class="item-checkbox" type="checkbox" name="video_info_list" value="$video_info" form="playlist-add">
                </div>
''')

def grid_video_item_info(grid_video_renderer, author):
    renderer = grid_video_renderer
    return {
        "title": renderer['title']['simpleText'],
        "id": renderer['videoId'],
        "views": renderer['viewCountText'].get('simpleText', None) or renderer['viewCountText']['runs'][0]['text'],
        "author": author,
        "duration": default_multi_get(renderer, 'lengthText', 'simpleText', default=''), # livestreams dont have a length
        "published": default_multi_get(renderer, 'publishedTimeText', 'simpleText', default=''),
    }

def grid_video_item_html(item):
    video_info = json.dumps({key: item[key] for key in ('id', 'title', 'author', 'duration')})
    return grid_video_item_template.substitute(
        title       = html.escape(item["title"]),
        views       = item["views"],
        duration    = item["duration"],
        url         = URL_ORIGIN + "/watch?v=" + item["id"],
        thumbnail   = get_thumbnail_url(item['id']),
        video_info  = html.escape(json.dumps(video_info)),
        published   = item["published"],
        datetime    = '', # TODO
    )

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

channel_tab_template = Template('''\n<a class="tab page-button"$href_attribute>$tab_name</a>''')
tabs = ('Videos', 'Playlists', 'About')
def channel_tabs_html(channel_id, current_tab):
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
            items = contents['twoColumnBrowseResultsRenderer']['tabs'][2]['tabRenderer']['content']['sectionListRenderer']['contents'][0]['itemSectionRenderer']['contents'][0]['gridRenderer']['items']
    items_html = grid_items_html(items, {'author': microformat['title']})
    
    return yt_channel_items_template.substitute(
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
        page_title          = common.get_plain_text(channel_metadata['title']) + ' - About',
        channel_title       = common.get_plain_text(channel_metadata['title']),
        avatar              = html.escape(avatar),
        description         = description,
        links               = channel_links,
        stats               = stats,
        channel_tabs        = channel_tabs_html(channel_metadata['channelId'], 'About'),
    )
    
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
        polymer_json = common.fetch_url('https://www.youtube.com/channel/' + channel_id + '/playlists?pbj=1', headers_1)
        polymer_json = json.loads(polymer_json)
        return channel_playlists_html(polymer_json)
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
        polymer_json = common.fetch_url('https://www.youtube.com/user/' + username + '/playlists?pbj=1', headers_1)
        polymer_json = json.loads(polymer_json)
        return channel_playlists_html(polymer_json)
    else:
        raise ValueError('Unknown channel page: ' + page)