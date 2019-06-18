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