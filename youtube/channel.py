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
import cachetools.func
import traceback

import flask
from flask import request

headers_desktop = (
    ('Accept', '*/*'),
    ('Accept-Language', 'en-US,en;q=0.5'),
    ('X-YouTube-Client-Name', '1'),
    ('X-YouTube-Client-Version', '2.20180830'),
) + util.desktop_ua
headers_mobile = (
    ('Accept', '*/*'),
    ('Accept-Language', 'en-US,en;q=0.5'),
    ('X-YouTube-Client-Name', '2'),
    ('X-YouTube-Client-Version', '2.20180830'),
) + util.mobile_ua
real_cookie = (('Cookie', 'VISITOR_INFO1_LIVE=8XihrAcN1l4'),)
generic_cookie = (('Cookie', 'VISITOR_INFO1_LIVE=ST1Ti53r4fU'),)

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
def channel_ctoken_v3(channel_id, page, sort, tab, view=1):
    # page > 1 doesn't work when sorting by oldest
    offset = 30*(int(page) - 1)
    page_token = proto.string(61, proto.unpadded_b64encode(
        proto.string(1, proto.unpadded_b64encode(proto.uint(1,offset)))
    ))

    tab = proto.string(2, tab )
    sort = proto.uint(3, int(sort))

    shelf_view = proto.uint(4, 0)
    view = proto.uint(6, int(view))
    continuation_info = proto.string(3,
        proto.percent_b64encode(tab + sort + shelf_view + view + page_token)
    )

    channel_id = proto.string(2, channel_id )
    pointless_nest = proto.string(80226972, channel_id + continuation_info)

    return base64.urlsafe_b64encode(pointless_nest).decode('ascii')

def channel_ctoken_v2(channel_id, page, sort, tab, view=1):
    # see https://github.com/iv-org/invidious/issues/1319#issuecomment-671732646
    # page > 1 doesn't work when sorting by oldest
    offset = 30*(int(page) - 1)
    schema_number = {
        3: 6307666885028338688,
        2: 17254859483345278706,
        1: 16570086088270825023,
    }[int(sort)]
    page_token = proto.string(61, proto.unpadded_b64encode(proto.string(1,
            proto.uint(1, schema_number) + proto.string(2,
                proto.string(1, proto.unpadded_b64encode(proto.uint(1,offset)))
            )
    )))

    tab = proto.string(2, tab )
    sort = proto.uint(3, int(sort))
    #page = proto.string(15, str(page) )

    shelf_view = proto.uint(4, 0)
    view = proto.uint(6, int(view))
    continuation_info = proto.string(3,
        proto.percent_b64encode(tab + sort + shelf_view + view + page_token)
    )

    channel_id = proto.string(2, channel_id )
    pointless_nest = proto.string(80226972, channel_id + continuation_info)

    return base64.urlsafe_b64encode(pointless_nest).decode('ascii')

def channel_ctoken_v1(channel_id, page, sort, tab, view=1):
    tab = proto.string(2, tab )
    sort = proto.uint(3, int(sort))
    page = proto.string(15, str(page) )
    # example with shelves in videos tab: https://www.youtube.com/channel/UCNL1ZadSjHpjm4q9j2sVtOA/videos
    shelf_view = proto.uint(4, 0)
    view = proto.uint(6, int(view))
    continuation_info = proto.string(3, proto.percent_b64encode(tab + view + sort + shelf_view + page + proto.uint(23, 0)) )

    channel_id = proto.string(2, channel_id )
    pointless_nest = proto.string(80226972, channel_id + continuation_info)

    return base64.urlsafe_b64encode(pointless_nest).decode('ascii')

def get_channel_tab(channel_id, page="1", sort=3, tab='videos', view=1, print_status=True):
    message = 'Got channel tab' if print_status else None

    if int(sort) == 2 and int(page) > 1:
        ctoken = channel_ctoken_v1(channel_id, page, sort, tab, view)
        ctoken = ctoken.replace('=', '%3D')
        url = ('https://www.youtube.com/channel/' + channel_id + '/' + tab
            + '?action_continuation=1&continuation=' + ctoken
            + '&pbj=1')
        content = util.fetch_url(url, headers_desktop + real_cookie,
            debug_name='channel_tab', report_text=message)
    else:
        ctoken = channel_ctoken_v3(channel_id, page, sort, tab, view)
        ctoken = ctoken.replace('=', '%3D')
        url = 'https://www.youtube.com/browse_ajax?ctoken=' + ctoken
        content = util.fetch_url(url,
            headers_desktop + generic_cookie,
            debug_name='channel_tab', report_text=message)

    return content

# cache entries expire after 30 minutes
@cachetools.func.ttl_cache(maxsize=128, ttl=30*60)
def get_number_of_videos_channel(channel_id):
    if channel_id is None:
        return 1000

    # Uploads playlist
    playlist_id = 'UU' + channel_id[2:]
    url = 'https://m.youtube.com/playlist?list=' + playlist_id + '&pbj=1'

    try:
        response = util.fetch_url(url, headers_mobile,
            debug_name='number_of_videos', report_text='Got number of videos')
    except urllib.error.HTTPError as e:
        traceback.print_exc()
        print("Couldn't retrieve number of videos")
        return 1000

    response = response.decode('utf-8')

    # match = re.search(r'"numVideosText":\s*{\s*"runs":\s*\[{"text":\s*"([\d,]*) videos"', response)
    match = re.search(r'"numVideosText".*?([,\d]+)', response)
    if match:
        return int(match.group(1).replace(',',''))
    else:
        return 0

channel_id_re = re.compile(r'videos\.xml\?channel_id=([a-zA-Z0-9_-]{24})"')
@cachetools.func.lru_cache(maxsize=128)
def get_channel_id(base_url):
    # method that gives the smallest possible response at ~4 kb
    # needs to be as fast as possible
    base_url = base_url.replace('https://www', 'https://m') # avoid redirect
    response = util.fetch_url(base_url + '/about?pbj=1', headers_mobile,
        debug_name='get_channel_id', report_text='Got channel id').decode('utf-8')
    match = channel_id_re.search(response)
    if match:
        return match.group(1)
    return None

def get_number_of_videos_general(base_url):
    return get_number_of_videos_channel(get_channel_id(base_url))

def get_channel_search_json(channel_id, query, page):
    params = proto.string(2, 'search') + proto.string(15, str(page))
    params = proto.percent_b64encode(params)
    ctoken = proto.string(2, channel_id) + proto.string(3, params) + proto.string(11, query)
    ctoken = base64.urlsafe_b64encode(proto.nested(80226972, ctoken)).decode('ascii')

    polymer_json = util.fetch_url("https://www.youtube.com/browse_ajax?ctoken=" + ctoken, headers_desktop, debug_name='channel_search')

    return polymer_json


def post_process_channel_info(info):
    info['avatar'] = util.prefix_url(info['avatar'])
    info['channel_url'] = util.prefix_url(info['channel_url'])
    for item in info['items']:
        util.prefix_urls(item)
        util.add_extra_html_info(item)





playlist_sort_codes = {'2': "da", '3': "dd", '4': "lad"}

# youtube.com/[channel_id]/[tab]
# youtube.com/user/[username]/[tab]
# youtube.com/c/[custom]/[tab]
# youtube.com/[custom]/[tab]
def get_channel_page_general_url(base_url, tab, request, channel_id=None):

    page_number = int(request.args.get('page', 1))
    sort = request.args.get('sort', '3')
    view = request.args.get('view', '1')
    query = request.args.get('query', '')

    if tab == 'videos' and channel_id:
        tasks = (
            gevent.spawn(get_number_of_videos_channel, channel_id),
            gevent.spawn(get_channel_tab, channel_id, page_number, sort, 'videos', view)
        )
        gevent.joinall(tasks)
        util.check_gevent_exceptions(*tasks)
        number_of_videos, polymer_json = tasks[0].value, tasks[1].value
    elif tab == 'videos':
        tasks = (
            gevent.spawn(get_number_of_videos_general, base_url),
            gevent.spawn(util.fetch_url, base_url + '/videos?pbj=1&view=0', headers_desktop, debug_name='gen_channel_videos')
        )
        gevent.joinall(tasks)
        util.check_gevent_exceptions(*tasks)
        number_of_videos, polymer_json = tasks[0].value, tasks[1].value
    elif tab == 'about':
        polymer_json = util.fetch_url(base_url + '/about?pbj=1', headers_desktop, debug_name='gen_channel_about')
    elif tab == 'playlists':
        polymer_json = util.fetch_url(base_url+ '/playlists?pbj=1&view=1&sort=' + playlist_sort_codes[sort], headers_desktop, debug_name='gen_channel_playlists')
    elif tab == 'search' and channel_id:
        polymer_json = get_channel_search_json(channel_id, query, page_number)
    elif tab == 'search':
        url = base_url + '/search?pbj=1&query=' + urllib.parse.quote(query, safe='')
        polymer_json = util.fetch_url(url, headers_desktop, debug_name='gen_channel_search')
    else:
        flask.abort(404, 'Unknown channel tab: ' + tab)


    info = yt_data_extract.extract_channel_info(json.loads(polymer_json), tab)
    if info['error'] is not None:
        return flask.render_template('error.html', error_message = info['error'])

    post_process_channel_info(info)
    if tab == 'videos':
        info['number_of_videos'] = number_of_videos
        info['number_of_pages'] = math.ceil(number_of_videos/30)
        info['header_playlist_names'] = local_playlist.get_playlist_names()
    if tab in ('videos', 'playlists'):
        info['current_sort'] = sort
    elif tab == 'search':
        info['search_box_value'] = query
        info['header_playlist_names'] = local_playlist.get_playlist_names()
        info['page_number'] = page_number
    info['subscribed'] = subscriptions.is_subscribed(info['channel_id'])

    return flask.render_template('channel.html',
        parameters_dictionary = request.args,
        **info
    )

@yt_app.route('/channel/<channel_id>/')
@yt_app.route('/channel/<channel_id>/<tab>')
def get_channel_page(channel_id, tab='videos'):
    return get_channel_page_general_url('https://www.youtube.com/channel/' + channel_id, tab, request, channel_id)

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

