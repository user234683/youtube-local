# Contains functions having to do with posting/editing/deleting comments
from youtube import util, proto, comments, accounts
from youtube import yt_app
import settings

import urllib
import json
import re
import traceback
import os

import flask
from flask import request

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


    content = util.fetch_url("https://m.youtube.com/service_ajax?name=createCommentEndpoint", headers=headers, data=data, cookiejar_send=cookiejar, debug_name='post_comment')

    code = json.loads(content)['code']
    print("Comment posting code: " + code)
    return code


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

    content = util.fetch_url("https://m.youtube.com/service_ajax?name=createCommentReplyEndpoint", headers=headers, data=data, cookiejar_send=cookiejar, debug_name='post_reply')

    code = json.loads(content)['code']
    print("Comment posting code: " + code)
    return code

def _delete_comment(video_id, comment_id, session_token, cookiejar):
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 10_3_1 like Mac OS X) AppleWebKit/603.1.30 (KHTML, like Gecko) Version/10.0 Mobile/14E304 Safari/602.1',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'X-YouTube-Client-Name': '2',
        'X-YouTube-Client-Version': '2.20180823',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    action = proto.uint(1,6) + proto.string(3, comment_id) + proto.string(5, video_id)
    action = proto.percent_b64encode(action).decode('ascii')

    sej = json.dumps({"clickTrackingParams":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=","commandMetadata":{"webCommandMetadata":{"url":"/service_ajax","sendPost":True}},"performCommentActionEndpoint":{"action":action}})

    data_dict = {
        'sej': sej,
        'session_token': session_token,
    }
    data = urllib.parse.urlencode(data_dict).encode()

    content = util.fetch_url("https://m.youtube.com/service_ajax?name=performCommentActionEndpoint", headers=headers, data=data, cookiejar_send=cookiejar)
    code = json.loads(content)['code']
    print("Comment deletion code: " + code)
    return code

xsrf_token_regex = re.compile(r'''XSRF_TOKEN"\s*:\s*"([\w-]*(?:=|%3D){0,2})"''')
def get_session_token(video_id, cookiejar):
    ''' Get session token for a video. This is required in order to post/edit/delete comments. This will modify cookiejar with cookies from youtube required for commenting'''
    # youtube-dl uses disable_polymer=1 which uses a different request format which has an obfuscated javascript algorithm to generate a parameter called "bgr"
    # Tokens retrieved from disable_polymer pages only work with that format. Tokens retrieved on mobile only work using mobile requests
    # Additionally, tokens retrieved without sending the same cookie won't work. So this is necessary even if the bgr and stuff was reverse engineered.
    headers = {'User-Agent': util.mobile_user_agent}
    mobile_page = util.fetch_url('https://m.youtube.com/watch?v=' + video_id, headers, report_text="Retrieved session token for comment", cookiejar_send=cookiejar, cookiejar_receive=cookiejar).decode()
    match = xsrf_token_regex.search(mobile_page)
    if match:
        return match.group(1).replace("%3D", "=")
    else:
        raise Exception("Couldn't find xsrf_token")

@yt_app.route('/delete_comment', methods=['POST'])
def delete_comment():
    video_id = request.values['video_id']
    cookiejar = accounts.account_cookiejar(request.values['channel_id'])
    token = get_session_token(video_id, cookiejar)

    code = _delete_comment(video_id, request.values['comment_id'], token, cookiejar)

    if code == "SUCCESS":
        return flask.redirect(util.URL_ORIGIN + '/comment_delete_success', 303)
    else:
        return flask.redirect(util.URL_ORIGIN + '/comment_delete_fail', 303)

@yt_app.route('/comment_delete_success')
def comment_delete_success():
    return flask.render_template('status.html', title='Success', message='Successfully deleted comment')

@yt_app.route('/comment_delete_fail')
def comment_delete_fail():
    return flask.render_template('status.html', title='Error', message='Failed to delete comment')

@yt_app.route('/post_comment', methods=['POST'])
@yt_app.route('/comments', methods=['POST'])
def post_comment():
    video_id = request.values['video_id']
    channel_id = request.values['channel_id']
    cookiejar = accounts.account_cookiejar(channel_id)
    token = get_session_token(video_id, cookiejar)

    if 'parent_id' in request.values:
        code = _post_comment_reply(request.values['comment_text'], request.values['video_id'], request.values['parent_id'], token, cookiejar)
        return flask.redirect(util.URL_ORIGIN + '/comments?' + request.query_string.decode('utf-8'), 303)
    else:
        code = _post_comment(request.values['comment_text'], request.values['video_id'], token, cookiejar)
        return flask.redirect(util.URL_ORIGIN + '/comments?ctoken=' + comments.make_comment_ctoken(video_id, sort=1), 303)

@yt_app.route('/delete_comment', methods=['GET'])
def get_delete_comment_page():
    parameters = [(parameter_name, request.args[parameter_name]) for parameter_name in ('video_id', 'channel_id', 'comment_id')]
    return flask.render_template('delete_comment.html', parameters = parameters)


@yt_app.route('/post_comment', methods=['GET'])
def get_post_comment_page():
    video_id = request.args['video_id']
    parent_id = request.args.get('parent_id', '')
    
    if parent_id:   # comment reply
        form_action = util.URL_ORIGIN + '/comments?parent_id=' + parent_id + "&video_id=" + video_id
        replying = True
    else:
        form_action = ''
        replying = False


    comment_posting_box_info = {
        'form_action': form_action,
        'video_id': video_id,
        'accounts': accounts.account_list_data(),
        'include_video_id_input': not replying,
        'replying': replying,
    }
    return flask.render_template('post_comment.html',
        comment_posting_box_info = comment_posting_box_info,
        replying = replying,
    )




