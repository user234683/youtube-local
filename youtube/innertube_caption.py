import base64
from youtube import util
import urllib.parse
import json
import blackboxprotobuf

def generate_caption_params(video_id: str = '', lang: str = 'en', auto_generated: bool = False):
    typedef_2 = {
            '1': {
                'name': 'kind',
                'type': 'string',
                },
            '2': {
                'name': 'language_code',
                'type': 'string',
                },
            '3': {
                'name': 'empty_string',
                'type': 'string',
                },
            }

    typedef = {
            '1': {
                'name': 'videoId',
                'type': 'string',
                },
            '2': {
                'name': 'lang_param',
                'type': 'string',
                },
            '3': {
                'name': 'varint_3',
                'type': 'int',
                },
            '5': {
                'name': 'fixed_string',
                'type': 'string',
                },
            '6': {
                'name': 'varint_6',
                'type': 'int',
                },

            '7': {
                'name': 'varint_7',
                'type': 'int',
                },
            '8': {
                'name': 'varint_8',
                'type': 'int',
                },
            }

    def encode_to_protobuf(message, typedef):
        result = blackboxprotobuf.encode_message(message, typedef)
        return result

    language_code = lang
    if not auto_generated:
        kind = ""
    else:
        kind = "asr"

    two_payload = {
            'kind': kind,
            'language_code': language_code,
            'empty_string': ''
    }

    two_protobuf = encode_to_protobuf(two_payload, typedef_2)
    base64_encoded_lang = urllib.parse.quote(base64.b64encode(two_protobuf).decode())
    one_payload = {
            'videoId': video_id,
            'lang_param': base64_encoded_lang,
            'varint_3': 1,
            'fixed_string': 'engagement-panel-searchable-transcript-search-panel',
            'varint_6': 0,
            'varint_7': 0,
            'varint_8': 0,
            }

    one_protobuf = encode_to_protobuf(one_payload, typedef)

    params = base64.b64encode(one_protobuf).decode()
    return params

def get_caption_json_resp(video_id, lang: str = 'en', auto_generated: bool = False):
    unquoted_params = generate_caption_params(video_id, lang, auto_generated)
    params = urllib.parse.quote(unquoted_params)
    ytcfg = util.INNERTUBE_CLIENTS['web']
    ua = util.desktop_user_agent
    visitor_data = util.get_visitor_data()
    header = { 'User-Agent': util.desktop_user_agent, 'X-Goog-Visitor-Id': visitor_data }
    payload = {}
    ctx = ytcfg['INNERTUBE_CONTEXT']
    payload['context'] = ctx
    payload['params'] = params
    youtube_home = 'https://www.youtube.com'
    caption_api = f"{youtube_home}/youtubei/v1/get_transcript"
    resp = util.fetch_url(caption_api, headers=header, data=json.dumps(payload), report_text=f'Fetching captions for {video_id}')

    if resp:
        caption_data = json.loads(resp)
    else:
        return None
    vtt_body = caption_data['actions'][0]['updateEngagementPanelAction']['content']['transcriptRenderer']['content']['transcriptSearchPanelRenderer']['body']['transcriptSegmentListRenderer'].get('initialSegments')
    if vtt_body:
        return caption_data
    else:
        print('Unable to find vtt_body, retrying request with continuation params')
        continuation_submenu = caption_data['actions'][0]['updateEngagementPanelAction']['content']['transcriptRenderer']['content']['transcriptSearchPanelRenderer']['footer']['transcriptFooterRenderer']['languageMenu']['sortFilterSubMenuRenderer']['subMenuItems']
        for item in continuation_submenu:
            if lang in item['title']:
                params_new = item['continuation']['reloadContinuationData']['continuation']
                payload['params'] = params_new
                resp_new = util.fetch_url(caption_api, headers=header, data=json.dumps(payload), report_text=f'Fetching captions for {video_id}')
                caption_data_new = json.loads(resp_new.decode())
                vtt_body_new = caption_data_new['actions'][0]['updateEngagementPanelAction']['content']['transcriptRenderer']['content']['transcriptSearchPanelRenderer']['body']['transcriptSegmentListRenderer'].get('initialSegments')
                if vtt_body_new:
                    print('Got vtt_body from continuation request')
                else:
                    print('Still not getting vtt_body with continuation.\nReturning the new_caption_data as is.')
                return caption_data_new

def convert_milliseconds_to_hhmmss_optimized(ms):
    if not isinstance(ms, int):
        ms = int(ms)
    total_seconds = ms // 1000
    milliseconds = ms % 1000
    hours = total_seconds // 3600
    total_seconds %= 3600
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{hours:02}:{minutes:02}:{seconds:02}.{milliseconds:03}"

def webvtt_from_caption_data(caption_data: dict = {}):
    if not caption_data:
        return None
    vtt_body = caption_data['actions'][0]['updateEngagementPanelAction']['content']['transcriptRenderer']['content']['transcriptSearchPanelRenderer']['body']['transcriptSegmentListRenderer'].get('initialSegments')
    if not vtt_body:
        print('Unable to find vtt_body in the caption data')
        return 'WEBVTT\n'

    vtt_content = [ 'WEBVTT\n' ]

    for item in vtt_body:
        if item.get('transcriptSegmentRenderer'):
            vtt_item = item['transcriptSegmentRenderer']
            ms_to_vtt_time = convert_milliseconds_to_hhmmss_optimized
            start_time = ms_to_vtt_time(vtt_item['startMs'])
            end_time = ms_to_vtt_time(vtt_item['endMs'])
            running_text = vtt_item['snippet']['runs'][0]['text']
            webvtt_time_line = str.format("""{} --> {}\n{}\n""", start_time, end_time, running_text)
            vtt_content.append(webvtt_time_line)

    vtt_txt = '\n'.join(vtt_content)
    return vtt_txt
