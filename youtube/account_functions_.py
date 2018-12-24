# Contains functions having to do with logging in or requiring that one is logged in

import urllib
import json
from youtube import common, proto, comments
import re
import traceback
import settings
import http.cookiejar

def _post_comment(text, video_id, session_token, cookie):
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 10_3_1 like Mac OS X) AppleWebKit/603.1.30 (KHTML, like Gecko) Version/10.0 Mobile/14E304 Safari/602.1',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'X-YouTube-Client-Name': '2',
        'X-YouTube-Client-Version': '2.20180823',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Cookie': cookie,
    }

    comment_params = proto.string(2, video_id) + proto.nested(5, proto.uint(1, 0)) + proto.uint(10, 1)
    comment_params = proto.percent_b64encode(comment_params).decode('ascii')

    sej = json.dumps({"clickTrackingParams":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=", "commandMetadata":{"webCommandMetadata":{"url":"/service_ajax","sendPost":True}},"createCommentEndpoint":{"createCommentParams": comment_params}})

    data_dict = {
        'comment_text': text,
        'sej': sej,
        'session_token': session_token,
    }
    data = urllib.parse.urlencode(data_dict).encode()

    req = urllib.request.Request("https://m.youtube.com/service_ajax?name=createCommentEndpoint", headers=headers, data=data)
    response = urllib.request.urlopen(req, timeout = 5)
    content = response.read()
    content = common.decode_content(content, response.getheader('Content-Encoding', default='identity'))
    code = json.loads(content)['code']
    print("Comment posting code: " + code)
    return code
    '''with open('debug/post_comment_response', 'wb') as f:
        f.write(content)'''


def _post_comment_reply(text, video_id, parent_comment_id, session_token, cookie):
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 10_3_1 like Mac OS X) AppleWebKit/603.1.30 (KHTML, like Gecko) Version/10.0 Mobile/14E304 Safari/602.1',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'X-YouTube-Client-Name': '2',
        'X-YouTube-Client-Version': '2.20180823',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Cookie': cookie,
    }

    comment_params = proto.string(2, video_id) + proto.string(4, parent_comment_id) + proto.nested(5, proto.uint(1, 0)) + proto.uint(6,0) + proto.uint(10, 1)
    comment_params = proto.percent_b64encode(comment_params).decode('ascii')

    sej = json.dumps({"clickTrackingParams":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=", "commandMetadata":{"webCommandMetadata":{"url":"/service_ajax","sendPost":True}},"createCommentReplyEndpoint":{"createReplyParams": comment_params}})

    data_dict = {
        'comment_text': text,
        'sej': sej,
        'session_token': session_token,
    }
    data = urllib.parse.urlencode(data_dict).encode()

    req = urllib.request.Request("https://m.youtube.com/service_ajax?name=createCommentReplyEndpoint", headers=headers, data=data)
    response = urllib.request.urlopen(req, timeout = 5)
    content = response.read()
    content = common.decode_content(content, response.getheader('Content-Encoding', default='identity'))
    code = json.loads(content)['code']
    print("Comment posting code: " + code)
    return code
    '''with open('debug/post_comment_response', 'wb') as f:
        f.write(content)'''

def delete_comment(video_id, comment_id, author_id, session_token, cookie):
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 10_3_1 like Mac OS X) AppleWebKit/603.1.30 (KHTML, like Gecko) Version/10.0 Mobile/14E304 Safari/602.1',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'X-YouTube-Client-Name': '2',
        'X-YouTube-Client-Version': '2.20180823',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Cookie': cookie,
    }
    action = proto.uint(1,6) + proto.string(3, comment_id) + proto.string(5, video_id) + proto.string(9, author_id)
    action = proto.percent_b64encode(action).decode('ascii')

    sej = json.dumps({"clickTrackingParams":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=","commandMetadata":{"webCommandMetadata":{"url":"/service_ajax","sendPost":True}},"performCommentActionEndpoint":{"action":action}})

    data_dict = {
        'sej': sej,
        'session_token': session_token,
    }
    data = urllib.parse.urlencode(data_dict).encode()

    req = urllib.request.Request("https://m.youtube.com/service_ajax?name=performCommentActionEndpoint", headers=headers, data=data)
    response = urllib.request.urlopen(req, timeout = 5)
    content = response.read()

xsrf_token_regex = re.compile(r'''XSRF_TOKEN"\s*:\s*"([\w-]*(?:=|%3D){0,2})"''')
def post_comment(query_string, fields):
    with open(os.path.join(settings.data_dir, 'cookie.txt'), 'r', encoding='utf-8') as f:
        cookie_data = f.read()

    parameters = urllib.parse.parse_qs(query_string)
    try:
        video_id = fields['video_id'][0]
    except KeyError:
        video_id = parameters['video_id'][0]

    # Get session token for mobile
    # youtube-dl uses disable_polymer=1 which uses a different request format which has an obfuscated javascript algorithm to generate a parameter called "bgr"
    # Tokens retrieved from disable_polymer pages only work with that format. Tokens retrieved on mobile only work using mobile requests
    # Additionally, tokens retrieved without sending the same cookie won't work. So this is necessary even if the bgr and stuff was reverse engineered.
    headers = {'User-Agent': common.mobile_user_agent,
    'Cookie': cookie_data,}
    mobile_page = common.fetch_url('https://m.youtube.com/watch?v=' + video_id, headers, report_text="Retrieved session token for comment").decode()
    match = xsrf_token_regex.search(mobile_page)
    if match:
        token = match.group(1).replace("%3D", "=")
    else:
        raise Exception("Couldn't find xsrf_token")

    if 'parent_id' in parameters:
        code = _post_comment_reply(fields['comment_text'][0], parameters['video_id'][0], parameters['parent_id'][0], token, cookie_data)
        try:
            response = comments.get_comments_page(query_string)
        except socket.error as e:
            traceback.print_tb(e.__traceback__)
            return b'Refreshing comment page yielded error 502 Bad Gateway.\nPost comment status code: ' + code.encode('ascii')
        except Exception as e:
            traceback.print_tb(e.__traceback__)
            return b'Refreshing comment page yielded error 500 Internal Server Error.\nPost comment status code: ' + code.encode('ascii')
        return response
    else:
        code = _post_comment(fields['comment_text'][0], fields['video_id'][0], token, cookie_data)
        try:
            response = comments.get_comments_page('ctoken=' + comments.make_comment_ctoken(video_id, sort=1))
        except socket.error as e:
            traceback.print_tb(e.__traceback__)
            return b'Refreshing comment page yielded error 502 Bad Gateway.\nPost comment status code: ' + code.encode('ascii')
        except Exception as e:
            traceback.print_tb(e.__traceback__)
            return b'Refreshing comment page yielded error 500 Internal Server Error.\nPost comment status code: ' + code.encode('ascii')
        return response

def get_post_comment_page(query_string):
    parameters = urllib.parse.parse_qs(query_string)
    video_id = parameters['video_id'][0]
    parent_id = common.default_multi_get(parameters, 'parent_id', 0, default='')
    
    style = ''' main{
    display: grid;
    grid-template-columns: 3fr 2fr;
}
.left{
    display:grid;
    grid-template-columns: 1fr 640px;
}
textarea{
    width: 460px;
    height: 85px;
}
.comment-form{
    grid-column:2;
}'''
    if parent_id:   # comment reply
        comment_box = comments.comment_box_template.substitute(
            form_action = common.URL_ORIGIN + '/comments?parent_id=' + parent_id + "&video_id=" + video_id,
            video_id_input = '',
            post_text = "Post reply",
        )
    else:
        comment_box = comments.comment_box_template.substitute(
            form_action = common.URL_ORIGIN + '/comments?ctoken=' + comments.make_comment_ctoken(video_id, sort=1).replace("=", "%3D"),
            video_id_input = '''<input type="hidden" name="video_id" value="''' + video_id + '''">''',
            post_text = "Post comment",
        )
        
    page = '''<div class="left">\n''' + comment_box + '''</div>\n'''
    return common.yt_basic_template.substitute(
        page_title = "Post comment reply" if parent_id else "Post a comment",
        style = style,
        header = common.get_header(),
        page = page,
    )



# ---------------------------------
# Code ported from youtube-dl
# ---------------------------------
from html.parser import HTMLParser as compat_HTMLParser
import http.client as compat_http_client

class HTMLAttributeParser(compat_HTMLParser):
    """Trivial HTML parser to gather the attributes for a single element"""
    def __init__(self):
        self.attrs = {}
        compat_HTMLParser.__init__(self)

    def handle_starttag(self, tag, attrs):
        self.attrs = dict(attrs)

def extract_attributes(html_element):
    """Given a string for an HTML element such as
    <el
         a="foo" B="bar" c="&98;az" d=boz
         empty= noval entity="&amp;"
         sq='"' dq="'"
    >
    Decode and return a dictionary of attributes.
    {
        'a': 'foo', 'b': 'bar', c: 'baz', d: 'boz',
        'empty': '', 'noval': None, 'entity': '&',
        'sq': '"', 'dq': '\''
    }.
    NB HTMLParser is stricter in Python 2.6 & 3.2 than in later versions,
    but the cases in the unit test will work for all of 2.6, 2.7, 3.2-3.5.
    """
    parser = HTMLAttributeParser()
    parser.feed(html_element)
    parser.close()

    return parser.attrs

def _hidden_inputs(html):
    html = re.sub(r'<!--(?:(?!<!--).)*-->', '', html)
    hidden_inputs = {}
    for input in re.findall(r'(?i)(<input[^>]+>)', html):
        attrs = extract_attributes(input)
        if not input:
            continue
        if attrs.get('type') not in ('hidden', 'submit'):
            continue
        name = attrs.get('name') or attrs.get('id')
        value = attrs.get('value')
        if name and value is not None:
            hidden_inputs[name] = value
    return hidden_inputs

def try_get(src, getter, expected_type=None):
    if not isinstance(getter, (list, tuple)):
        getter = [getter]
    for get in getter:
        try:
            v = get(src)
        except (AttributeError, KeyError, TypeError, IndexError):
            pass
        else:
            if expected_type is None or isinstance(v, expected_type):
                return v

def remove_start(s, start):
    return s[len(start):] if s is not None and s.startswith(start) else s

_LOGIN_URL = 'https://accounts.google.com/ServiceLogin'
_TWOFACTOR_URL = 'https://accounts.google.com/signin/challenge'

_LOOKUP_URL = 'https://accounts.google.com/_/signin/sl/lookup'
_CHALLENGE_URL = 'https://accounts.google.com/_/signin/sl/challenge'
_TFA_URL = 'https://accounts.google.com/_/signin/challenge?hl=en&TL={0}'
def _login(username, password, cookie_jar):
    """
    Attempt to log in to YouTube.
    True is returned if successful or skipped.
    False is returned if login failed.

    Taken from youtube-dl
    """
    login_page = common.fetch_url(_LOGIN_URL, report_text='Downloaded login page', cookie_jar_receive=cookie_jar).decode('utf-8')

    if login_page is False:
        return

    login_form = _hidden_inputs(login_page)

    def req(url, f_req, note, errnote):
        data = login_form.copy()
        data.update({
            'pstMsg': 1,
            'checkConnection': 'youtube',
            'checkedDomains': 'youtube',
            'hl': 'en',
            'deviceinfo': '[null,null,null,[],null,"US",null,null,[],"GlifWebSignIn",null,[null,null,[]]]',
            'f.req': json.dumps(f_req),
            'flowName': 'GlifWebSignIn',
            'flowEntry': 'ServiceLogin',
        })
        headers={
            'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8',
            'Google-Accounts-XSRF': 1,
        }
        result = common.fetch_url(url, headers, report_text=note, data=data, cookie_jar_send=cookie_jar, cookie_jar_receive=cookie_jar)
        result = re.sub(r'^[^\[]*', '', result)
        return json.loads(result)

    def warn(message):
        print("Login: " + message)

    lookup_req = [
        username,
        None, [], None, 'US', None, None, 2, False, True,
        [
            None, None,
            [2, 1, None, 1,
             'https://accounts.google.com/ServiceLogin?passive=true&continue=https%3A%2F%2Fwww.youtube.com%2Fsignin%3Fnext%3D%252F%26action_handle_signin%3Dtrue%26hl%3Den%26app%3Ddesktop%26feature%3Dsign_in_button&hl=en&service=youtube&uilel=3&requestPath=%2FServiceLogin&Page=PasswordSeparationSignIn',
             None, [], 4],
            1, [None, None, []], None, None, None, True
        ],
        username,
    ]

    lookup_results = req(
        _LOOKUP_URL, lookup_req,
        'Looking up account info', 'Unable to look up account info')

    if lookup_results is False:
        return False

    user_hash = try_get(lookup_results, lambda x: x[0][2], str)
    if not user_hash:
        warn('Unable to extract user hash')
        return False

    challenge_req = [
        user_hash,
        None, 1, None, [1, None, None, None, [password, None, True]],
        [
            None, None, [2, 1, None, 1, 'https://accounts.google.com/ServiceLogin?passive=true&continue=https%3A%2F%2Fwww.youtube.com%2Fsignin%3Fnext%3D%252F%26action_handle_signin%3Dtrue%26hl%3Den%26app%3Ddesktop%26feature%3Dsign_in_button&hl=en&service=youtube&uilel=3&requestPath=%2FServiceLogin&Page=PasswordSeparationSignIn', None, [], 4],
            1, [None, None, []], None, None, None, True
        ]]

    challenge_results = req(
        _CHALLENGE_URL, challenge_req,
        'Logging in', 'Unable to log in')

    if challenge_results is False:
        return

    login_res = try_get(challenge_results, lambda x: x[0][5], list)
    if login_res:
        login_msg = try_get(login_res, lambda x: x[5], str)
        warn(
            'Unable to login: %s' % 'Invalid password'
            if login_msg == 'INCORRECT_ANSWER_ENTERED' else login_msg)
        return False

    res = try_get(challenge_results, lambda x: x[0][-1], list)
    if not res:
        warn('Unable to extract result entry')
        return False

    login_challenge = try_get(res, lambda x: x[0][0], list)
    if login_challenge:
        challenge_str = try_get(login_challenge, lambda x: x[2], str)
        if challenge_str == 'TWO_STEP_VERIFICATION':
            # SEND_SUCCESS - TFA code has been successfully sent to phone
            # QUOTA_EXCEEDED - reached the limit of TFA codes
            status = try_get(login_challenge, lambda x: x[5], str)
            if status == 'QUOTA_EXCEEDED':
                warn('Exceeded the limit of TFA codes, try later')
                return False

            tl = try_get(challenge_results, lambda x: x[1][2], str)
            if not tl:
                warn('Unable to extract TL')
                return False

            tfa_code = self._get_tfa_info('2-step verification code')

            if not tfa_code:
                warn(
                    'Two-factor authentication required. Provide it either interactively or with --twofactor <code>'
                    '(Note that only TOTP (Google Authenticator App) codes work at this time.)')
                return False

            tfa_code = remove_start(tfa_code, 'G-')

            tfa_req = [
                user_hash, None, 2, None,
                [
                    9, None, None, None, None, None, None, None,
                    [None, tfa_code, True, 2]
                ]]

            tfa_results = req(
                _TFA_URL.format(tl), tfa_req,
                'Submitting TFA code', 'Unable to submit TFA code')

            if tfa_results is False:
                return False

            tfa_res = try_get(tfa_results, lambda x: x[0][5], list)
            if tfa_res:
                tfa_msg = try_get(tfa_res, lambda x: x[5], str)
                warn(
                    'Unable to finish TFA: %s' % 'Invalid TFA code'
                    if tfa_msg == 'INCORRECT_ANSWER_ENTERED' else tfa_msg)
                return False

            check_cookie_url = try_get(
                tfa_results, lambda x: x[0][-1][2], str)
        else:
            CHALLENGES = {
                'LOGIN_CHALLENGE': "This device isn't recognized. For your security, Google wants to make sure it's really you.",
                'USERNAME_RECOVERY': 'Please provide additional information to aid in the recovery process.',
                'REAUTH': "There is something unusual about your activity. For your security, Google wants to make sure it's really you.",
            }
            challenge = CHALLENGES.get(
                challenge_str,
                '%s returned error %s.' % ('youtube', challenge_str))
            warn('%s\nGo to https://accounts.google.com/, login and solve a challenge.' % challenge)
            return False
    else:
        check_cookie_url = try_get(res, lambda x: x[2], str)

    if not check_cookie_url:
        warn('Unable to extract CheckCookie URL')
        return False

    try:
        check_cookie_results = common.fetch_url(check_cookie_url, report-text="Checked cookie", cookie_jar_send=cookie_jar, cookie_jar_receive=cookie_jar).decode('utf-8')
    except (urllib.error.URLError, compat_http_client.HTTPException, socket.error) as err:
        return False

    if 'https://myaccount.google.com/' not in check_cookie_results:
        warn('Unable to log in')
        return False

    return True
