from youtube import proto, util, yt_data_extract
from youtube.util import concat_or_none
from youtube import yt_app
import settings

import json
import base64
import urllib
import re
import traceback

import flask
from flask import request

# Here's what I know about the secret key (starting with ASJN_i)
# *The secret key definitely contains the following information (or perhaps the information is stored at youtube's servers):
#   -Video id
#   -Offset
#   -Sort
# *If the video id or sort in the ctoken contradicts the ASJN, the response is an error. The offset encoded outside the ASJN is ignored entirely.
# *The ASJN is base64 encoded data, indicated by the fact that the character after "ASJN_i" is one of ("0", "1", "2", "3")
# *The encoded data is not valid protobuf
# *The encoded data (after the 5 or so bytes that are always the same) is indistinguishable from random data according to a battery of randomness tests
# *The ASJN in the ctoken provided by a response changes in regular intervals of about a second or two.
# *Old ASJN's continue to work, and start at the same comment even if new comments have been posted since
# *The ASJN has no relation with any of the data in the response it came from

def make_comment_ctoken(video_id, sort=0, offset=0, lc='', secret_key=''):
    video_id = proto.as_bytes(video_id)
    secret_key = proto.as_bytes(secret_key)


    page_info = proto.string(4,video_id) + proto.uint(6, sort)
    offset_information = proto.nested(4, page_info) + proto.uint(5, offset)
    if secret_key:
        offset_information = proto.string(1, secret_key) + offset_information

    page_params = proto.string(2, video_id)
    if lc:
        page_params += proto.string(6, proto.percent_b64encode(proto.string(15, lc)))

    result = proto.nested(2, page_params) + proto.uint(3,6) + proto.nested(6, offset_information)
    return base64.urlsafe_b64encode(result).decode('ascii')


def request_comments(ctoken, replies=False):
    url = 'https://m.youtube.com/youtubei/v1/next'
    url += '?key=AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8'
    data = json.dumps({
        'context': {
            'client': {
                'hl': 'en',
                'gl': 'US',
                'clientName': 'MWEB',
                'clientVersion': '2.20210804.02.00',
            },
        },
        'continuation': ctoken.replace('=', '%3D'),
    })

    content = util.fetch_url(
        url, headers=util.mobile_xhr_headers + util.json_header, data=data,
        report_text='Retrieved comments', debug_name='request_comments')
    content = content.decode('utf-8')

    polymer_json = json.loads(content)
    return polymer_json


def single_comment_ctoken(video_id, comment_id):
    page_params = proto.string(2, video_id) + proto.string(6, proto.percent_b64encode(proto.string(15, comment_id)))

    result = proto.nested(2, page_params) + proto.uint(3,6)
    return base64.urlsafe_b64encode(result).decode('ascii')



def post_process_comments_info(comments_info):
    for comment in comments_info['comments']:
        comment['author_url'] = concat_or_none(
            '/', comment['author_url'])
        comment['author_avatar'] = concat_or_none(
            settings.img_prefix, comment['author_avatar'])

        comment['permalink'] = concat_or_none(util.URL_ORIGIN, '/watch?v=',
            comments_info['video_id'], '&lc=', comment['id'])


        reply_count = comment['reply_count']
        comment['replies_url'] = None
        if comment['reply_ctoken']:
            # change max_replies field to 250 in ctoken
            ctoken = comment['reply_ctoken']
            ctoken, err = proto.set_protobuf_value(
                ctoken,
                'base64p', 6, 3, 9, value=200)
            if err:
                print('Error setting ctoken value:')
                print(err)
                comment['replies_url'] = None
            comment['replies_url'] = concat_or_none(util.URL_ORIGIN,
                '/comments?replies=1&ctoken=' + ctoken)

        if reply_count == 0:
            comment['view_replies_text'] = 'Reply'
        elif reply_count == 1:
            comment['view_replies_text'] = '1 reply'
        else:
            comment['view_replies_text'] = str(reply_count) + ' replies'


        if comment['approx_like_count'] == '1':
            comment['likes_text'] = '1 like'
        else:
            comment['likes_text'] = (str(comment['approx_like_count'])
                                     + ' likes')

    comments_info['include_avatars'] = settings.enable_comment_avatars
    if comments_info['ctoken']:
        ctoken = comments_info['ctoken']
        if comments_info['is_replies']:
            replies_param = '&replies=1'
            # change max_replies field to 250 in ctoken
            new_ctoken, err = proto.set_protobuf_value(
                ctoken,
                'base64p', 6, 3, 9, value=200)
            if err:
                print('Error setting ctoken value:')
                print(err)
            else:
                ctoken = new_ctoken
        else:
            replies_param = ''
        comments_info['more_comments_url'] = concat_or_none(util.URL_ORIGIN,
            '/comments?ctoken=', ctoken, replies_param)

    if comments_info['offset'] is None:
        comments_info['page_number'] = None
    else:
        comments_info['page_number'] = int(comments_info['offset']/20) + 1

    if not comments_info['is_replies']:
        comments_info['sort_text'] = 'top' if comments_info['sort'] == 0 else 'newest'


    comments_info['video_url'] = concat_or_none(util.URL_ORIGIN,
        '/watch?v=', comments_info['video_id'])
    comments_info['video_thumbnail'] = concat_or_none(settings.img_prefix, 'https://i.ytimg.com/vi/',
        comments_info['video_id'], '/mqdefault.jpg')


def video_comments(video_id, sort=0, offset=0, lc='', secret_key=''):
    try:
        if settings.comments_mode:
            comments_info = {'error': None}
            other_sort_url = (
                util.URL_ORIGIN + '/comments?ctoken='
                + make_comment_ctoken(video_id, sort=1 - sort, lc=lc)
            )
            other_sort_text = 'Sort by ' + ('newest' if sort == 0 else 'top')

            this_sort_url = (util.URL_ORIGIN
                             + '/comments?ctoken='
                             + make_comment_ctoken(video_id, sort=sort, lc=lc))

            comments_info['comment_links'] = [
                (other_sort_text, other_sort_url),
                ('Direct link', this_sort_url)
            ]

            ctoken = make_comment_ctoken(video_id, sort, offset, lc)
            comments_info.update(yt_data_extract.extract_comments_info(
                request_comments(ctoken), ctoken=ctoken
            ))
            post_process_comments_info(comments_info)

            return comments_info
        else:
            return {}
    except util.FetchError as e:
        if e.code == '429' and settings.route_tor:
            comments_info['error'] = 'Error: Youtube blocked the request because the Tor exit node is overutilized.'
            if e.error_message:
                comments_info['error'] += '\n\n' + e.error_message
            comments_info['error'] += '\n\nExit node IP address: %s' % e.ip
        else:
            comments_info['error'] = traceback.format_exc()

    except Exception as e:
        comments_info['error'] = traceback.format_exc()

    if comments_info.get('error'):
        print('Error retrieving comments for ' + str(video_id) + ':\n' +
              comments_info['error'])

    return comments_info



@yt_app.route('/comments')
def get_comments_page():
    ctoken = request.args.get('ctoken', '')
    replies = request.args.get('replies', '0') == '1'

    comments_info = yt_data_extract.extract_comments_info(
        request_comments(ctoken, replies), ctoken=ctoken
    )
    post_process_comments_info(comments_info)

    if not replies:
        if comments_info['sort'] is None or comments_info['video_id'] is None:
            other_sort_url = None
        else:
            other_sort_url = (
                util.URL_ORIGIN
                + '/comments?ctoken='
                + make_comment_ctoken(comments_info['video_id'],
                                      sort=1-comments_info['sort'])
            )
        other_sort_text = 'Sort by ' + ('newest' if comments_info['sort'] == 0 else 'top')
        comments_info['comment_links'] = [(other_sort_text, other_sort_url)]

    return flask.render_template('comments_page.html',
        comments_info = comments_info,
        slim = request.args.get('slim', False)
    )

