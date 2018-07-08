import json
import urllib
import html
from string import Template
import base64
from math import ceil
from youtube.common import default_multi_get, get_thumbnail_url, URL_ORIGIN
from youtube import common, proto

with open("yt_search_results_template.html", "r") as file:
    yt_search_results_template = file.read()
    
with open("yt_search_template.html", "r") as file:
    yt_search_template = file.read()

page_button_template = Template('''<a class="page-button" href="$href">$page</a>''')
current_page_button_template = Template('''<div class="page-button">$page</div>''')

# Sort: 1
    # Upload date: 2
    # View count: 3
    # Rating: 1
# Offset: 9
# Filters: 2
    # Upload date: 1
    # Type: 2
    # Duration: 3


features = {
    '4k': 14,
    'hd': 4,
    'hdr': 25,
    'subtitles': 5,
    'creative_commons': 6,
    '3d': 7,
    'live': 8,
    'purchased': 9,
    '360': 15,
    'location': 23,
}

def page_number_to_sp_parameter(page):
    offset = (int(page) - 1)*20    # 20 results per page
    return base64.urlsafe_b64encode(proto.uint(9, offset) + proto.string(61, b'')).decode('ascii')

def get_search_json(query, page):
    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query)
    headers = {
        'Host': 'www.youtube.com',
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64)',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'X-YouTube-Client-Name': '1',
        'X-YouTube-Client-Version': '2.20180418',
    }
    url += "&pbj=1&sp=" + page_number_to_sp_parameter(page)
    content = common.fetch_url(url, headers=headers)
    info = json.loads(content)
    return info
    

def page_buttons_html(page_start, page_end, current_page, query):
    result = ""
    for page in range(page_start, page_end+1):
        if page == current_page:
            template = current_page_button_template
        else:
            template = page_button_template
        result += template.substitute(page=page, href=URL_ORIGIN + "/search?query=" + urllib.parse.quote_plus(query) + "&page=" + str(page))
    return result

showing_results_for = Template('''
                <div>Showing results for <a>$corrected_query</a></div>
                <div>Search instead for <a href="$original_query_url">$original_query</a></div>
''')
did_you_mean = Template('''
                <div>Did you mean <a href="$corrected_query_url">$corrected_query</a></div>
''')    
def get_search_page(query_string, parameters=()):
    qs_query = urllib.parse.parse_qs(query_string)
    if len(qs_query) == 0:
        return yt_search_template
    query = qs_query["query"][0]
    page = qs_query.get("page", "1")[0]

    info = get_search_json(query, page)
    
    estimated_results = int(info[1]['response']['estimatedResults'])
    estimated_pages = ceil(estimated_results/20)
    results = info[1]['response']['contents']['twoColumnSearchResultsRenderer']['primaryContents']['sectionListRenderer']['contents'][0]['itemSectionRenderer']['contents']
    
    corrections = ''
    result_list_html = ""
    for renderer in results:
        type = list(renderer.keys())[0]
        if type == 'shelfRenderer':
            continue
        if type == 'didYouMeanRenderer':
            renderer = renderer[type]
            corrected_query_string = urllib.parse.parse_qs(query_string)
            corrected_query_string['query'] = [renderer['correctedQueryEndpoint']['searchEndpoint']['query']]
            corrected_query_url = URL_ORIGIN + '/search?' + common.make_query_string(corrected_query_string)
            corrections = did_you_mean.substitute(
                corrected_query_url = corrected_query_url,
                corrected_query = common.format_text_runs(renderer['correctedQuery']['runs']),
            )
            continue
        if type == 'showingResultsForRenderer':
            renderer = renderer[type]
            no_autocorrect_query_string = urllib.parse.parse_qs(query_string)
            no_autocorrect_query_string['autocorrect'] = ['0']
            no_autocorrect_query_url = URL_ORIGIN + '/search?' + common.make_query_string(no_autocorrect_query_string)
            corrections = showing_results_for.substitute(
                corrected_query = common.format_text_runs(renderer['correctedQuery']['runs']),
                original_query_url = no_autocorrect_query_url,
                original_query = html.escape(renderer['originalQuery']['simpleText']),
            )
            continue
        result_list_html += common.renderer_html(renderer, current_query_string=query_string)
        
    page = int(page)
    if page <= 5:
        page_start = 1
        page_end = min(9, estimated_pages)
    else:
        page_start = page - 4
        page_end = min(page + 4, estimated_pages)
        
    
    result = Template(yt_search_results_template).substitute(
        header              = common.get_header(),
        results             = result_list_html, 
        page_title          = query + " - Search", 
        search_box_value    = html.escape(query),
        number_of_results   = '{:,}'.format(estimated_results),
        number_of_pages     = '{:,}'.format(estimated_pages),
        page_buttons        = page_buttons_html(page_start, page_end, page, query),
        corrections         = corrections
        )
    return result