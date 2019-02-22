from youtube.template import Template
from youtube import local_playlist, yt_data_extract, util

import json
import html


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
        url         = util.URL_ORIGIN + "/watch?v=" + item["id"],
        thumbnail   = util.get_thumbnail_url(item['id']),
        video_info  = html.escape(video_info),
    )

def small_playlist_item_html(item):
    return small_playlist_item_template.substitute(
        title=html.escape(item["title"]),
        size = item['size'],
        author="",
        url = util.URL_ORIGIN + "/playlist?list=" + item["id"],
        thumbnail= util.get_thumbnail_url(item['first_video_id']),
    )

def medium_playlist_item_html(item):
    return medium_playlist_item_template.substitute(
        title=html.escape(item["title"]),
        size = item['size'],
        author=item['author'],
        author_url= util.URL_ORIGIN + item['author_url'],
        url = util.URL_ORIGIN + "/playlist?list=" + item["id"],
        thumbnail= item['thumbnail'],
    )

def medium_video_item_html(medium_video_info):
    info = medium_video_info
       
    return medium_video_item_template.substitute(
            title=html.escape(info["title"]),
            views=info["views"],
            published = info["published"],
            description = yt_data_extract.format_text_runs(info["description"]),
            author=html.escape(info["author"]),
            author_url=info["author_url"],
            duration=info["duration"],
            url = util.URL_ORIGIN + "/watch?v=" + info["id"],
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


                                <h3>Upload date</h3>
                                <input type="radio" id="time_any" name="time" value="0">
                                <label for="time_any">Any</label>

                                <input type="radio" id="time_last_hour" name="time" value="1">
                                <label for="time_last_hour">Last hour</label>

                                <input type="radio" id="time_today" name="time" value="2">
                                <label for="time_today">Today</label>

                                <input type="radio" id="time_this_week" name="time" value="3">
                                <label for="time_this_week">This week</label>

                                <input type="radio" id="time_this_month" name="time" value="4">
                                <label for="time_this_month">This month</label>

                                <input type="radio" id="time_this_year" name="time" value="5">
                                <label for="time_this_year">This year</label>

                                <h3>Type</h3>
                                <input type="radio" id="type_any" name="type" value="0">
                                <label for="type_any">Any</label>

                                <input type="radio" id="type_video" name="type" value="1">
                                <label for="type_video">Video</label>

                                <input type="radio" id="type_channel" name="type" value="2">
                                <label for="type_channel">Channel</label>

                                <input type="radio" id="type_playlist" name="type" value="3">
                                <label for="type_playlist">Playlist</label>

                                <input type="radio" id="type_movie" name="type" value="4">
                                <label for="type_movie">Movie</label>

                                <input type="radio" id="type_show" name="type" value="5">
                                <label for="type_show">Show</label>


                                <h3>Duration</h3>
                                <input type="radio" id="duration_any" name="duration" value="0">
                                <label for="duration_any">Any</label>

                                <input type="radio" id="duration_short" name="duration" value="1">
                                <label for="duration_short">Short (< 4 minutes)</label>

                                <input type="radio" id="duration_long" name="duration" value="2">
                                <label for="duration_long">Long (> 20 minutes)</label>

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











def badges_html(badges):
    return ' | '.join(map(html.escape, badges))


html_transform_dispatch = {
    'title':        html.escape,
    'published':    html.escape,
    'id':           html.escape,
    'description':  yt_data_extract.format_text_runs,
    'duration':     html.escape,
    'thumbnail':    lambda url: html.escape('/' + url.lstrip('/')),
    'size':         html.escape,
    'author':       html.escape,
    'author_url':   lambda url: html.escape(util.URL_ORIGIN + url),
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
    html_ready['url'] = util.URL_ORIGIN + "/watch?v=" + html_ready['id']
    html_ready['datetime'] = '' #TODO
    
    for key in html_exclude:
        del html_ready[key]
    html_ready['stats'] = get_stats(html_ready)

    return template.substitute(html_ready)


def playlist_item_html(item, template, html_exclude=set()):
    html_ready = get_html_ready(item)

    html_ready['url'] = util.URL_ORIGIN + "/playlist?list=" + html_ready['id']
    html_ready['datetime'] = '' #TODO

    for key in html_exclude:
        del html_ready[key]
    html_ready['stats'] = get_stats(html_ready)

    return template.substitute(html_ready)







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
        result += template.substitute(page=page, href = url + "?" + util.update_query_string(current_query_string, {'page': [str(page)]}) )
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
        info = yt_data_extract.renderer_info(renderer)
        html_ready = get_html_ready(info)
        html_ready['url'] = util.URL_ORIGIN + "/channel/" + html_ready['id']
        return medium_channel_item_template.substitute(html_ready)
    
    if type in ('movieRenderer', 'clarificationRenderer'):
        return ''

    info = yt_data_extract.renderer_info(renderer)
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