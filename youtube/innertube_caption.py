import base64
from youtube import util, proto
from youtube.yt_data_extract import deep_get
import urllib.parse
import json
import traceback

def generate_caption_params(video_id: str = '', lang: str = 'en', auto_generated: bool = False):
    lang_param = {
        1: [2, b'asr' if auto_generated else b''],
        2: [2, lang.encode()],
        3: [2, b''],
    }
    payload_param = {
        1: [2, video_id.encode()],
        2: [2, ('base64', lang_param)],
        3: [0, 1],
        5: [2, b'engagement-panel-searchable-transcript-search-panel'],
        6: [0, 1],
        7: [0, 1],
        8: [0, 1],
    }
    payload_protobuf = proto._make_protobuf(payload_param)
    return urllib.parse.quote(base64.urlsafe_b64encode(payload_protobuf).decode())

def get_caption_json_resp(video_id, lang: str = 'en', auto_generated: bool = False):
    params = generate_caption_params(video_id, lang, auto_generated)
    payload = {'params': params}
    try:
        resp = util.call_youtube_api('web', 'get_transcript', payload)
    except Exception as e:
        print(f'Error fetching captions via innertube: {e}')
        traceback.print_exc()
        return None

    if resp:
        caption_data = json.loads(resp)
    else:
        return None
    vtt_body = deep_get(caption_data, 'actions', 0, 'updateEngagementPanelAction', 'content', 'transcriptRenderer', 'content', 'transcriptSearchPanelRenderer', 'body', 'transcriptSegmentListRenderer', 'initialSegments')
    if vtt_body:
        return caption_data
    else:
        print('Unable to find vtt_body, retrying request with continuation params')
        continuation_submenu = deep_get(caption_data, 'actions', 0, 'updateEngagementPanelAction', 'content', 'transcriptRenderer', 'content', 'transcriptSearchPanelRenderer', 'footer', 'transcriptFooterRenderer', 'languageMenu', 'sortFilterSubMenuRenderer', 'subMenuItems')
        if not continuation_submenu:
            print('No continuation submenu found in response')
            return None
        for item in continuation_submenu:
            if lang in item['title']:
                params_new = deep_get(item, 'continuation', 'reloadContinuationData', 'continuation')
                retry_payload = {'params': params_new}
                try:
                    resp_new = util.call_youtube_api('web', 'get_transcript', retry_payload)
                except Exception as e:
                    print(f'Error fetching captions continuation: {e}')
                    return None
                caption_data_new = json.loads(resp_new)
                vtt_body_new = deep_get(caption_data_new, 'actions', 0, 'updateEngagementPanelAction', 'content', 'transcriptRenderer', 'content', 'transcriptSearchPanelRenderer', 'body', 'transcriptSegmentListRenderer', 'initialSegments')
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
    vtt_body = deep_get(caption_data, 'actions', 0, 'updateEngagementPanelAction', 'content', 'transcriptRenderer', 'content', 'transcriptSearchPanelRenderer', 'body', 'transcriptSegmentListRenderer', 'initialSegments')
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
            running_text = deep_get(vtt_item, 'snippet', 'runs', 0, 'text')
            webvtt_time_line = f'{start_time} --> {end_time}\n{running_text}\n'
            vtt_content.append(webvtt_time_line)

    vtt_txt = '\n'.join(vtt_content)
    return vtt_txt
