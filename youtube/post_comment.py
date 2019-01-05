# Contains functions having to do with posting/editing/deleting comments

import urllib
import json
from youtube import common, proto, comments, accounts
import re
import traceback
import settings
import os

def _post_comment(text, video_id, session_token, cookiejar):
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 10_3_1 like Mac OS X) AppleWebKit/603.1.30 (KHTML, like Gecko) Version/10.0 Mobile/14E304 Safari/602.1',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'X-YouTube-Client-Name': '2',
        'X-YouTube-Client-Version': '2.20180823',
        'Content-Type': 'application/x-www-form-urlencoded',
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


    content = common.fetch_url("https://m.youtube.com/service_ajax?name=createCommentEndpoint", headers=headers, data=data, cookiejar_send=cookiejar)

    code = json.loads(content)['code']
    print("Comment posting code: " + code)
    return code
    '''with open('debug/post_comment_response', 'wb') as f:
        f.write(content)'''


def _post_comment_reply(text, video_id, parent_comment_id, session_token, cookiejar):
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 10_3_1 like Mac OS X) AppleWebKit/603.1.30 (KHTML, like Gecko) Version/10.0 Mobile/14E304 Safari/602.1',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'X-YouTube-Client-Name': '2',
        'X-YouTube-Client-Version': '2.20180823',
        'Content-Type': 'application/x-www-form-urlencoded',
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

    content = common.fetch_url("https://m.youtube.com/service_ajax?name=createCommentReplyEndpoint", headers=headers, data=data, cookiejar_send=cookiejar)

    code = json.loads(content)['code']
    print("Comment posting code: " + code)
    return code
    '''with open('debug/post_comment_response', 'wb') as f:
        f.write(content)'''

def _delete_comment(video_id, comment_id, author_id, session_token, cookiejar):
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 10_3_1 like Mac OS X) AppleWebKit/603.1.30 (KHTML, like Gecko) Version/10.0 Mobile/14E304 Safari/602.1',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'X-YouTube-Client-Name': '2',
        'X-YouTube-Client-Version': '2.20180823',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    action = proto.uint(1,6) + proto.string(3, comment_id) + proto.string(5, video_id) + proto.string(9, author_id)
    action = proto.percent_b64encode(action).decode('ascii')

    sej = json.dumps({"clickTrackingParams":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=","commandMetadata":{"webCommandMetadata":{"url":"/service_ajax","sendPost":True}},"performCommentActionEndpoint":{"action":action}})

    data_dict = {
        'sej': sej,
        'session_token': session_token,
    }
    data = urllib.parse.urlencode(data_dict).encode()

    content = common.fetch_url("https://m.youtube.com/service_ajax?name=performCommentActionEndpoint", headers=headers, data=data, cookiejar_send=cookiejar)
    code = json.loads(content)['code']
    print("Comment deletion code: " + code)
    return code

xsrf_token_regex = re.compile(r'''XSRF_TOKEN"\s*:\s*"([\w-]*(?:=|%3D){0,2})"''')
def get_session_token(video_id, cookiejar):
    ''' Get session token for a video. This is required in order to post/edit/delete comments. This will modify cookiejar with cookies from youtube required for commenting'''
    # youtube-dl uses disable_polymer=1 which uses a different request format which has an obfuscated javascript algorithm to generate a parameter called "bgr"
    # Tokens retrieved from disable_polymer pages only work with that format. Tokens retrieved on mobile only work using mobile requests
    # Additionally, tokens retrieved without sending the same cookie won't work. So this is necessary even if the bgr and stuff was reverse engineered.
    headers = {'User-Agent': common.mobile_user_agent}
    mobile_page = common.fetch_url('https://m.youtube.com/watch?v=' + video_id, headers, report_text="Retrieved session token for comment", cookiejar_send=cookiejar, cookiejar_receive=cookiejar).decode()
    match = xsrf_token_regex.search(mobile_page)
    if match:
        return match.group(1).replace("%3D", "=")
    else:
        raise Exception("Couldn't find xsrf_token")

def delete_comment(env, start_response):
    fields = env['fields']
    video_id = fields['video_id'][0]
    cookiejar = accounts.account_cookiejar(fields['channel_id'][0])
    token = get_session_token(video_id, cookiejar)

    code = _delete_comment(video_id, fields['comment_id'][0], fields['author_id'][0], token, cookiejar)

    if code == "SUCCESS":
        start_response('303 See Other',  [('Location', common.URL_ORIGIN + '/comment_delete_success'),] )
    else:
        start_response('303 See Other',  [('Location', common.URL_ORIGIN + '/comment_delete_fail'),] )

def post_comment(env, start_response):
    parameters = env['fields']
    video_id = parameters['video_id'][0]
    channel_id = parameters['channel_id'][0]
    cookiejar = accounts.account_cookiejar(channel_id)
    token = get_session_token(video_id, cookiejar)

    if 'parent_id' in parameters:
        code = _post_comment_reply(parameters['comment_text'][0], parameters['video_id'][0], parameters['parent_id'][0], token, cookiejar)
        start_response('303 See Other',  (('Location', common.URL_ORIGIN + '/comments?' + env['QUERY_STRING']),) )

    else:
        code = _post_comment(parameters['comment_text'][0], parameters['video_id'][0], token, cookiejar)
        start_response('303 See Other',  (('Location', common.URL_ORIGIN + '/comments?ctoken=' + comments.make_comment_ctoken(video_id, sort=1)),) )

    return b''

def get_delete_comment_page(env, start_response):
    start_response('200 OK', [('Content-type','text/html'),])
    parameters = env['fields']

    style = '''
    main{
        display: grid;
        grid-template-columns: minmax(0px, 3fr) 640px 40px 500px minmax(0px,2fr);
        align-content: start;
    }
    main > div, main > form{
        margin-top:20px;
        grid-column:2;
    }
    '''

    page = '''
    <div>Are you sure you want to delete this comment?</div>
    <form action="" method="POST">'''
    for parameter in ('video_id', 'channel_id', 'author_id', 'comment_id'):
        page += '''\n        <input type="hidden" name="''' + parameter + '''" value="''' + parameters[parameter][0] + '''">'''
    page += '''
        <input type="submit" value="Yes, delete it">
    </form>'''
    return common.yt_basic_template.substitute(
        page_title = "Delete comment?",
        style = style,
        header = common.get_header(),
        page = page,
    ).encode('utf-8')

def get_post_comment_page(env, start_response):
    start_response('200 OK', [('Content-type','text/html'),])
    parameters = env['fields']
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
    justify-content:start;
}'''
    if parent_id:   # comment reply
        comment_box = comments.comment_box_template.substitute(
            form_action = common.URL_ORIGIN + '/comments?parent_id=' + parent_id + "&video_id=" + video_id,
            video_id_input = '',
            post_text = "Post reply",
            options=comments.comment_box_account_options(),
        )
    else:
        comment_box = comments.comment_box_template.substitute(
            form_action = common.URL_ORIGIN + '/post_comment',
            video_id_input = '''<input type="hidden" name="video_id" value="''' + video_id + '''">''',
            post_text = "Post comment",
            options=comments.comment_box_account_options(),
        )
        
    page = '''<div class="left">\n''' + comment_box + '''</div>\n'''
    return common.yt_basic_template.substitute(
        page_title = "Post comment reply" if parent_id else "Post a comment",
        style = style,
        header = common.get_header(),
        page = page,
    ).encode('utf-8')