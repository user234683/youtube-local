import json
import youtube.proto as proto
import base64
from youtube.common import uppercase_escape, default_multi_get, format_text_runs, URL_ORIGIN, fetch_url
from string import Template
import urllib.request
import urllib
import html
comment_template = Template('''
                <div class="comment-container">
                    <div class="comment">
                        <a class="author-avatar" href="$author_url" title="$author">
                            <img class="author-avatar-img" src="$author_avatar">
                        </a>
                        <address>
                            <a class="author" href="$author_url" title="$author">$author</a>
                        </address>
                        <span class="text">$text</span>
                        <time datetime="$datetime">$published</time>
                        <span class="likes">$likes</span>
$replies
                    </div>

                </div>
''')
reply_link_template = Template('''
                    <a href="$url" class="replies">View replies</a>
''')
with open("yt_comments_template.html", "r") as file:
    yt_comments_template = Template(file.read())


#                        <a class="replies-link" href="$replies_url">$replies_link_text</a>


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

def make_comment_ctoken(video_id, sort=0, offset=0, secret_key=''):
    video_id = proto.as_bytes(video_id)
    secret_key = proto.as_bytes(secret_key)
    

    page_info = proto.string(4,video_id) + proto.uint(6, sort)
    offset_information = proto.nested(4, page_info) + proto.uint(5, offset)
    if secret_key:
        offset_information = proto.string(1, secret_key) + offset_information
    
    result = proto.nested(2, proto.string(2, video_id)) + proto.uint(3,6) + proto.nested(6, offset_information)
    return base64.urlsafe_b64encode(result).decode('ascii')

def comment_replies_ctoken(video_id, comment_id, max_results=500):  

    params = proto.string(2, comment_id) + proto.uint(9, max_results)
    params = proto.nested(3, params)
    
    result = proto.nested(2, proto.string(2, video_id)) + proto.uint(3,6) + proto.nested(6, params)
    return base64.urlsafe_b64encode(result).decode('ascii')

def get_ids(ctoken):
    params = proto.parse(proto.b64_to_bytes(ctoken))
    video_id = proto.parse(params[2])[2]
    params = proto.parse(params[6])
    params = proto.parse(params[3])
    return params[2].decode('ascii'), video_id.decode('ascii')

mobile_headers = {
    'Host': 'm.youtube.com',
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 10_3_1 like Mac OS X) AppleWebKit/603.1.30 (KHTML, like Gecko) Version/10.0 Mobile/14E304 Safari/602.1',
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.5',
    'X-YouTube-Client-Name': '2',
    'X-YouTube-Client-Version': '1.20180613',
}
def request_comments(ctoken, replies=False):
    if replies: # let's make it use different urls for no reason despite all the data being encoded
        base_url = "https://m.youtube.com/watch_comment?action_get_comment_replies=1&ctoken="
    else:
        base_url = "https://m.youtube.com/watch_comment?action_get_comments=1&ctoken="
    url = base_url + ctoken.replace("=", "%3D") + "&pbj=1"
    print("Sending comments ajax request")
    for i in range(0,8):    # don't retry more than 8 times
        content = fetch_url(url, headers=mobile_headers)
        if content[0:4] == b")]}'":             # random closing characters included at beginning of response for some reason
            content = content[4:]
        elif content[0:10] == b'\n<!DOCTYPE':   # occasionally returns html instead of json for no reason
            content = b''
            print("got <!DOCTYPE>, retrying")
            continue
        break
    '''with open('debug/comments_debug', 'wb') as f:
        f.write(content)'''
    return content

def parse_comments(content, replies=False):
    try:
        content = json.loads(uppercase_escape(content.decode('utf-8')))
        #print(content)
        comments_raw = content['content']['continuation_contents']['contents']
        ctoken = default_multi_get(content, 'content', 'continuation_contents', 'continuations', 0, 'continuation', default='')
        
        comments = []
        for comment_raw in comments_raw:
            replies_url = ''
            if not replies:
                if comment_raw['replies'] is not None:
                    ctoken = comment_raw['replies']['continuations'][0]['continuation']
                    comment_id, video_id = get_ids(ctoken)
                    replies_url = URL_ORIGIN + '/comments?parent_id=' + comment_id + "&video_id=" + video_id
                comment_raw = comment_raw['comment']
            comment = {
            'author': comment_raw['author']['runs'][0]['text'],
            'author_url': comment_raw['author_endpoint']['url'],
            'author_avatar': comment_raw['author_thumbnail']['url'],
            'likes': comment_raw['like_count'],
            'published': comment_raw['published_time']['runs'][0]['text'],
            'text': comment_raw['content']['runs'],
            'reply_count': '',
            'replies_url': replies_url,
            }
            comments.append(comment)
    except Exception as e:
        print('Error parsing comments: ' + str(e))
        comments = ()
        ctoken = ''
    else:
        print("Finished getting and parsing comments")
    return {'ctoken': ctoken, 'comments': comments}

def get_comments_html(result):
    html_result = ''
    for comment in result['comments']:
        replies = ''
        if comment['replies_url']:
            replies = reply_link_template.substitute(url=comment['replies_url'])
        html_result += comment_template.substitute(
            author=html.escape(comment['author']),
            author_url = URL_ORIGIN + comment['author_url'],
            author_avatar = '/' + comment['author_avatar'],
            likes = str(comment['likes']) + ' likes' if str(comment['likes']) != '0' else '',
            published = comment['published'],
            text = format_text_runs(comment['text']),
            datetime = '',  #TODO
            replies=replies,
            #replies='',
        )
    return html_result, result['ctoken']
    
def video_comments(video_id, sort=0, offset=0, secret_key=''):
    result = parse_comments(request_comments(make_comment_ctoken(video_id, sort, offset, secret_key)))
    return get_comments_html(result)

more_comments_template = Template('''<a class="page-button more-comments" href="$url">More comments</a>''')

def get_comments_page(query_string):
    parameters = urllib.parse.parse_qs(query_string)
    ctoken = default_multi_get(parameters, 'ctoken', 0, default='')
    if not ctoken:
        video_id = parameters['video_id'][0]
        parent_id = parameters['parent_id'][0]

        ctoken = comment_replies_ctoken(video_id, parent_id)
        replies = True
    
    result = parse_comments(request_comments(ctoken, replies), replies)
    comments_html, ctoken = get_comments_html(result)
    if ctoken == '':
        more_comments_button = ''
    else:
        more_comments_button = more_comments_template.substitute(url = URL_ORIGIN + '/comments?ctoken=' + ctoken)

    return yt_comments_template.substitute(
        comments = comments_html,
        page_title = 'Comments',
        more_comments_button=more_comments_button,
    )

