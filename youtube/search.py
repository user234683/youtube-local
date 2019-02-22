from youtube import util, html_common, yt_data_extract, proto

import json
import urllib
import html
from string import Template
import base64
from math import ceil


with open("yt_search_results_template.html", "r") as file:
    yt_search_results_template = file.read()


# Sort: 1
    # Upload date: 2
    # View count: 3
    # Rating: 1
    # Relevance: 0
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

def page_number_to_sp_parameter(page, autocorrect, sort, filters):
    offset = (int(page) - 1)*20    # 20 results per page
    autocorrect = proto.nested(8, proto.uint(1, 1 - int(autocorrect) ))
    filters_enc = proto.nested(2, proto.uint(1, filters['time']) + proto.uint(2, filters['type']) + proto.uint(3, filters['duration']))
    result = proto.uint(1, sort) + filters_enc + autocorrect + proto.uint(9, offset) + proto.string(61, b'')
    return base64.urlsafe_b64encode(result).decode('ascii')

def get_search_json(query, page, autocorrect, sort, filters):
    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query)
    headers = {
        'Host': 'www.youtube.com',
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64)',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'X-YouTube-Client-Name': '1',
        'X-YouTube-Client-Version': '2.20180418',
    }
    url += "&pbj=1&sp=" + page_number_to_sp_parameter(page, autocorrect, sort, filters).replace("=", "%3D")
    content = util.fetch_url(url, headers=headers, report_text="Got search results")
    info = json.loads(content)
    return info
    

showing_results_for = Template('''
                <div>Showing results for <a>$corrected_query</a></div>
                <div>Search instead for <a href="$original_query_url">$original_query</a></div>
''')
did_you_mean = Template('''
                <div>Did you mean <a href="$corrected_query_url">$corrected_query</a></div>
''')    
def get_search_page(env, start_response):
    start_response('200 OK', [('Content-type','text/html'),])
    parameters = env['parameters']
    if len(parameters) == 0:
        return html_common.yt_basic_template.substitute(
            page_title = "Search",
            header = html_common.get_header(),
            style = '',
            page = '',
        ).encode('utf-8')
    query = parameters["query"][0]
    page = parameters.get("page", "1")[0]
    autocorrect = int(parameters.get("autocorrect", "1")[0])
    sort = int(parameters.get("sort", "0")[0])
    filters = {}
    filters['time'] = int(parameters.get("time", "0")[0])
    filters['type'] = int(parameters.get("type", "0")[0])
    filters['duration'] = int(parameters.get("duration", "0")[0])
    info = get_search_json(query, page, autocorrect, sort, filters)
    
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
            corrected_query_string = parameters.copy()
            corrected_query_string['query'] = [renderer['correctedQueryEndpoint']['searchEndpoint']['query']]
            corrected_query_url = util.URL_ORIGIN + '/search?' + urllib.parse.urlencode(corrected_query_string, doseq=True)
            corrections = did_you_mean.substitute(
                corrected_query_url = corrected_query_url,
                corrected_query = yt_data_extract.format_text_runs(renderer['correctedQuery']['runs']),
            )
            continue
        if type == 'showingResultsForRenderer':
            renderer = renderer[type]
            no_autocorrect_query_string = parameters.copy()
            no_autocorrect_query_string['autocorrect'] = ['0']
            no_autocorrect_query_url = util.URL_ORIGIN + '/search?' + urllib.parse.urlencode(no_autocorrect_query_string, doseq=True)
            corrections = showing_results_for.substitute(
                corrected_query = yt_data_extract.format_text_runs(renderer['correctedQuery']['runs']),
                original_query_url = no_autocorrect_query_url,
                original_query = html.escape(renderer['originalQuery']['simpleText']),
            )
            continue
        result_list_html += html_common.renderer_html(renderer, current_query_string=env['QUERY_STRING'])
        
    page = int(page)
    if page <= 5:
        page_start = 1
        page_end = min(9, estimated_pages)
    else:
        page_start = page - 4
        page_end = min(page + 4, estimated_pages)
        
    
    result = Template(yt_search_results_template).substitute(
        header              = html_common.get_header(query),
        results             = result_list_html, 
        page_title          = query + " - Search", 
        search_box_value    = html.escape(query),
        number_of_results   = '{:,}'.format(estimated_results),
        number_of_pages     = '{:,}'.format(estimated_pages),
        page_buttons        = html_common.page_buttons_html(page, estimated_pages, util.URL_ORIGIN + "/search", env['QUERY_STRING']),
        corrections         = corrections
        )
    return result.encode('utf-8')
