from youtube import util, yt_data_extract, proto, local_playlist
from youtube import yt_app

import json
import urllib
import base64
from math import ceil
from flask import request
import flask

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


@yt_app.route('/search')
def get_search_page():
    if len(request.args) == 0:
        return flask.render_template('base.html', title="Search")

    if 'query' not in request.args:
        abort(400)

    query = request.args.get("query")
    page = request.args.get("page", "1")
    autocorrect = int(request.args.get("autocorrect", "1"))
    sort = int(request.args.get("sort", "0"))
    filters = {}
    filters['time'] = int(request.args.get("time", "0"))
    filters['type'] = int(request.args.get("type", "0"))
    filters['duration'] = int(request.args.get("duration", "0"))
    info = get_search_json(query, page, autocorrect, sort, filters)
    
    estimated_results = int(info[1]['response']['estimatedResults'])
    estimated_pages = ceil(estimated_results/20)
    results = info[1]['response']['contents']['twoColumnSearchResultsRenderer']['primaryContents']['sectionListRenderer']['contents'][0]['itemSectionRenderer']['contents']

    parsed_results = []
    corrections = {'type': None}
    for renderer in results:
        type = list(renderer.keys())[0]
        if type == 'shelfRenderer':
            continue
        if type == 'didYouMeanRenderer':
            renderer = renderer[type]
            corrected_query_string = parameters.copy()
            corrected_query_string['query'] = [renderer['correctedQueryEndpoint']['searchEndpoint']['query']]
            corrected_query_url = util.URL_ORIGIN + '/search?' + urllib.parse.urlencode(corrected_query_string, doseq=True)

            corrections = {
                'type': 'did_you_mean',
                'corrected_query': yt_data_extract.format_text_runs(renderer['correctedQuery']['runs']),
                'corrected_query_url': corrected_query_url,
            }
            continue
        if type == 'showingResultsForRenderer':
            renderer = renderer[type]
            no_autocorrect_query_string = parameters.copy()
            no_autocorrect_query_string['autocorrect'] = ['0']
            no_autocorrect_query_url = util.URL_ORIGIN + '/search?' + urllib.parse.urlencode(no_autocorrect_query_string, doseq=True)

            corrections = {
                'type': 'showing_results_for',
                'corrected_query': yt_data_extract.format_text_runs(renderer['correctedQuery']['runs']),
                'original_query_url': no_autocorrect_query_url,
                'original_query': renderer['originalQuery']['simpleText'],
            }
            continue

        info = yt_data_extract.parse_info_prepare_for_html(renderer)
        if info['type'] != 'unsupported':
            parsed_results.append(info)

    return flask.render_template('search.html',
        header_playlist_names = local_playlist.get_playlist_names(),
        query = query,
        estimated_results = estimated_results,
        estimated_pages = estimated_pages,
        corrections = corrections,
        results = parsed_results,
        parameters_dictionary = request.args,
    )


