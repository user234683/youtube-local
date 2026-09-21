from youtube.util import INNERTUBE_CLIENTS, fetch_url
import urllib.request
import json
import time
import settings

def get_po_token(client, identifier=''):
    proxy = ''
    if settings.route_tor > 0:
        proxy = f'socks5h://localhost:{settings.tor_port}'
    if not identifier:
        return None
    print(f'Generating po_token for {identifier}')
    start_time = time.perf_counter()
    client_context = INNERTUBE_CLIENTS[client]['INNERTUBE_CONTEXT']
    try:
        if proxy:
            # workaround for fetch_url which doesn't work with localhost if settings.route_tor is enabled.
            with urllib.request.urlopen('http://localhost:4416/ping') as resp:
                http_resp = resp.read()
        else:
            http_resp = fetch_url('http://localhost:4416/ping')
        ping_result = json.loads(http_resp.decode())
        print(f"Using bgutil server {ping_result['version']}")
        proxy_payload = {}
        if proxy:
            print(f'get_po_token: using tor/socks at {proxy}')
            proxy_payload = { 'proxy': proxy }
        payload = {
                'content_binding': identifier,
                'bypass_cache': True,
                'innertube_context': client_context,
                **proxy_payload
                }
        if not proxy:
            result = fetch_url('http://localhost:4416/get_pot', report_text=f'Getting po_token for {identifier} via bgutil server', headers={'Content-Type': 'application/json'}, data=json.dumps(payload))
        else:
            # Same workaround for fetch_url
            print(f'Getting po_token for {identifier} via bgutil server')
            req = urllib.request.Request(url='http://localhost:4416/get_pot', headers={'Content-Type': 'application/json'}, data=json.dumps(payload).encode('utf-8'))
            with urllib.request.urlopen(req) as resp:
                result = resp.read()
        result_json = json.loads(result.decode())
        po_token = result_json['poToken']
        end_time = time.perf_counter()
        print(f'Got po_token for {identifier} via bgutil server in { end_time - start_time:.2f} s')
        return po_token
    except Exception as err:
        print(f'Unable to generate po_token. Make sure that bgutil server is running on localhost:4416. Refer to https://github.com/Brainicism/bgutil-ytdlp-pot-provider for more details.\n{err}')
        return None
