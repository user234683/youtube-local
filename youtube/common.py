from youtube.template import Template
from youtube import local_playlist
import html
import json
import re
import urllib.parse
import gzip
import brotli
import time


URL_ORIGIN = "/https://www.youtube.com"


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


with open('yt_basic_template.html', 'r', encoding='utf-8') as file:
    yt_basic_template = Template(file.read())




page_button_template = Template('''<a class="page-button" href="$href">$page</a>''')
current_page_button_template = Template('''<div class="current-page-button">$page</a>''')

medium_playlist_item_template = Template('''
                <div class="medium-item-box">
                    <div class="medium-item">
                        <a class="playlist-thumbnail-box" href="$url" title="$title">
                            <img class="playlist-thumbnail-img" src="$thumbnail">
                            <div class="playlist-thumbnail-info">
                                <span>$size</span>
                            </div>
                        </a>

                        <a class="title" href="$url" title="$title">$title</a>
                        
                        <div class="stats">$stats</div>
                    </div>
                </div>
''')
medium_video_item_template = Template('''
                <div class="medium-item-box">
                    <div class="medium-item">
                        <a class="video-thumbnail-box" href="$url" title="$title">
                            <img class="video-thumbnail-img" src="$thumbnail">
                            <span class="video-duration">$duration</span>
                        </a>

                        <a class="title" href="$url" title="$title">$title</a>
                        
                        <div class="stats">$stats</div>

                        <span class="description">$description</span>
                        <span class="badges">$badges</span>
                    </div>
                    <input class="item-checkbox" type="checkbox" name="video_info_list" value="$video_info" form="playlist-edit">
                </div>
''')

small_video_item_template = Template('''
                <div class="small-item-box">
                    <div class="small-item">
                        <a class="video-thumbnail-box" href="$url" title="$title">
                            <img class="video-thumbnail-img" src="$thumbnail">
                            <span class="video-duration">$duration</span>
                        </a>
                        <a class="title" href="$url" title="$title">$title</a>
                        
                        <address>$author</address>
                        <span class="views">$views</span>
                        
                    </div>
                    <input class="item-checkbox" type="checkbox" name="video_info_list" value="$video_info" form="playlist-edit">
                </div>
''')

small_playlist_item_template = Template('''
                <div class="small-item-box">
                    <div class="small-item">
                        <a class="playlist-thumbnail-box" href="$url" title="$title">
                            <img class="playlist-thumbnail-img" src="$thumbnail">
                            <div class="playlist-thumbnail-info">
                                <span>$size</span>
                            </div>
                        </a>
                        <a class="title" href="$url" title="$title">$title</a>
                        
                        <address>$author</address>
                    </div>
                </div>
''')

medium_channel_item_template = Template('''
                <div class="medium-item-box">
                    <div class="medium-item">
                        <a class="video-thumbnail-box" href="$url" title="$title">
                            <img class="video-thumbnail-img" src="$thumbnail">
                            <span class="video-duration">$duration</span>
                        </a>

                        <a class="title" href="$url">$title</a>
                        
                        <span>$subscriber_count</span>
                        <span>$size</span>

                        <span class="description">$description</span>
                    </div>
                </div>
''')

def decode_content(content, encoding_header):
    encodings = encoding_header.replace(' ', '').split(',')
    for encoding in reversed(encodings):
        if encoding == 'identity':
            continue
        if encoding == 'br':
            content = brotli.decompress(content)
        elif encoding == 'gzip':
            content = gzip.decompress(content)
    return content

def fetch_url(url, headers=(), timeout=15, report_text=None):
    if isinstance(headers, list):
        headers +=  [('Accept-Encoding', 'gzip, br')]
        headers = dict(headers)
    elif isinstance(headers, tuple):
        headers += (('Accept-Encoding', 'gzip, br'),)
        headers = dict(headers)
    else:
        headers = headers.copy()
        headers['Accept-Encoding'] = 'gzip, br'
    
    start_time = time.time()

    req = urllib.request.Request(url, headers=headers)
    response = urllib.request.urlopen(req, timeout=timeout)
    response_time = time.time()

    content = response.read()
    read_finish = time.time()
    if report_text:
        print(report_text, '    Latency:', response_time - start_time, '    Read time:', read_finish - response_time)
    content = decode_content(content, response.getheader('Content-Encoding', default='identity'))
    return content

mobile_user_agent = 'Mozilla/5.0 (iPhone; CPU iPhone OS 10_3_1 like Mac OS X) AppleWebKit/603.1.30 (KHTML, like Gecko) Version/10.0 Mobile/14E304 Safari/602.1'
mobile_ua = (('User-Agent', mobile_user_agent),)
desktop_user_agent = 'Mozilla/5.0 (Windows NT 6.1; rv:52.0) Gecko/20100101 Firefox/52.0'
desktop_ua = (('User-Agent', desktop_user_agent),)

def dict_add(*dicts):
    for dictionary in dicts[1:]:
        dicts[0].update(dictionary)
    return dicts[0]

def video_id(url):
    url_parts = urllib.parse.urlparse(url)
    return urllib.parse.parse_qs(url_parts.query)['v'][0]

def uppercase_escape(s):
     return re.sub(
         r'\\U([0-9a-fA-F]{8})',
         lambda m: chr(int(m.group(1), base=16)), s)

def default_multi_get(object, *keys, default):
    ''' Like dict.get(), but for nested dictionaries/sequences, supporting keys or indices. Last argument is the default value to use in case of any IndexErrors or KeyErrors '''
    try:
        for key in keys:
            object = object[key]
        return object
    except (IndexError, KeyError):
        return default

def get_plain_text(node):
    try:
        return html.escape(node['simpleText'])
    except KeyError:
        return unformmated_text_runs(node['runs'])
        
def unformmated_text_runs(runs):
    result = ''
    for text_run in runs:
        result += html.escape(text_run["text"])
    return result

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

# default, sddefault, mqdefault, hqdefault, hq720
def get_thumbnail_url(video_id):
    return "/i.ytimg.com/vi/" + video_id + "/mqdefault.jpg"
    
def seconds_to_timestamp(seconds):
    seconds = int(seconds)
    hours, seconds = divmod(seconds,3600)
    minutes, seconds = divmod(seconds,60)
    if hours != 0:
        timestamp = str(hours) + ":"
        timestamp += str(minutes).zfill(2)  # zfill pads with zeros
    else:
        timestamp = str(minutes)

    timestamp += ":" + str(seconds).zfill(2)
    return timestamp


# -----
# HTML
# -----

def small_video_item_html(item):
    video_info = json.dumps({key: item[key] for key in ('id', 'title', 'author', 'duration')})
    return small_video_item_template.substitute(
        title       = html.escape(item["title"]),
        views       = item["views"],
        author      = html.escape(item["author"]),
        duration    = item["duration"],
        url         = URL_ORIGIN + "/watch?v=" + item["id"],
        thumbnail   = get_thumbnail_url(item['id']),
        video_info  = html.escape(video_info),
    )

def small_playlist_item_html(item):
    return small_playlist_item_template.substitute(
        title=html.escape(item["title"]),
        size = item['size'],
        author="",
        url = URL_ORIGIN + "/playlist?list=" + item["id"],
        thumbnail= get_thumbnail_url(item['first_video_id']),
    )

def medium_playlist_item_html(item):
    return medium_playlist_item_template.substitute(
        title=html.escape(item["title"]),
        size = item['size'],
        author=item['author'],
        author_url= URL_ORIGIN + item['author_url'],
        url = URL_ORIGIN + "/playlist?list=" + item["id"],
        thumbnail= item['thumbnail'],
    )

def medium_video_item_html(medium_video_info):
    info = medium_video_info
       
    return medium_video_item_template.substitute(
            title=html.escape(info["title"]),
            views=info["views"],
            published = info["published"],
            description = format_text_runs(info["description"]),
            author=html.escape(info["author"]),
            author_url=info["author_url"],
            duration=info["duration"],
            url = URL_ORIGIN + "/watch?v=" + info["id"],
            thumbnail=info['thumbnail'],
            datetime='', # TODO
        )


header_template = Template('''
        <header>

                <form id="site-search" action="/youtube.com/search">
                    <input type="search" name="query" class="search-box" value="$search_box_value">
                    <button type="submit" value="Search" class="search-button">Search</button>
                    <div class="dropdown">
                        <button class="dropdown-label">Options</button>
                        <div class="css-sucks">
                            <div class="dropdown-content">
                                <h3>Sort by</h3>
                                <input type="radio" id="sort_relevance" name="sort" value="0">
                                <label for="sort_relevance">Relevance</label>

                                <input type="radio" id="sort_upload_date" name="sort" value="2">
                                <label for="sort_upload_date">Upload date</label>

                                <input type="radio" id="sort_view_count" name="sort" value="3">
                                <label for="sort_view_count">View count</label>

                                <input type="radio" id="sort_rating" name="sort" value="1">
                                <label for="sort_rating">Rating</label>
                            </div>
                        </div>
                    </div>
                </form>

            <div id="header-right">
                <form id="playlist-edit" action="/youtube.com/edit_playlist" method="post" target="_self">
                    <input name="playlist_name" id="playlist-name-selection" list="playlist-options" type="text">
                    <datalist id="playlist-options">
$playlists
                    </datalist>
                    <button type="submit" id="playlist-add-button" name="action" value="add">Add to playlist</button>
                    <button type="reset" id="item-selection-reset">Clear selection</button>
                </form>
                <a href="/youtube.com/playlists" id="local-playlists">Local playlists</a>
            </div>
        </header>
''')
playlist_option_template = Template('''<option value="$name">$name</option>''')
def get_header(search_box_value=""):
    playlists = ''
    for name in local_playlist.get_playlist_names():
        playlists += playlist_option_template.substitute(name = name)
    return header_template.substitute(playlists = playlists, search_box_value = html.escape(search_box_value))



def get_url(node):
    try:
        return node['runs'][0]['navigationEndpoint']['commandMetadata']['webCommandMetadata']['url']
    except KeyError:
        return node['navigationEndpoint']['commandMetadata']['webCommandMetadata']['url']


def get_text(node):
    try:
        return node['simpleText']
    except KeyError:
            pass
    try:
        return node['runs'][0]['text']
    except IndexError: # empty text runs
        return ''

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

    'videoCountText':       ('size',        get_text),
    'playlistId':           ('id',          lambda node: node),

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

def renderer_info(renderer):
    try:
        info = {}
        if 'viewCountText' in renderer:     # prefer this one as it contains all the digits
            info['views'] = get_text(renderer['viewCountText'])
        elif 'shortViewCountText' in renderer:
            info['views'] = get_text(renderer['shortViewCountText'])
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
        return info
    except KeyError:
        print(renderer)
        raise
    
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
    
def badges_html(badges):
    return ' | '.join(map(html.escape, badges))





html_transform_dispatch = {
    'title':        html.escape,
    'published':    html.escape,
    'id':           html.escape,
    'description':  format_text_runs,
    'duration':     html.escape,
    'thumbnail':    lambda url: html.escape('/' + url.lstrip('/')),
    'size':         html.escape,
    'author':       html.escape,
    'author_url':   lambda url: html.escape(URL_ORIGIN + url),
    'views':        html.escape,
    'subscriber_count': html.escape,
    'badges':       badges_html,
    'playlist_index':   html.escape,
}

def get_html_ready(item):
    html_ready = {}
    for key, value in item.items():
        try:
            function = html_transform_dispatch[key]
        except KeyError:
            continue
        html_ready[key] = function(value)
    return html_ready


author_template_url = Template('''<address>By <a href="$author_url">$author</a></address>''')
author_template = Template('''<address><b>$author</b></address>''')
stat_templates = (
    Template('''<span class="views">$views</span>'''),
    Template('''<time datetime="$datetime">$published</time>'''),
)
def get_stats(html_ready):
    stats = []
    if 'author' in html_ready:
        if 'author_url' in html_ready:
            stats.append(author_template_url.substitute(html_ready))
        else:
            stats.append(author_template.substitute(html_ready))
    for stat in stat_templates:
        try:
            stats.append(stat.strict_substitute(html_ready))
        except KeyError:
            pass
    return ' | '.join(stats)

def video_item_html(item, template, html_exclude=set()):

    video_info = {}
    for key in ('id', 'title', 'author'):
        try:
            video_info[key] = item[key] 
        except KeyError:
            video_info[key] = ''
    try:
        video_info['duration'] = item['duration']
    except KeyError:
        video_info['duration'] = 'Live'     # livestreams don't have a duration

    html_ready = get_html_ready(item)

    html_ready['video_info'] = html.escape(json.dumps(video_info) )
    html_ready['url'] = URL_ORIGIN + "/watch?v=" + html_ready['id']
    html_ready['datetime'] = '' #TODO
    
    for key in html_exclude:
        del html_ready[key]
    html_ready['stats'] = get_stats(html_ready)

    return template.substitute(html_ready)


def playlist_item_html(item, template, html_exclude=set()):
    html_ready = get_html_ready(item)

    html_ready['url'] = URL_ORIGIN + "/playlist?list=" + html_ready['id']
    html_ready['datetime'] = '' #TODO

    for key in html_exclude:
        del html_ready[key]
    html_ready['stats'] = get_stats(html_ready)

    return template.substitute(html_ready)






def make_query_string(query_string):
    return '&'.join(key + '=' + ','.join(values) for key,values in query_string.items())

def update_query_string(query_string, items):
    parameters = urllib.parse.parse_qs(query_string)
    parameters.update(items)
    return make_query_string(parameters)

page_button_template = Template('''<a class="page-button" href="$href">$page</a>''')
current_page_button_template = Template('''<div class="page-button">$page</div>''')

def page_buttons_html(current_page, estimated_pages, url, current_query_string):
    if current_page <= 5:
        page_start = 1
        page_end = min(9, estimated_pages)
    else:
        page_start = current_page - 4
        page_end = min(current_page + 4, estimated_pages)

    result = ""
    for page in range(page_start, page_end+1):
        if page == current_page:
            template = current_page_button_template
        else:
            template = page_button_template
        result += template.substitute(page=page, href = url + "?" + update_query_string(current_query_string, {'page': [str(page)]}) )
    return result







showing_results_for = Template('''
                <div class="showing-results-for">
                    <div>Showing results for <a>$corrected_query</a></div>
                    <div>Search instead for <a href="$original_query_url">$original_query</a></div>
                </div>
''')

did_you_mean = Template('''
                <div class="did-you-mean">
                    <div>Did you mean <a href="$corrected_query_url">$corrected_query</a></div>
                </div>
''')
    
def renderer_html(renderer, additional_info={}, current_query_string=''):
    type = list(renderer.keys())[0]
    renderer = renderer[type]
    if type == 'itemSectionRenderer':
        return renderer_html(renderer['contents'][0], additional_info, current_query_string)

    if type == 'channelRenderer':
        info = renderer_info(renderer)
        html_ready = get_html_ready(info)
        html_ready['url'] = URL_ORIGIN + "/channel/" + html_ready['id']
        return medium_channel_item_template.substitute(html_ready)
    
    if type in ('movieRenderer', 'clarificationRenderer'):
        return ''

    info = renderer_info(renderer)
    info.update(additional_info)
    html_exclude = set(additional_info.keys())
    if type == 'compactVideoRenderer':
        return video_item_html(info, small_video_item_template, html_exclude=html_exclude)
    if type in ('compactPlaylistRenderer', 'compactRadioRenderer', 'compactShowRenderer'):
        return playlist_item_html(info, small_playlist_item_template, html_exclude=html_exclude)
    if type in ('videoRenderer', 'gridVideoRenderer'):
        return video_item_html(info, medium_video_item_template, html_exclude=html_exclude)
    if type in ('playlistRenderer', 'gridPlaylistRenderer', 'radioRenderer', 'gridRadioRenderer', 'gridShowRenderer', 'showRenderer'):
        return playlist_item_html(info, medium_playlist_item_template, html_exclude=html_exclude)

    #print(renderer)
    #raise NotImplementedError('Unknown renderer type: ' + type)
    return ''
