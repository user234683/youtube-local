# Contains functions having to do with logging in or requiring that one is logged in
import urllib
import json
from youtube import common, proto, comments
import re
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
    '''with open('debug/post_comment_response', 'wb') as f:
        f.write(response.read())'''


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
    '''with open('debug/post_comment_response', 'wb') as f:
        f.write(response.read())'''



xsrf_token_regex = re.compile(r'''XSRF_TOKEN"\s*:\s*"([\w-]*(?:=|%3D){0,2})"''')
def post_comment(query_string, fields):
    with open('data/cookie.txt', 'r', encoding='utf-8') as f:
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
        _post_comment_reply(fields['comment_text'][0], parameters['video_id'][0], parameters['parent_id'][0], token, cookie_data)
        return comments.get_comments_page(query_string)
    else:
        _post_comment(fields['comment_text'][0], fields['video_id'][0], token, cookie_data)
        return comments.get_comments_page('ctoken=' + comments.make_comment_ctoken(video_id, sort=1))
        

def get_post_comment_page(query_string):
    parameters = urllib.parse.parse_qs(query_string)
    video_id = parameters['v'][0]
    style = ''' main{
    display: grid;
    grid-template-columns: 3fr 2fr;
}
.left{
    display:grid;
    grid-template-columns: 1fr 640px;
}
textarea{
    width: 462px;
    height: 85px;
}
.comment-form{
    grid-column:2;
}'''
    page = '''<div class="left">
    <form action="''' + common.URL_ORIGIN + '/comments?ctoken=' + comments.make_comment_ctoken(video_id, sort=1).replace("=", "%3D") + '''" method="post" class="comment-form">
        <textarea name="comment_text"></textarea>
        <input type="hidden" name="video_id" value="''' + video_id + '''">
        <button type="submit">Post comment</button>
    </form>
</div>
'''
    return common.yt_basic_template.substitute(
        page_title = "Post a comment",
        style = style,
        header = common.get_header(),
        page = page,
    )