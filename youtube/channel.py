import base64
from youtube import util, yt_data_extract, local_playlist, subscriptions
from youtube import yt_app

import urllib
import json
from string import Template
import youtube.proto as proto
import html
import math
import gevent
import re
import functools

import flask
from flask import request

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

def get_channel_tab(channel_id, page="1", sort=3, tab='videos', view=1, print_status=True):
    ctoken = channel_ctoken(channel_id, page, sort, tab, view).replace('=', '%3D')
    url = "https://www.youtube.com/browse_ajax?ctoken=" + ctoken

    if print_status:
        print("Sending channel tab ajax request")
    content = util.fetch_url(url, util.desktop_ua + headers_1, debug_name='channel_tab')
    if print_status:
        print("Finished recieving channel tab response")

    return content

def get_number_of_videos(channel_id):
    # Uploads playlist
    playlist_id = 'UU' + channel_id[2:]
    url = 'https://m.youtube.com/playlist?list=' + playlist_id + '&pbj=1'
    print("Getting number of videos")

    # Sometimes retrieving playlist info fails with 403 for no discernable reason
    try:
        response = util.fetch_url(url, util.mobile_ua + headers_pbj, debug_name='number_of_videos')
    except urllib.error.HTTPError as e:
        if e.code != 403:
            raise
        print("Couldn't retrieve number of videos")
        return 1000

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

def get_channel_search_json(channel_id, query, page):
    params = proto.string(2, 'search') + proto.string(15, str(page))
    params = proto.percent_b64encode(params)
    ctoken = proto.string(2, channel_id) + proto.string(3, params) + proto.string(11, query)
    ctoken = base64.urlsafe_b64encode(proto.nested(80226972, ctoken)).decode('ascii')

    polymer_json = util.fetch_url("https://www.youtube.com/browse_ajax?ctoken=" + ctoken, util.desktop_ua + headers_1, debug_name='channel_search')

    return polymer_json

def extract_info(polymer_json, tab):
    response = polymer_json[1]['response']
    try:
        microformat = response['microformat']['microformatDataRenderer']

    # channel doesn't exist or was terminated
    # example terminated channel: https://www.youtube.com/channel/UCnKJeK_r90jDdIuzHXC0Org
    except KeyError:
        if 'alerts' in response and len(response['alerts']) > 0:
            result = ''
            for alert in response['alerts']:
                result += alert['alertRenderer']['text']['simpleText'] + '\n'
            flask.abort(200, result)
        elif 'errors' in response['responseContext']:
            for error in response['responseContext']['errors']['error']:
                if error['code'] == 'INVALID_VALUE' and error['location'] == 'browse_id':
                    flask.abort(404, 'This channel does not exist')
        raise


    info = {}
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
        info['items'] = [yt_data_extract.renderer_info(renderer, additional_info) for renderer in items]

    elif tab == 'about':
        channel_metadata = tab_content['sectionListRenderer']['contents'][0]['itemSectionRenderer']['contents'][0]['channelAboutFullMetadataRenderer']


        info['links'] = []
        for link_json in channel_metadata.get('primaryLinks', ()):
            url = link_json['navigationEndpoint']['urlEndpoint']['url']
            if url.startswith('/redirect'):     # youtube puts these on external links to do tracking
                query_string = url[url.find('?')+1: ]
                url = urllib.parse.parse_qs(query_string)['q'][0]

            text = yt_data_extract.get_plain_text(link_json['title'])

            info['links'].append( (text, url) )


        info['stats'] = []
        for stat_name in ('subscriberCountText', 'joinedDateText', 'viewCountText', 'country'):
            try:
                stat = channel_metadata[stat_name]
            except KeyError:
                continue
            info['stats'].append(yt_data_extract.get_plain_text(stat))

        if 'description' in channel_metadata:
            info['description'] = yt_data_extract.get_text(channel_metadata['description'])
        else:
            info['description'] = ''

    else:
        raise NotImplementedError('Unknown or unsupported channel tab: ' + tab)

    return info

def post_process_channel_info(info):
    info['avatar'] = util.prefix_url(info['avatar'])
    info['channel_url'] = util.prefix_url(info['channel_url'])
    for item in info['items']:
        yt_data_extract.prefix_urls(item)
        yt_data_extract.add_extra_html_info(item)





playlist_sort_codes = {'2': "da", '3': "dd", '4': "lad"}

@yt_app.route('/channel/<channel_id>/')
@yt_app.route('/channel/<channel_id>/<tab>')
def get_channel_page(channel_id, tab='videos'):

    page_number = int(request.args.get('page', 1))
    sort = request.args.get('sort', '3')
    view = request.args.get('view', '1')
    query = request.args.get('query', '')


    if tab == 'videos':
        tasks = (
            gevent.spawn(get_number_of_videos, channel_id ), 
            gevent.spawn(get_channel_tab, channel_id, page_number, sort, 'videos', view)
        )
        gevent.joinall(tasks)
        number_of_videos, polymer_json = tasks[0].value, tasks[1].value

    elif tab == 'about':
        polymer_json = util.fetch_url('https://www.youtube.com/channel/' + channel_id + '/about?pbj=1', util.desktop_ua + headers_1, debug_name='channel_about')
    elif tab == 'playlists':
        polymer_json = util.fetch_url('https://www.youtube.com/channel/' + channel_id + '/playlists?pbj=1&view=1&sort=' + playlist_sort_codes[sort], util.desktop_ua + headers_1, debug_name='channel_playlists')
    elif tab == 'search':
        tasks = (
            gevent.spawn(get_number_of_videos, channel_id ), 
            gevent.spawn(get_channel_search_json, channel_id, query, page_number)
        )
        gevent.joinall(tasks)
        number_of_videos, polymer_json = tasks[0].value, tasks[1].value

    else:
        flask.abort(404, 'Unknown channel tab: ' + tab)


    info = extract_info(json.loads(polymer_json), tab)
    post_process_channel_info(info)
    if tab in ('videos', 'search'):
        info['number_of_videos'] = number_of_videos
        info['number_of_pages'] = math.ceil(number_of_videos/30)
        info['header_playlist_names'] = local_playlist.get_playlist_names()
    if tab in ('videos', 'playlists'):
        info['current_sort'] = sort
    elif tab == 'search':
        info['search_box_value'] = query
    info['subscribed'] = subscriptions.is_subscribed(info['channel_id'])

    return flask.render_template('channel.html',
        parameters_dictionary = request.args,
        **info
    )


# youtube.com/user/[username]/[tab]
# youtube.com/c/[custom]/[tab]
# youtube.com/[custom]/[tab]
def get_channel_page_general_url(base_url, tab, request):

    page_number = int(request.args.get('page', 1))
    sort = request.args.get('sort', '3')
    view = request.args.get('view', '1')
    query = request.args.get('query', '')

    if tab == 'videos':
        polymer_json = util.fetch_url(base_url + '/videos?pbj=1&view=0', util.desktop_ua + headers_1, debug_name='gen_channel_videos')
    elif tab == 'about':
        polymer_json = util.fetch_url(base_url + '/about?pbj=1', util.desktop_ua + headers_1, debug_name='gen_channel_about')
    elif tab == 'playlists':
        polymer_json = util.fetch_url(base_url+ '/playlists?pbj=1&view=1', util.desktop_ua + headers_1, debug_name='gen_channel_playlists')
    elif tab == 'search':
        raise NotImplementedError()
    else:
        flask.abort(404, 'Unknown channel tab: ' + tab)


    info = extract_info(json.loads(polymer_json), tab)
    post_process_channel_info(info)
    if tab in ('videos', 'search'):
        info['number_of_videos'] = 1000
        info['number_of_pages'] = math.ceil(1000/30)
        info['header_playlist_names'] = local_playlist.get_playlist_names()
    if tab in ('videos', 'playlists'):
        info['current_sort'] = sort
    elif tab == 'search':
        info['search_box_value'] = query
    info['subscribed'] = subscriptions.is_subscribed(info['channel_id'])

    return flask.render_template('channel.html',
        parameters_dictionary = request.args,
        **info
    )


@yt_app.route('/user/<username>/')
@yt_app.route('/user/<username>/<tab>')
def get_user_page(username, tab='videos'):
    return get_channel_page_general_url('https://www.youtube.com/user/' + username, tab, request)

@yt_app.route('/c/<custom>/')
@yt_app.route('/c/<custom>/<tab>')
def get_custom_c_page(custom, tab='videos'):
    return get_channel_page_general_url('https://www.youtube.com/c/' + custom, tab, request)

@yt_app.route('/<custom>')
@yt_app.route('/<custom>/<tab>')
def get_toplevel_custom_page(custom, tab='videos'):
    return get_channel_page_general_url('https://www.youtube.com/' + custom, tab, request)

