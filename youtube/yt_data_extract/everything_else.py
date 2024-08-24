from .common import (get, multi_get, deep_get, multi_deep_get,
    liberal_update, conservative_update, remove_redirect, normalize_url,
    extract_str, extract_formatted_text, extract_int, extract_approx_int,
    extract_date, check_missing_keys, extract_item_info, extract_items,
    extract_response)
from youtube import proto

import re
import urllib
from math import ceil

def extract_channel_info(polymer_json, tab, continuation=False):
    response, err = extract_response(polymer_json)
    if err:
        return {'error': err}


    metadata = deep_get(response, 'metadata', 'channelMetadataRenderer',
        default={})
    if not metadata:
        metadata = deep_get(response, 'microformat', 'microformatDataRenderer',
            default={})

    # channel doesn't exist or was terminated
    # example terminated channel: https://www.youtube.com/channel/UCnKJeK_r90jDdIuzHXC0Org
    # metadata and microformat are not present for continuation requests
    if not metadata and not continuation:
        if response.get('alerts'):
            error_string = ' '.join(
                extract_str(deep_get(alert, 'alertRenderer', 'text'), default='')
                for alert in response['alerts']
            )
            if not error_string:
                error_string = 'Failed to extract error'
            return {'error': error_string}
        elif deep_get(response, 'responseContext', 'errors'):
            for error in response['responseContext']['errors'].get('error', []):
                if error.get('code') == 'INVALID_VALUE' and error.get('location') == 'browse_id':
                    return {'error': 'This channel does not exist'}
        return {'error': 'Failure getting metadata'}

    info = {'error': None}
    info['current_tab'] = tab

    info['approx_subscriber_count'] = extract_approx_int(deep_get(response,
        'header', 'c4TabbedHeaderRenderer', 'subscriberCountText'))

    # stuff from microformat (info given by youtube for first page on channel)
    info['short_description'] = metadata.get('description')
    if info['short_description'] and len(info['short_description']) > 730:
        info['short_description'] = info['short_description'][0:730] + '...'
    info['channel_name'] = metadata.get('title')
    info['avatar'] = normalize_url(multi_deep_get(metadata,
        ['avatar', 'thumbnails', 0, 'url'],
        ['thumbnail', 'thumbnails', 0, 'url'],
    ))
    channel_url = multi_get(metadata, 'urlCanonical', 'channelUrl')
    if channel_url:
        channel_id = get(channel_url.rstrip('/').split('/'), -1)
        info['channel_id'] = channel_id
    else:
        info['channel_id'] = metadata.get('externalId')
    if info['channel_id']:
        info['channel_url'] = 'https://www.youtube.com/channel/' + channel_id
    else:
        info['channel_url'] = None

    # get items
    info['items'] = []
    info['ctoken'] = None

    # empty channel
    #if 'contents' not in response and 'continuationContents' not in response:
    #    return info

    if tab in ('videos', 'shorts', 'streams', 'playlists', 'search'):
        items, ctoken = extract_items(response)
        additional_info = {
            'author': info['channel_name'],
            'author_id': info['channel_id'],
            'author_url': info['channel_url'],
        }
        info['items'] = [extract_item_info(renderer, additional_info) for renderer in items]
        info['ctoken'] = ctoken
        if tab in ('search', 'playlists'):
            info['is_last_page'] = (ctoken is None)
    elif tab == 'about':
        # Latest type
        items, _ = extract_items(response, item_types={'aboutChannelRenderer'})
        if items:
            a_metadata = deep_get(items, 0, 'aboutChannelRenderer',
                'metadata', 'aboutChannelViewModel')
            if not a_metadata:
                info['error'] = 'Could not find aboutChannelViewModel'
                return info

            info['links'] = []
            for link_outer in a_metadata.get('links', ()):
                link = link_outer.get('channelExternalLinkViewModel') or {}
                link_content = extract_str(deep_get(link, 'link', 'content'))
                for run in deep_get(link, 'link', 'commandRuns') or ():
                    url = remove_redirect(deep_get(run, 'onTap', 
                        'innertubeCommand', 'urlEndpoint', 'url'))
                    if url and not (url.startswith('http://')
                            or url.startswith('https://')):
                        url = 'https://' + url
                    if link_content is None or (link_content in url):
                        break
                else: # didn't break
                    url = link_content
                    if url and not (url.startswith('http://')
                            or url.startswith('https://')):
                        url = 'https://' + url
                text = extract_str(deep_get(link, 'title', 'content'))
                info['links'].append( (text, url) )

            info['date_joined'] = extract_date(
                a_metadata.get('joinedDateText')
            )
            info['view_count'] = extract_int(a_metadata.get('viewCountText'))
            info['approx_view_count'] = extract_approx_int(
                a_metadata.get('viewCountText')
            )
            info['description'] = extract_str(
                a_metadata.get('description'), default=''
            )
            info['approx_video_count'] = extract_approx_int(
                a_metadata.get('videoCountText')
            )
            info['approx_subscriber_count'] = extract_approx_int(
                a_metadata.get('subscriberCountText')
            )
            info['country'] = extract_str(a_metadata.get('country'))
            info['canonical_url'] = extract_str(
                a_metadata.get('canonicalChannelUrl')
            )

        # Old type
        else:
            items, _ = extract_items(response,
                item_types={'channelAboutFullMetadataRenderer'})
            if not items:
                info['error'] = 'Could not find aboutChannelRenderer or channelAboutFullMetadataRenderer'
                return info
            a_metadata = items[0]['channelAboutFullMetadataRenderer']

            info['links'] = []
            for link_json in a_metadata.get('primaryLinks', ()):
                url = remove_redirect(deep_get(link_json, 'navigationEndpoint',
                    'urlEndpoint', 'url'))
                if url and not (url.startswith('http://')
                                or url.startswith('https://')):
                    url = 'https://' + url
                text = extract_str(link_json.get('title'))
                info['links'].append( (text, url) )

            info['date_joined'] = extract_date(a_metadata.get('joinedDateText'))
            info['view_count'] = extract_int(a_metadata.get('viewCountText'))
            info['description'] = extract_str(a_metadata.get(
                'description'), default='')

            info['approx_video_count'] = None
            info['approx_subscriber_count'] = None
            info['country'] = None
            info['canonical_url'] = None
    else:
        raise NotImplementedError('Unknown or unsupported channel tab: ' + tab)

    return info

def extract_search_info(polymer_json):
    response, err = extract_response(polymer_json)
    if err:
        return {'error': err}
    info = {'error': None}
    info['estimated_results'] = int(response['estimatedResults'])
    info['estimated_pages'] = ceil(info['estimated_results']/20)


    results, _ = extract_items(response)


    info['items'] = []
    info['corrections'] = {'type': None}
    for renderer in results:
        type = list(renderer.keys())[0]
        if type == 'shelfRenderer':
            continue
        if type == 'didYouMeanRenderer':
            renderer = renderer[type]

            info['corrections'] = {
                'type': 'did_you_mean',
                'corrected_query': renderer['correctedQueryEndpoint']['searchEndpoint']['query'],
                'corrected_query_text': renderer['correctedQuery']['runs'],
            }
            continue
        if type == 'showingResultsForRenderer':
            renderer = renderer[type]

            info['corrections'] = {
                'type': 'showing_results_for',
                'corrected_query_text': renderer['correctedQuery']['runs'],
                'original_query_text': renderer['originalQuery']['simpleText'],
            }
            continue

        i_info = extract_item_info(renderer)
        if i_info.get('type') != 'unsupported':
            info['items'].append(i_info)


    return info

def extract_playlist_metadata(polymer_json):
    response, err = extract_response(polymer_json)
    if err:
        return {'error': err}

    metadata = {'error': None}
    header = deep_get(response, 'header', 'playlistHeaderRenderer', default={})
    metadata['title'] = extract_str(header.get('title'))

    metadata['first_video_id'] = deep_get(header, 'playEndpoint', 'watchEndpoint', 'videoId')
    first_id = re.search(r'([a-z_\-]{11})', deep_get(header,
        'thumbnail', 'thumbnails', 0, 'url', default=''))
    if first_id:
        conservative_update(metadata, 'first_video_id', first_id.group(1))
    if metadata['first_video_id'] is None:
        metadata['thumbnail'] = None
    else:
        metadata['thumbnail'] = 'https://i.ytimg.com/vi/' + metadata['first_video_id'] + '/mqdefault.jpg'

    metadata['video_count'] = extract_int(header.get('numVideosText'))
    metadata['description'] = extract_str(header.get('descriptionText'), default='')
    metadata['author'] = extract_str(header.get('ownerText'))
    metadata['author_id'] = multi_deep_get(header,
        ['ownerText', 'runs', 0, 'navigationEndpoint', 'browseEndpoint', 'browseId'],
        ['ownerEndpoint', 'browseEndpoint', 'browseId'])
    if metadata['author_id']:
        metadata['author_url'] = 'https://www.youtube.com/channel/' + metadata['author_id']
    else:
        metadata['author_url'] = None
    metadata['view_count'] = extract_int(header.get('viewCountText'))
    metadata['like_count'] = extract_int(header.get('likesCountWithoutLikeText'))
    for stat in header.get('stats', ()):
        text = extract_str(stat)
        if 'videos' in text:
            conservative_update(metadata, 'video_count', extract_int(text))
        elif 'views' in text:
            conservative_update(metadata, 'view_count', extract_int(text))
        elif 'updated' in text:
            metadata['time_published'] = extract_date(text)

    microformat = deep_get(response, 'microformat', 'microformatDataRenderer',
                           default={})
    conservative_update(
        metadata, 'title', extract_str(microformat.get('title'))
    )
    conservative_update(
        metadata, 'description', extract_str(microformat.get('description'))
    )
    conservative_update(
        metadata, 'thumbnail', deep_get(microformat, 'thumbnail',
                                        'thumbnails', -1, 'url')
    )

    return metadata

def extract_playlist_info(polymer_json):
    response, err = extract_response(polymer_json)
    if err:
        return {'error': err}
    info = {'error': None}
    video_list, _ = extract_items(response)

    info['items'] = [extract_item_info(renderer) for renderer in video_list]

    info['metadata'] = extract_playlist_metadata(polymer_json)

    return info

def _ctoken_metadata(ctoken):
    result = dict()
    params = proto.parse(proto.b64_to_bytes(ctoken))
    result['video_id'] = proto.parse(params[2])[2].decode('ascii')

    offset_information = proto.parse(params[6])
    result['offset'] = offset_information.get(5, 0)

    result['is_replies'] = False
    if (3 in offset_information) and (2 in proto.parse(offset_information[3])):
        result['is_replies'] = True
        result['sort'] = None
    else:
        try:
            result['sort'] = proto.parse(offset_information[4])[6]
        except KeyError:
            result['sort'] = 0
    return result

def extract_comments_info(polymer_json, ctoken=None):
    response, err = extract_response(polymer_json)
    if err:
        return {'error': err}
    info = {'error': None}

    if ctoken:
        metadata = _ctoken_metadata(ctoken)
    else:
        metadata = {}
    info['video_id'] = metadata.get('video_id')
    info['offset'] = metadata.get('offset')
    info['is_replies'] = metadata.get('is_replies')
    info['sort'] = metadata.get('sort')
    info['video_title'] = None

    comments, ctoken = extract_items(response,
        item_types={'commentThreadRenderer', 'commentRenderer'})
    info['comments'] = []
    info['ctoken'] = ctoken
    for comment in comments:
        comment_info = {}

        if 'commentThreadRenderer' in comment:  # top level comments
            conservative_update(info, 'is_replies', False)
            comment_thread  = comment['commentThreadRenderer']
            info['video_title'] = extract_str(comment_thread.get('commentTargetTitle'))
            if 'replies' not in comment_thread:
                comment_info['reply_count'] = 0
                comment_info['reply_ctoken'] = None
            else:
                comment_info['reply_count'] = extract_int(deep_get(comment_thread,
                    'replies', 'commentRepliesRenderer', 'moreText'
                ), default=1)   # With 1 reply, the text reads "View reply"
                comment_info['reply_ctoken'] = multi_deep_get(
                    comment_thread,
                    ['replies', 'commentRepliesRenderer', 'contents', 0,
                     'continuationItemRenderer', 'button', 'buttonRenderer',
                     'command', 'continuationCommand', 'token'],
                    ['replies', 'commentRepliesRenderer', 'continuations', 0,
                     'nextContinuationData', 'continuation']
                )
            comment_renderer = deep_get(comment_thread, 'comment', 'commentRenderer', default={})
        elif 'commentRenderer' in comment:  # replies
            comment_info['reply_count'] = 0     # replyCount, below, not present for replies even if the reply has further replies to it
            comment_info['reply_ctoken'] = None
            conservative_update(info, 'is_replies', True)
            comment_renderer = comment['commentRenderer']
        else:
            comment_renderer = {}

        # These 3 are sometimes absent, likely because the channel was deleted
        comment_info['author'] = extract_str(comment_renderer.get('authorText'))
        comment_info['author_url'] = normalize_url(deep_get(comment_renderer,
            'authorEndpoint', 'commandMetadata', 'webCommandMetadata', 'url'))
        comment_info['author_id'] = deep_get(comment_renderer,
            'authorEndpoint', 'browseEndpoint', 'browseId')

        comment_info['author_avatar'] = normalize_url(deep_get(
            comment_renderer, 'authorThumbnail', 'thumbnails', 0, 'url'))
        comment_info['id'] = comment_renderer.get('commentId')
        comment_info['text'] = extract_formatted_text(comment_renderer.get('contentText'))
        comment_info['time_published'] = extract_str(comment_renderer.get('publishedTimeText'))
        comment_info['like_count'] = comment_renderer.get('likeCount')
        comment_info['approx_like_count'] = extract_approx_int(
            comment_renderer.get('voteCount'))
        liberal_update(comment_info, 'reply_count', comment_renderer.get('replyCount'))

        info['comments'].append(comment_info)

    return info
