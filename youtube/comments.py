import json
from youtube import proto, common, accounts
import base64
from youtube.common import uppercase_escape, default_multi_get, format_text_runs, URL_ORIGIN, fetch_url
from string import Template
import urllib.request
import urllib
import html
import settings
import re
comment_area_template = Template('''
<section class="comment-area">
$video-metadata
$comment-links
$comment-box
$comments
$more-comments-button    
</section>
''')
comment_template = Template('''
                <div class="comment-container">
                    <div class="comment">
                        <a class="author-avatar" href="$author_url" title="$author">
$avatar
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
comment_avatar_template = Template('''                            <img class="author-avatar-img" src="$author_avatar">''')

reply_link_template = Template('''
                    <a href="$url" class="replies">$view_replies_text</a>
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

def comment_replies_ctoken(video_id, comment_id, max_results=500):  

    params = proto.string(2, comment_id) + proto.uint(9, max_results)
    params = proto.nested(3, params)
    
    result = proto.nested(2, proto.string(2, video_id)) + proto.uint(3,6) + proto.nested(6, params)
    return base64.urlsafe_b64encode(result).decode('ascii')

def ctoken_metadata(ctoken):
    result = dict()
    params = proto.parse(proto.b64_to_bytes(ctoken))
    result['video_id'] = proto.parse(params[2])[2].decode('ascii')

    offset_information = proto.parse(params[6])
    result['offset'] = offset_information.get(5, 0)

    result['is_replies'] = False
    if (3 in offset_information) and (2 in proto.parse(offset_information[3])):
        result['is_replies'] = True
    else:
        try:
            result['sort'] = proto.parse(offset_information[4])[6]
        except KeyError:
            result['sort'] = 0
    return result

def get_ids(ctoken):
    params = proto.parse(proto.b64_to_bytes(ctoken))
    video_id = proto.parse(params[2])[2]
    params = proto.parse(params[6])
    params = proto.parse(params[3])
    return params[2].decode('ascii'), video_id.decode('ascii')

mobile_headers = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 10_3_1 like Mac OS X) AppleWebKit/603.1.30 (KHTML, like Gecko) Version/10.0 Mobile/14E304 Safari/602.1',
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.5',
    'X-YouTube-Client-Name': '2',
    'X-YouTube-Client-Version': '2.20180823',
}
def request_comments(ctoken, replies=False):
    if replies: # let's make it use different urls for no reason despite all the data being encoded
        base_url = "https://m.youtube.com/watch_comment?action_get_comment_replies=1&ctoken="
    else:
        base_url = "https://m.youtube.com/watch_comment?action_get_comments=1&ctoken="
    url = base_url + ctoken.replace("=", "%3D") + "&pbj=1"

    for i in range(0,8):    # don't retry more than 8 times
        content = fetch_url(url, headers=mobile_headers, report_text="Retrieved comments")
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

def single_comment_ctoken(video_id, comment_id):
    page_params = proto.string(2, video_id) + proto.string(6, proto.percent_b64encode(proto.string(15, comment_id)))

    result = proto.nested(2, page_params) + proto.uint(3,6)
    return base64.urlsafe_b64encode(result).decode('ascii')
    

def parse_comments_ajax(content, replies=False):
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
                    reply_ctoken = comment_raw['replies']['continuations'][0]['continuation']
                    comment_id, video_id = get_ids(reply_ctoken)
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

    return {'ctoken': ctoken, 'comments': comments}

reply_count_regex = re.compile(r'(\d+)')
def parse_comments_polymer(content, replies=False):
    try:
        video_title = ''
        content = json.loads(uppercase_escape(content.decode('utf-8')))
        url = content[1]['url']
        ctoken = urllib.parse.parse_qs(url[url.find('?')+1:])['ctoken'][0]
        video_id = ctoken_metadata(ctoken)['video_id']
        #print(content)
        try:
            comments_raw = content[1]['response']['continuationContents']['commentSectionContinuation']['items']
        except KeyError:
            comments_raw = content[1]['response']['continuationContents']['commentRepliesContinuation']['contents']
            replies = True

        ctoken = default_multi_get(content, 1, 'response', 'continuationContents', 'commentSectionContinuation', 'continuations', 0, 'nextContinuationData', 'continuation', default='')
        
        comments = []
        for comment_raw in comments_raw:
            replies_url = ''
            view_replies_text = ''
            try:
                comment_raw = comment_raw['commentThreadRenderer']
            except KeyError:
                pass
            else:
                if 'commentTargetTitle' in comment_raw:
                    video_title = comment_raw['commentTargetTitle']['runs'][0]['text']

                parent_id = comment_raw['comment']['commentRenderer']['commentId']
                if 'replies' in comment_raw:
                    #reply_ctoken = comment_raw['replies']['commentRepliesRenderer']['continuations'][0]['nextContinuationData']['continuation']
                    #comment_id, video_id = get_ids(reply_ctoken)
                    replies_url = URL_ORIGIN + '/comments?parent_id=' + parent_id + "&video_id=" + video_id
                    view_replies_text = common.get_plain_text(comment_raw['replies']['commentRepliesRenderer']['moreText'])
                    match = reply_count_regex.search(view_replies_text)
                    if match is None:
                        view_replies_text = '1 reply'
                    else:
                        view_replies_text = match.group(1) + " replies"
                elif not replies:
                    view_replies_text = "Reply"
                    replies_url = URL_ORIGIN + '/post_comment?parent_id=' + parent_id + "&video_id=" + video_id
                comment_raw = comment_raw['comment']
            
            comment_raw = comment_raw['commentRenderer']
            comment = {
            'author': common.get_plain_text(comment_raw['authorText']),
            'author_url': comment_raw['authorEndpoint']['commandMetadata']['webCommandMetadata']['url'],
            'author_avatar': comment_raw['authorThumbnail']['thumbnails'][0]['url'],
            'likes': comment_raw['likeCount'],
            'published': common.get_plain_text(comment_raw['publishedTimeText']),
            'text': comment_raw['contentText'].get('runs', ''),
            'view_replies_text': view_replies_text,
            'replies_url': replies_url,
            }
            comments.append(comment)
    except Exception as e:
        print('Error parsing comments: ' + str(e))
        comments = ()
        ctoken = ''

    return {'ctoken': ctoken, 'comments': comments, 'video_title': video_title}



def get_comments_html(comments):
    html_result = ''
    for comment in comments:
        replies = ''
        if comment['replies_url']:
            replies = reply_link_template.substitute(url=comment['replies_url'], view_replies_text=html.escape(comment['view_replies_text']))
        if settings.enable_comment_avatars:
            avatar = comment_avatar_template.substitute(
                author_url = URL_ORIGIN + comment['author_url'],
                author_avatar = '/' + comment['author_avatar'],
            )
        else:
            avatar = ''
        html_result += comment_template.substitute(
            author=comment['author'],
            author_url = URL_ORIGIN + comment['author_url'],
            avatar = avatar,
            likes = str(comment['likes']) + ' likes' if str(comment['likes']) != '0' else '',
            published = comment['published'],
            text = format_text_runs(comment['text']),
            datetime = '',  #TODO
            replies=replies,
            #replies='',
        )
    return html_result
    
def video_comments(video_id, sort=0, offset=0, lc='', secret_key=''):
    if settings.enable_comments:
        post_comment_url = common.URL_ORIGIN + "/post_comment?video_id=" + video_id
        post_comment_link = '''<a class="sort-button" href="''' + post_comment_url + '''">Post comment</a>'''

        other_sort_url = common.URL_ORIGIN + '/comments?ctoken=' + make_comment_ctoken(video_id, sort=1 - sort, lc=lc)
        other_sort_name = 'newest' if sort == 0 else 'top'
        other_sort_link = '''<a class="sort-button" href="''' + other_sort_url + '''">Sort by ''' + other_sort_name + '''</a>'''

        comment_links = '''<div class="comment-links">\n'''
        comment_links += other_sort_link + '\n' + post_comment_link + '\n'
        comment_links += '''</div>'''
        
        comment_info = parse_comments_polymer(request_comments(make_comment_ctoken(video_id, sort, offset, lc, secret_key)))
        ctoken = comment_info['ctoken']

        if ctoken == '':
            more_comments_button = ''
        else:
            more_comments_button = more_comments_template.substitute(url = common.URL_ORIGIN + '/comments?ctoken=' + ctoken)

        result = '''<section class="comments-area">\n'''
        result += comment_links + '\n'
        result += '<div class="comments">\n'
        result += get_comments_html(comment_info['comments']) + '\n'
        result += '</div>\n'
        result += more_comments_button + '\n'
        result += '''</section>'''
        return result
    return ''

more_comments_template = Template('''<a class="page-button more-comments" href="$url">More comments</a>''')
video_metadata_template = Template('''<section class="video-metadata">
    <a class="video-metadata-thumbnail-box" href="$url" title="$title">
        <img class="video-metadata-thumbnail-img" src="$thumbnail" height="180px" width="320px">
    </a>
    <a class="title" href="$url" title="$title">$title</a>

    <h2>Comments page $page_number</h2>
    <span>Sorted by $sort</span>
</section>
''')
account_option_template = Template('''
            <option value="$username">$username</option>''')

def comment_box_account_options():
    return ''.join(account_option_template.substitute(username=username) for username in accounts.username_list())

comment_box_template = Template('''
<form action="$form_action" method="post" class="comment-form">
    <div id="comment-account-options">
        <label for="username-selection">Account:</label>
        <select id="username-selection">
$options
        </select>
        <a href="''' + common.URL_ORIGIN + '''/login" target="_blank">Add account</a>
    </div>
    <textarea name="comment_text"></textarea>
    $video_id_input
    <button type="submit" class="post-comment-button">$post_text</button>
</form>''')
def get_comments_page(query_string):
    parameters = urllib.parse.parse_qs(query_string)
    ctoken = default_multi_get(parameters, 'ctoken', 0, default='')
    replies = False
    if not ctoken:
        video_id = parameters['video_id'][0]
        parent_id = parameters['parent_id'][0]

        ctoken = comment_replies_ctoken(video_id, parent_id)
        replies = True

    comment_info = parse_comments_polymer(request_comments(ctoken, replies), replies)

    metadata = ctoken_metadata(ctoken)
    if replies:
        page_title = 'Replies'
        video_metadata = ''
        comment_box = comment_box_template.substitute(form_action='', video_id_input='', post_text='Post reply', options=comment_box_account_options())
        comment_links = ''
    else:
        page_number = str(int(metadata['offset']/20) + 1)
        page_title = 'Comments page ' + page_number
        
        video_metadata = video_metadata_template.substitute(
            page_number = page_number,
            sort = 'top' if metadata['sort'] == 0 else 'newest',
            title = html.escape(comment_info['video_title']),
            url = common.URL_ORIGIN + '/watch?v=' + metadata['video_id'],
            thumbnail = '/i.ytimg.com/vi/'+ metadata['video_id'] + '/mqdefault.jpg',
        )
        comment_box = comment_box_template.substitute(
            form_action= common.URL_ORIGIN + '/post_comment',
            video_id_input='''<input type="hidden" name="video_id" value="''' + metadata['video_id'] + '''">''',
            post_text='Post comment',
            options=comment_box_account_options(),
        )

        other_sort_url = common.URL_ORIGIN + '/comments?ctoken=' + make_comment_ctoken(metadata['video_id'], sort=1 - metadata['sort'])
        other_sort_name = 'newest' if metadata['sort'] == 0 else 'top'
        other_sort_link = '''<a class="sort-button" href="''' + other_sort_url + '''">Sort by ''' + other_sort_name + '''</a>'''


        comment_links = '''<div class="comment-links">\n'''
        comment_links += other_sort_link + '\n'
        comment_links += '''</div>'''

    comments_html = get_comments_html(comment_info['comments'])
    ctoken = comment_info['ctoken']
    if ctoken == '':
        more_comments_button = ''
    else:
        more_comments_button = more_comments_template.substitute(url = URL_ORIGIN + '/comments?ctoken=' + ctoken)
    comments_area = '<section class="comments-area">\n'
    comments_area += video_metadata + comment_box + comment_links + '\n'
    comments_area += '<div class="comments">\n'
    comments_area += comments_html + '\n'
    comments_area += '</div>\n'
    comments_area += more_comments_button + '\n'
    comments_area += '</section>\n'
    return yt_comments_template.substitute(
        header = common.get_header(),
        comments_area = comments_area,
        page_title = page_title,
    )