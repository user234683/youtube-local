import json
import urllib.parse
import subprocess
import os
import re
import tempfile
import time
import settings
try:
    from yt_dlp_ejs.yt import solver
    has_solver = True
except ImportError:
    has_solver = False
from youtube.util import fetch_url
from youtube.pot_provider import get_po_token

def get_js_runtime():
    supported_runtimes = [ 'deno', 'bun', 'node' ]
    for js_runtime in supported_runtimes:
        try:
            result = subprocess.run([js_runtime, '--version'], check=True, capture_output=True)
            print(f"Using runtime: {js_runtime} {result.stdout.decode('utf-8')}")
            return js_runtime
        except Exception as err:
            pass
    return None

js_runtime = get_js_runtime()
js_decryption_possible = has_solver and js_runtime is not None

if not js_decryption_possible:
    print('Warning: js client is not usable, will fall back to non js client for player api requests.')

def get_player_info(video_id):
    iframe_api = 'https://www.youtube.com/iframe_api'+f'?videoId={video_id}'
    iframe_response = fetch_url(iframe_api)
    player_version_re = re.compile(r'player\\?/([0-9a-fA-F]{8})\\?/')
    player_version_search = re.search(player_version_re, iframe_response.decode("utf-8"))
    player_version = player_version_search.group(1)
    player_url = f'https://www.youtube.com/s/player/{player_version}/player_ias.vflset/en_US/base.js'
    base_js_cache = os.path.join(settings.data_dir, f'base_{player_version}.js')
    if not os.path.exists(base_js_cache):
        print(f'Downloading player: base_{player_version}.js')
        player_content = fetch_url(player_url)
        if not os.path.isdir(settings.data_dir):
            os.makedirs(settings.data_dir)
        with open(base_js_cache, 'wb') as f:
            f.write(player_content)
    else:
        print(f'Using cached player: base_{player_version}.js')
        with open(base_js_cache, 'rb') as f:
            player_content = f.read()
    sts_re = re.compile(r'(?:signatureTimestamp|sts)\s*:\s*(?P<sts>[0-9]{5})')
    sts_search = re.search(sts_re, player_content.decode('utf-8'))
    sts = sts_search.groupdict().get('sts')
    return player_version, sts

def extract_signatures(json_resp):
    all_formats = list(json_resp.get('streamingData', {}).get('formats', [])+json_resp.get('streamingData', {}).get('adaptiveFormats', []))
    nsig_list = []
    sig_list = []
    sp = ''
    formats = []
    for item in all_formats:
        if item.get('signatureCipher'):
            parsed_signature_cipher = urllib.parse.parse_qs(item['signatureCipher'])
            url = parsed_signature_cipher.get('url')[0]
            s = parsed_signature_cipher.get('s')[0]
            item['s'] = s
            item['url'] = url
            item.pop('signatureCipher')
            if not sp:
                sp = parsed_signature_cipher.get('sp')[0]
            if s not in sig_list:
                sig_list.append(s)
            formats.append(item)
        elif item.get('url'):
            url = item['url']
            formats.append(item)
        if not formats:
            print('Error: no formats available to decrypt. YT requires SABR playback for this js client, which is not currently supported.')
        parsed_url = urllib.parse.urlparse(url)
        parsed_url_qs = urllib.parse.parse_qs(parsed_url.query)
        nsig = parsed_url_qs.get('n')[0]
        if nsig not in nsig_list:
            nsig_list.append(nsig)
    return nsig_list, sig_list, sp, formats

def decrypt_signatures(client, player_version, json_resp):
    if not has_solver:
        print('Warning: unable to perform signature decryption because yt-dlp-ejs is not installed')
        return json_resp
    start = time.perf_counter()
    nsig_list, sig_list, sp, formats = extract_signatures(json_resp)
    try:
        result = ejs_decrypt(player_version, nsig=nsig_list, sig=sig_list)
    except Exception as err:
        print(f'An exception occured:\n{err}')
        return None
    # Query transformation steps
    video_id = json_resp['videoDetails']['videoId']
    po_token = get_po_token(client, video_id)
    if po_token is None:
        print('Warning: unable to obtain po_token, stream will be unplayable after one minute')
    for item in formats:
        parsed_url = urllib.parse.urlparse(item['url'])
        query_param = urllib.parse.parse_qsl(parsed_url.query)
        query_param_dict = {}
        for k, v in query_param:
            query_param_dict[k] = v
        nsig = query_param_dict['n']
        sig = item.get('s')
        # Actual replacement of signature values
        # print(f"{ item['itag']} n: {query_param_dict['n']} → {result[0]['data'].get(nsig)}")
        query_param_dict['n'] = result[0]['data'].get(nsig)
        # sp value is 'sig'
        if sig and sp:
            # print(f"{ item['itag']} s: {sig} → {result[1]['data'].get(sig)}")
            query_param_dict[sp] = result[1]['data'].get(sig)
        if po_token:
            query_param_dict['pot'] = po_token
        item['url'] = urllib.parse.urlunparse(
                (parsed_url.scheme,
                 parsed_url.hostname,
                 parsed_url.path,
                 '',
                 urllib.parse.urlencode(query_param_dict),
                 parsed_url.fragment))
    end = time.perf_counter()
    print(f"Decrypted signatures for {len(formats)} formats in {end - start:.2f} s")
    json_results = dict(json_resp)
    json_results['streamingData'].pop('adaptiveFormats')
    json_results['streamingData']['formats'] = formats
    json_results['streamingData']['adaptiveFormats'] = formats
    return json_results

def ejs_decrypt(player_version, nsig, sig=[]):
    if not js_runtime:
        raise NameError("No supported js_runtime is found!\nSupported runtimes: deno, bun, node.")
    player_cache = os.path.join(settings.data_dir, f'base_{player_version}.js')
    processed_cache = os.path.join(settings.data_dir, f'processed_{player_version}.js')
    code_fd, code_tempfile = tempfile.mkstemp(prefix='yt-ejs-', suffix='.js')
    if not os.path.isfile(processed_cache):
        with open(player_cache, 'rb') as file:
            player = file.read().decode('utf-8')
            has_preprocessed = False
    else:
        with open(processed_cache, 'rb') as file:
            preprocessed_player = file.read().decode('utf-8')
            has_preprocessed = True
    payload = {}
    if has_preprocessed:
        payload['type'] = 'preprocessed'
        payload['preprocessed_player'] = preprocessed_player
    else:
        payload['type'] = 'player'
        payload['player'] = player
        payload['output_preprocessed'] = True
    payload['requests'] = [
    {'type': 'n', 'challenges': nsig},
    ]
    if sig:
        payload['requests'].append(
    {'type': 'sig', 'challenges': sig}
    )

    jscode = f'''{solver.lib()}
    Object.assign(globalThis, lib);
    {solver.core()}
    var result = jsc({json.dumps(payload)});
    console.log(JSON.stringify(result));
    '''
    with os.fdopen(code_fd, 'wb') as file:
        file.write(jscode.encode('utf-8'))
    result = subprocess.run([js_runtime, code_tempfile], capture_output=True)
    result.check_returncode()
    result_json = json.loads(result.stdout.decode('utf-8'))
    if not has_preprocessed:
        with open(processed_cache, 'wb') as file:
            file.write(result_json['preprocessed_player'].encode('utf-8'))
        result_json.pop('preprocessed_player')
    actual_result = result_json['responses']
    os.remove(code_tempfile)
    return actual_result
