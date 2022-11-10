from youtube import util, yt_data_extract, proto, local_playlist
from youtube import yt_app
import settings

import json
import urllib
import base64
import mimetypes
from flask import request
import flask
import os

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
    content = util.fetch_url(url, headers=headers, report_text="Got search results", debug_name='search_results')
    info = json.loads(content)
    return info


@yt_app.route('/results')
@yt_app.route('/search')
def get_search_page():
    query = request.args.get('search_query') or request.args.get('query')
    if query is None:
        return flask.render_template('base.html', title='Search')
    elif query.startswith('https://www.youtube.com') or query.startswith('https://www.youtu.be'):
         return flask.redirect(f'/{query}')

    page = request.args.get("page", "1")
    autocorrect = int(request.args.get("autocorrect", "1"))
    sort = int(request.args.get("sort", "0"))
    filters = {}
    filters['time'] = int(request.args.get("time", "0"))
    filters['type'] = int(request.args.get("type", "0"))
    filters['duration'] = int(request.args.get("duration", "0"))
    polymer_json = get_search_json(query, page, autocorrect, sort, filters)

    search_info = yt_data_extract.extract_search_info(polymer_json)
    if search_info['error']:
        return flask.render_template('error.html', error_message = search_info['error'])

    for extract_item_info in search_info['items']:
        util.prefix_urls(extract_item_info)
        util.add_extra_html_info(extract_item_info)

    corrections = search_info['corrections']
    if corrections['type'] == 'did_you_mean':
        corrected_query_string = request.args.to_dict(flat=False)
        corrected_query_string['search_query'] = [corrections['corrected_query']]
        corrections['corrected_query_url'] = util.URL_ORIGIN + '/results?' + urllib.parse.urlencode(corrected_query_string, doseq=True)
    elif corrections['type'] == 'showing_results_for':
        no_autocorrect_query_string = request.args.to_dict(flat=False)
        no_autocorrect_query_string['autocorrect'] = ['0']
        no_autocorrect_query_url = util.URL_ORIGIN + '/results?' + urllib.parse.urlencode(no_autocorrect_query_string, doseq=True)
        corrections['original_query_url'] = no_autocorrect_query_url

    return flask.render_template('search.html',
        header_playlist_names = local_playlist.get_playlist_names(),
        query = query,
        estimated_results = search_info['estimated_results'],
        estimated_pages = search_info['estimated_pages'],
        corrections = search_info['corrections'],
        results = search_info['items'],
        parameters_dictionary = request.args,
    )

@yt_app.route('/opensearch.xml')
def get_search_engine_xml():
    with open(os.path.join(settings.program_directory, 'youtube/opensearch.xml'), 'rb') as f:
        content = f.read().replace(b'$host_url',
                                   request.host_url.rstrip('/').encode())
        return flask.Response(content, mimetype='application/xml')
