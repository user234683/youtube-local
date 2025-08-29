from .common import (get, multi_get, deep_get, multi_deep_get,
    liberal_update, conservative_update, remove_redirect, normalize_url,
    extract_str, extract_formatted_text, extract_int, extract_approx_int,
    extract_date, check_missing_keys, extract_item_info, extract_items,
    extract_response, concat_or_none, liberal_dict_update,
    conservative_dict_update)

import json
import urllib.parse
import traceback
import re
import dukpy
import os
import settings
from .. import util

# from https://github.com/ytdl-org/youtube-dl/blob/master/youtube_dl/extractor/youtube.py
_formats = {
    '5': {'ext': 'flv', 'width': 400, 'height': 240, 'acodec': 'mp3', 'audio_bitrate': 64, 'vcodec': 'h263'},
    '6': {'ext': 'flv', 'width': 450, 'height': 270, 'acodec': 'mp3', 'audio_bitrate': 64, 'vcodec': 'h263'},
    '13': {'ext': '3gp', 'acodec': 'aac', 'vcodec': 'mp4v'},
    '17': {'ext': '3gp', 'width': 176, 'height': 144, 'acodec': 'aac', 'audio_bitrate': 24, 'vcodec': 'mp4v'},
    '18': {'ext': 'mp4', 'width': 640, 'height': 360, 'acodec': 'aac', 'audio_bitrate': 96, 'vcodec': 'h264'},
    '22': {'ext': 'mp4', 'width': 1280, 'height': 720, 'acodec': 'aac', 'audio_bitrate': 192, 'vcodec': 'h264'},
    '34': {'ext': 'flv', 'width': 640, 'height': 360, 'acodec': 'aac', 'audio_bitrate': 128, 'vcodec': 'h264'},
    '35': {'ext': 'flv', 'width': 854, 'height': 480, 'acodec': 'aac', 'audio_bitrate': 128, 'vcodec': 'h264'},
    # itag 36 videos are either 320x180 (BaW_jenozKc) or 320x240 (__2ABJjxzNo), audio_bitrate varies as well
    '36': {'ext': '3gp', 'width': 320, 'acodec': 'aac', 'vcodec': 'mp4v'},
    '37': {'ext': 'mp4', 'width': 1920, 'height': 1080, 'acodec': 'aac', 'audio_bitrate': 192, 'vcodec': 'h264'},
    '38': {'ext': 'mp4', 'width': 4096, 'height': 3072, 'acodec': 'aac', 'audio_bitrate': 192, 'vcodec': 'h264'},
    '43': {'ext': 'webm', 'width': 640, 'height': 360, 'acodec': 'vorbis', 'audio_bitrate': 128, 'vcodec': 'vp8'},
    '44': {'ext': 'webm', 'width': 854, 'height': 480, 'acodec': 'vorbis', 'audio_bitrate': 128, 'vcodec': 'vp8'},
    '45': {'ext': 'webm', 'width': 1280, 'height': 720, 'acodec': 'vorbis', 'audio_bitrate': 192, 'vcodec': 'vp8'},
    '46': {'ext': 'webm', 'width': 1920, 'height': 1080, 'acodec': 'vorbis', 'audio_bitrate': 192, 'vcodec': 'vp8'},
    '59': {'ext': 'mp4', 'width': 854, 'height': 480, 'acodec': 'aac', 'audio_bitrate': 128, 'vcodec': 'h264'},
    '78': {'ext': 'mp4', 'width': 854, 'height': 480, 'acodec': 'aac', 'audio_bitrate': 128, 'vcodec': 'h264'},


    # 3D videos
    '82': {'ext': 'mp4', 'height': 360, 'format_note': '3D', 'acodec': 'aac', 'audio_bitrate': 128, 'vcodec': 'h264'},
    '83': {'ext': 'mp4', 'height': 480, 'format_note': '3D', 'acodec': 'aac', 'audio_bitrate': 128, 'vcodec': 'h264'},
    '84': {'ext': 'mp4', 'height': 720, 'format_note': '3D', 'acodec': 'aac', 'audio_bitrate': 192, 'vcodec': 'h264'},
    '85': {'ext': 'mp4', 'height': 1080, 'format_note': '3D', 'acodec': 'aac', 'audio_bitrate': 192, 'vcodec': 'h264'},
    '100': {'ext': 'webm', 'height': 360, 'format_note': '3D', 'acodec': 'vorbis', 'audio_bitrate': 128, 'vcodec': 'vp8'},
    '101': {'ext': 'webm', 'height': 480, 'format_note': '3D', 'acodec': 'vorbis', 'audio_bitrate': 192, 'vcodec': 'vp8'},
    '102': {'ext': 'webm', 'height': 720, 'format_note': '3D', 'acodec': 'vorbis', 'audio_bitrate': 192, 'vcodec': 'vp8'},

    # Apple HTTP Live Streaming
    '91': {'ext': 'mp4', 'height': 144, 'format_note': 'HLS', 'acodec': 'aac', 'audio_bitrate': 48, 'vcodec': 'h264'},
    '92': {'ext': 'mp4', 'height': 240, 'format_note': 'HLS', 'acodec': 'aac', 'audio_bitrate': 48, 'vcodec': 'h264'},
    '93': {'ext': 'mp4', 'height': 360, 'format_note': 'HLS', 'acodec': 'aac', 'audio_bitrate': 128, 'vcodec': 'h264'},
    '94': {'ext': 'mp4', 'height': 480, 'format_note': 'HLS', 'acodec': 'aac', 'audio_bitrate': 128, 'vcodec': 'h264'},
    '95': {'ext': 'mp4', 'height': 720, 'format_note': 'HLS', 'acodec': 'aac', 'audio_bitrate': 256, 'vcodec': 'h264'},
    '96': {'ext': 'mp4', 'height': 1080, 'format_note': 'HLS', 'acodec': 'aac', 'audio_bitrate': 256, 'vcodec': 'h264'},
    '132': {'ext': 'mp4', 'height': 240, 'format_note': 'HLS', 'acodec': 'aac', 'audio_bitrate': 48, 'vcodec': 'h264'},
    '151': {'ext': 'mp4', 'height': 72, 'format_note': 'HLS', 'acodec': 'aac', 'audio_bitrate': 24, 'vcodec': 'h264'},

    # DASH mp4 video
    '133': {'ext': 'mp4', 'height': 240, 'format_note': 'DASH video', 'vcodec': 'h264'},
    '134': {'ext': 'mp4', 'height': 360, 'format_note': 'DASH video', 'vcodec': 'h264'},
    '135': {'ext': 'mp4', 'height': 480, 'format_note': 'DASH video', 'vcodec': 'h264'},
    '136': {'ext': 'mp4', 'height': 720, 'format_note': 'DASH video', 'vcodec': 'h264'},
    '137': {'ext': 'mp4', 'height': 1080, 'format_note': 'DASH video', 'vcodec': 'h264'},
    '138': {'ext': 'mp4', 'format_note': 'DASH video', 'vcodec': 'h264'},  # Height can vary (https://github.com/ytdl-org/youtube-dl/issues/4559)
    '160': {'ext': 'mp4', 'height': 144, 'format_note': 'DASH video', 'vcodec': 'h264'},
    '212': {'ext': 'mp4', 'height': 480, 'format_note': 'DASH video', 'vcodec': 'h264'},
    '264': {'ext': 'mp4', 'height': 1440, 'format_note': 'DASH video', 'vcodec': 'h264'},
    '298': {'ext': 'mp4', 'height': 720, 'format_note': 'DASH video', 'vcodec': 'h264', 'fps': 60},
    '299': {'ext': 'mp4', 'height': 1080, 'format_note': 'DASH video', 'vcodec': 'h264', 'fps': 60},
    '266': {'ext': 'mp4', 'height': 2160, 'format_note': 'DASH video', 'vcodec': 'h264'},

    # Dash mp4 audio
    '139': {'ext': 'm4a', 'format_note': 'DASH audio', 'acodec': 'aac', 'audio_bitrate': 48, 'container': 'm4a_dash'},
    '140': {'ext': 'm4a', 'format_note': 'DASH audio', 'acodec': 'aac', 'audio_bitrate': 128, 'container': 'm4a_dash'},
    '141': {'ext': 'm4a', 'format_note': 'DASH audio', 'acodec': 'aac', 'audio_bitrate': 256, 'container': 'm4a_dash'},
    '256': {'ext': 'm4a', 'format_note': 'DASH audio', 'acodec': 'aac', 'container': 'm4a_dash'},
    '258': {'ext': 'm4a', 'format_note': 'DASH audio', 'acodec': 'aac', 'container': 'm4a_dash'},
    '325': {'ext': 'm4a', 'format_note': 'DASH audio', 'acodec': 'dtse', 'container': 'm4a_dash'},
    '328': {'ext': 'm4a', 'format_note': 'DASH audio', 'acodec': 'ec-3', 'container': 'm4a_dash'},

    # Dash webm
    '167': {'ext': 'webm', 'height': 360, 'width': 640, 'format_note': 'DASH video', 'container': 'webm', 'vcodec': 'vp8'},
    '168': {'ext': 'webm', 'height': 480, 'width': 854, 'format_note': 'DASH video', 'container': 'webm', 'vcodec': 'vp8'},
    '169': {'ext': 'webm', 'height': 720, 'width': 1280, 'format_note': 'DASH video', 'container': 'webm', 'vcodec': 'vp8'},
    '170': {'ext': 'webm', 'height': 1080, 'width': 1920, 'format_note': 'DASH video', 'container': 'webm', 'vcodec': 'vp8'},
    '218': {'ext': 'webm', 'height': 480, 'width': 854, 'format_note': 'DASH video', 'container': 'webm', 'vcodec': 'vp8'},
    '219': {'ext': 'webm', 'height': 480, 'width': 854, 'format_note': 'DASH video', 'container': 'webm', 'vcodec': 'vp8'},
    '278': {'ext': 'webm', 'height': 144, 'format_note': 'DASH video', 'container': 'webm', 'vcodec': 'vp9'},
    '242': {'ext': 'webm', 'height': 240, 'format_note': 'DASH video', 'vcodec': 'vp9'},
    '243': {'ext': 'webm', 'height': 360, 'format_note': 'DASH video', 'vcodec': 'vp9'},
    '244': {'ext': 'webm', 'height': 480, 'format_note': 'DASH video', 'vcodec': 'vp9'},
    '245': {'ext': 'webm', 'height': 480, 'format_note': 'DASH video', 'vcodec': 'vp9'},
    '246': {'ext': 'webm', 'height': 480, 'format_note': 'DASH video', 'vcodec': 'vp9'},
    '247': {'ext': 'webm', 'height': 720, 'format_note': 'DASH video', 'vcodec': 'vp9'},
    '248': {'ext': 'webm', 'height': 1080, 'format_note': 'DASH video', 'vcodec': 'vp9'},
    '271': {'ext': 'webm', 'height': 1440, 'format_note': 'DASH video', 'vcodec': 'vp9'},
    # itag 272 videos are either 3840x2160 (e.g. RtoitU2A-3E) or 7680x4320 (sLprVF6d7Ug)
    '272': {'ext': 'webm', 'height': 2160, 'format_note': 'DASH video', 'vcodec': 'vp9'},
    '302': {'ext': 'webm', 'height': 720, 'format_note': 'DASH video', 'vcodec': 'vp9', 'fps': 60},
    '303': {'ext': 'webm', 'height': 1080, 'format_note': 'DASH video', 'vcodec': 'vp9', 'fps': 60},
    '308': {'ext': 'webm', 'height': 1440, 'format_note': 'DASH video', 'vcodec': 'vp9', 'fps': 60},
    '313': {'ext': 'webm', 'height': 2160, 'format_note': 'DASH video', 'vcodec': 'vp9'},
    '315': {'ext': 'webm', 'height': 2160, 'format_note': 'DASH video', 'vcodec': 'vp9', 'fps': 60},

    # Dash webm audio
    '171': {'ext': 'webm', 'acodec': 'vorbis', 'format_note': 'DASH audio', 'audio_bitrate': 128},
    '172': {'ext': 'webm', 'acodec': 'vorbis', 'format_note': 'DASH audio', 'audio_bitrate': 256},

    # Dash webm audio with opus inside
    '249': {'ext': 'webm', 'format_note': 'DASH audio', 'acodec': 'opus', 'audio_bitrate': 50},
    '250': {'ext': 'webm', 'format_note': 'DASH audio', 'acodec': 'opus', 'audio_bitrate': 70},
    '251': {'ext': 'webm', 'format_note': 'DASH audio', 'acodec': 'opus', 'audio_bitrate': 160},

    # RTMP (unnamed)
    '_rtmp': {'protocol': 'rtmp'},

    # av01 video only formats sometimes served with "unknown" codecs
    '394': {'vcodec': 'av01.0.05M.08'},
    '395': {'vcodec': 'av01.0.05M.08'},
    '396': {'vcodec': 'av01.0.05M.08'},
    '397': {'vcodec': 'av01.0.05M.08'},
}


def _extract_from_video_information_renderer(renderer_content):
    subtitle = extract_str(renderer_content.get('expandedSubtitle'),
                           default='')
    info = {
        'title': extract_str(renderer_content.get('title')),
        'view_count': extract_int(subtitle),
        'unlisted': False,
        'live': 'watching' in subtitle,
    }
    for badge in renderer_content.get('badges', []):
        if deep_get(badge, 'metadataBadgeRenderer', 'label') == 'Unlisted':
            info['unlisted'] = True
    return info

def _extract_likes_dislikes(renderer_content):
    def extract_button_count(toggle_button_renderer):
        # all the digits can be found in the accessibility data
        count = extract_int(multi_deep_get(
            toggle_button_renderer,
            ['defaultText', 'accessibility', 'accessibilityData', 'label'],
            ['accessibility', 'label'],
            ['accessibilityData', 'accessibilityData', 'label'],
            ['accessibilityText'],
        ))

        # this count doesn't have all the digits, it's like 53K for instance
        dumb_count = extract_int(extract_str(multi_get(
            toggle_button_renderer, ['defaultText', 'title'])))

        # The accessibility text will be "No likes" or "No dislikes" or
        # something like that, but dumb count will be 0
        if dumb_count == 0:
            count = 0
        return count

    info = {
        'like_count': None,
        'dislike_count': None,
    }
    for button in renderer_content.get('buttons', ()):
        if 'slimMetadataToggleButtonRenderer' in button:
            button_renderer = button['slimMetadataToggleButtonRenderer']
            count = extract_button_count(deep_get(button_renderer,
                                                  'button',
                                                  'toggleButtonRenderer'))
            if 'isLike' in button_renderer:
                info['like_count'] = count
            elif 'isDislike' in button_renderer:
                info['dislike_count'] = count
        elif 'slimMetadataButtonRenderer' in button:
            button_renderer = button['slimMetadataButtonRenderer']
            liberal_update(info, 'like_count', extract_button_count(
                multi_deep_get(button_renderer,
                    ['button', 'segmentedLikeDislikeButtonRenderer',
                     'likeButton', 'toggleButtonRenderer'],
                    ['button', 'segmentedLikeDislikeButtonViewModel',
                     'likeButtonViewModel', 'likeButtonViewModel',
                     'toggleButtonViewModel', 'toggleButtonViewModel',
                     'defaultButtonViewModel', 'buttonViewModel']
                )
            ))
            '''liberal_update(info, 'dislike_count', extract_button_count(
                deep_get(
                    button_renderer, 'button',
                    'segmentedLikeDislikeButtonRenderer',
                    'dislikeButton', 'toggleButtonRenderer'
                )
            ))'''
    return info

def _extract_from_owner_renderer(renderer_content):
    return {
        'author': extract_str(renderer_content.get('title')),
        'author_id': deep_get(
            renderer_content,
            'navigationEndpoint', 'browseEndpoint', 'browseId'),
    }

def _extract_from_video_header_renderer(renderer_content):
    return {
        'title': extract_str(renderer_content.get('title')),
        'time_published': extract_date(extract_str(
            renderer_content.get('publishDate'))),
    }

def _extract_from_description_renderer(renderer_content):
    return {
        'description': extract_str(
            renderer_content.get('descriptionBodyText'), recover_urls=True),
    }

def _extract_metadata_row_info(renderer_content):
    # extract category and music list
    info = {
        'category': None,
        'music_list': [],
    }

    current_song = {}
    for row in deep_get(renderer_content, 'rows', default=[]):
        row_title = extract_str(deep_get(row, 'metadataRowRenderer', 'title'), default='')
        row_content = extract_str(deep_get(row, 'metadataRowRenderer', 'contents', 0))
        if row_title == 'Category':
            info['category'] = row_content
        elif row_title in ('Song', 'Music'):
            if current_song:
                info['music_list'].append(current_song)
            current_song = {'title': row_content}
        elif row_title == 'Artist':
            current_song['artist'] = row_content
        elif row_title == 'Album':
            current_song['album'] = row_content
        elif row_title == 'Writers':
            current_song['writers'] = row_content
        elif row_title.startswith('Licensed'):
            current_song['licensor'] = row_content
    if current_song:
        info['music_list'].append(current_song)

    return info

def _extract_from_music_renderer(renderer_content):
    # latest format for the music list
    info = {
        'music_list': [],
    }

    for carousel in renderer_content.get('carouselLockups', []):
        song = {}
        carousel = carousel.get('carouselLockupRenderer', {})
        video_renderer = carousel.get('videoLockup', {})
        video_renderer_info = extract_item_info(video_renderer)
        video_id = video_renderer_info.get('id')
        song['url'] = concat_or_none('https://www.youtube.com/watch?v=',
                                     video_id)
        song['title'] = video_renderer_info.get('title')
        for row in carousel.get('infoRows', []):
            row = row.get('infoRowRenderer', {})
            title = extract_str(row.get('title'))
            data = extract_str(row.get('defaultMetadata'))
            if title == 'SONG':
                song['title'] = data
            elif title == 'ARTIST':
                song['artist'] = data
            elif title == 'ALBUM':
                song['album'] = data
            elif title == 'WRITERS':
                song['writers'] = data
        info['music_list'].append(song)
    return info

def _extract_from_video_metadata(renderer_content):
    info = _extract_from_video_information_renderer(renderer_content)
    liberal_dict_update(info, _extract_likes_dislikes(renderer_content))
    liberal_dict_update(info, _extract_from_owner_renderer(renderer_content))
    liberal_dict_update(info, _extract_metadata_row_info(deep_get(
        renderer_content, 'metadataRowContainer',
        'metadataRowContainerRenderer', default={}
    )))
    liberal_update(info, 'title', extract_str(renderer_content.get('title')))
    liberal_update(
        info, 'description',
        extract_str(renderer_content.get('description'), recover_urls=True)
    )
    liberal_update(info, 'time_published',
                   extract_date(renderer_content.get('dateText')))
    return info

visible_extraction_dispatch = {
    # Either these ones spread around in various places
    'slimVideoInformationRenderer': _extract_from_video_information_renderer,
    'slimVideoActionBarRenderer': _extract_likes_dislikes,
    'slimOwnerRenderer': _extract_from_owner_renderer,
    'videoDescriptionHeaderRenderer': _extract_from_video_header_renderer,
    'videoDescriptionMusicSectionRenderer': _extract_from_music_renderer,
    'expandableVideoDescriptionRenderer': _extract_from_description_renderer,
    'metadataRowContainerRenderer': _extract_metadata_row_info,
    # OR just this one, which contains SOME of the above inside it
    'slimVideoMetadataRenderer': _extract_from_video_metadata,
}

def _extract_watch_info_mobile(top_level):
    '''Scrapes information from the visible page'''
    info = {}
    response = top_level.get('response', {})

    # this renderer has the stuff visible on the page
    # check for playlist
    items, _ = extract_items(response,
        item_types={'singleColumnWatchNextResults'})
    if items:
        watch_next_results = items[0]['singleColumnWatchNextResults']
        playlist = deep_get(watch_next_results, 'playlist', 'playlist')
        if playlist is None:
            info['playlist'] = None
        else:
            info['playlist'] = {}
            info['playlist']['title'] = playlist.get('title')
            info['playlist']['author'] = extract_str(multi_get(playlist,
                'ownerName', 'longBylineText', 'shortBylineText', 'ownerText'))
            author_id = deep_get(playlist, 'longBylineText', 'runs', 0,
                'navigationEndpoint', 'browseEndpoint', 'browseId')
            info['playlist']['author_id'] = author_id
            info['playlist']['author_url'] = concat_or_none(
                'https://www.youtube.com/channel/', author_id)
            info['playlist']['id'] = playlist.get('playlistId')
            info['playlist']['url'] = concat_or_none(
                'https://www.youtube.com/playlist?list=',
                info['playlist']['id'])
            info['playlist']['video_count'] = playlist.get('totalVideos')
            info['playlist']['current_index'] = playlist.get('currentIndex')
            info['playlist']['items'] = [
                extract_item_info(i) for i in playlist.get('contents', ())]
    else:
        info['playlist'] = None

    # use dispatch table to get information scattered in various renderers
    items, _ = extract_items(
        response,
        item_types=visible_extraction_dispatch.keys(),
        search_engagement_panels=True
    )
    found = set()
    for renderer in items:
        name, renderer_content = list(renderer.items())[0]
        found.add(name)
        liberal_dict_update(
            info,
            visible_extraction_dispatch[name](renderer_content)
        )
    # Call the function on blank dict for any that weren't found
    # so that the empty keys get added
    for name in visible_extraction_dispatch.keys() - found:
        liberal_dict_update(info, visible_extraction_dispatch[name]({}))

    # comment section info
    items, _ = extract_items(response, item_types={
        'commentSectionRenderer', 'commentsEntryPointHeaderRenderer'})
    if items:
        header_type = list(items[0])[0]
        comment_info = items[0][header_type]
        # This seems to be some kind of A/B test being done on mobile, where
        # this is present instead of the normal commentSectionRenderer. It can
        # be seen here:
        # https://www.androidpolice.com/2019/10/31/google-youtube-app-comment-section-below-videos/
        # https://www.youtube.com/watch?v=bR5Q-wD-6qo
        if header_type == 'commentsEntryPointHeaderRenderer':
            comment_count_text = extract_str(multi_get(
                comment_info, 'commentCount', 'headerText'))
        else:
            comment_count_text = extract_str(deep_get(comment_info,
                'header', 'commentSectionHeaderRenderer', 'countText'))
        if comment_count_text == 'Comments':    # just this with no number, means 0 comments
            info['comment_count'] = '0'
        else:
            info['comment_count'] = extract_approx_int(comment_count_text)
        info['comments_disabled'] = False
    else:   # no comment section present means comments are disabled
        info['comment_count'] = '0'
        info['comments_disabled'] = True

    # check for limited state
    items, _ = extract_items(response, item_types={'limitedStateMessageRenderer'})
    if items:
        info['limited_state'] = True
    else:
        info['limited_state'] = False

    # related videos
    related, _ = extract_items(response)
    info['related_videos'] = [extract_item_info(renderer) for renderer in related]

    return info

def _extract_watch_info_desktop(top_level):
    info = {
        'comment_count': None,
        'comments_disabled': None,
        'limited_state': None,
        'playlist': None,
    }

    video_info = {}
    for renderer in deep_get(top_level, 'response', 'contents', 'twoColumnWatchNextResults', 'results', 'results', 'contents', default=()):
        if renderer and list(renderer.keys())[0] in ('videoPrimaryInfoRenderer', 'videoSecondaryInfoRenderer'):
            video_info.update(list(renderer.values())[0])

    info.update(_extract_metadata_row_info(video_info))
    info['description'] = extract_str(video_info.get('description', None), recover_urls=True)
    info['time_published'] = extract_date(extract_str(video_info.get('dateText', None)))

    likes_dislikes = deep_get(video_info, 'sentimentBar', 'sentimentBarRenderer', 'tooltip', default='').split('/')
    if len(likes_dislikes) == 2:
        info['like_count'] = extract_int(likes_dislikes[0])
        info['dislike_count'] = extract_int(likes_dislikes[1])
    else:
        info['like_count'] = None
        info['dislike_count'] = None

    info['title'] = extract_str(video_info.get('title', None))
    info['author'] = extract_str(deep_get(video_info, 'owner', 'videoOwnerRenderer', 'title'))
    info['author_id'] = deep_get(video_info, 'owner', 'videoOwnerRenderer', 'navigationEndpoint', 'browseEndpoint', 'browseId')
    info['view_count'] = extract_int(extract_str(deep_get(video_info, 'viewCount', 'videoViewCountRenderer', 'viewCount')))

    related = deep_get(top_level, 'response', 'contents', 'twoColumnWatchNextResults', 'secondaryResults', 'secondaryResults', 'results', default=[])
    info['related_videos'] = [extract_item_info(renderer) for renderer in related]

    return info

def update_format_with_codec_info(fmt, codec):
    if any(codec.startswith(c) for c in ('av', 'vp', 'h263', 'h264', 'mp4v')):
        if codec == 'vp8.0':
            codec = 'vp8'
        conservative_update(fmt, 'vcodec', codec)
    elif (codec.startswith('mp4a')
            or codec in ('opus', 'mp3', 'aac', 'dtse', 'ec-3', 'vorbis',
                        'ac-3')):
        conservative_update(fmt, 'acodec', codec)
    else:
        print('Warning: unrecognized codec: ' + codec)

fmt_type_re = re.compile(
    r'(text|audio|video)/([\w0-9]+); codecs="([^"]+)"')
def update_format_with_type_info(fmt, yt_fmt):
    # 'type' for invidious api format
    mime_type = multi_get(yt_fmt, 'mimeType', 'type')
    if mime_type is None:
        return
    match = re.fullmatch(fmt_type_re, mime_type)
    if match is None:
        print('Warning: Could not read mimetype', mime_type)
        return
    type, fmt['ext'], codecs = match.groups()
    codecs = codecs.split(', ')
    for codec in codecs:
        update_format_with_codec_info(fmt, codec)
    if type == 'audio':
        assert len(codecs) == 1

def _extract_formats(info, player_response):
    streaming_data = player_response.get('streamingData', {})
    yt_formats = streaming_data.get('formats', []) + streaming_data.get('adaptiveFormats', [])

    info['formats'] = []
    # because we may retry the extract_formats with a different player_response
    # so keep what we have
    conservative_update(info, 'hls_manifest_url',
        streaming_data.get('hlsManifestUrl'))
    conservative_update(info, 'dash_manifest_url',
        streaming_data.get('dash_manifest_url'))

    for yt_fmt in yt_formats:
        itag = yt_fmt.get('itag')

        # Translated audio track
        # Example: https://www.youtube.com/watch?v=gF9kkB0UWYQ
        # Only get the original language for now so a foreign
        # translation will not be picked just because it comes first
        if deep_get(yt_fmt, 'audioTrack', 'audioIsDefault') is False:
            continue

        fmt = {}
        fmt['itag'] = itag
        fmt['ext'] = None
        fmt['audio_bitrate'] = None
        fmt['bitrate'] = yt_fmt.get('bitrate')
        fmt['acodec'] = None
        fmt['vcodec'] = None
        fmt['width'] = yt_fmt.get('width')
        fmt['height'] = yt_fmt.get('height')
        fmt['file_size'] = extract_int(yt_fmt.get('contentLength'))
        fmt['audio_sample_rate'] = extract_int(yt_fmt.get('audioSampleRate'))
        fmt['duration_ms'] = yt_fmt.get('approxDurationMs')
        fmt['fps'] = yt_fmt.get('fps')
        fmt['init_range'] = yt_fmt.get('initRange')
        fmt['index_range'] = yt_fmt.get('indexRange')
        for key in ('init_range', 'index_range'):
            if fmt[key]:
                fmt[key]['start'] = int(fmt[key]['start'])
                fmt[key]['end'] = int(fmt[key]['end'])
        update_format_with_type_info(fmt, yt_fmt)
        cipher = dict(urllib.parse.parse_qsl(multi_get(yt_fmt,
            'cipher', 'signatureCipher', default='')))
        if cipher:
            fmt['url'] = cipher.get('url')
        else:
            fmt['url'] = yt_fmt.get('url')
        fmt['s'] = cipher.get('s')
        fmt['sp'] = cipher.get('sp')

        # update with information from big table
        hardcoded_itag_info = _formats.get(str(itag), {})
        for key, value in hardcoded_itag_info.items():
            conservative_update(fmt, key, value) # prefer info from Youtube
        fmt['quality'] = hardcoded_itag_info.get('height')
        conservative_update(
            fmt, 'quality',
            extract_int(yt_fmt.get('quality'), whole_word=False)
        )
        conservative_update(
            fmt, 'quality',
            extract_int(yt_fmt.get('qualityLabel'), whole_word=False)
        )

        info['formats'].append(fmt)

    # get ip address
    if info['formats']:
        query_string = (info['formats'][0].get('url') or '?').split('?')[1]
        info['ip_address'] = deep_get(
            urllib.parse.parse_qs(query_string), 'ip', 0)
    else:
        info['ip_address'] = None

hls_regex = re.compile(r'[\w_-]+=(?:"[^"]+"|[^",]+),')
def extract_hls_formats(hls_manifest):
    '''returns hls_formats, err'''
    hls_formats = []
    try:
        lines = hls_manifest.splitlines()
        i = 0
        while i < len(lines):
            if lines[i].startswith('#EXT-X-STREAM-INF'):
                fmt = {'acodec': None, 'vcodec': None, 'height': None,
                    'width': None, 'fps': None, 'audio_bitrate': None,
                    'itag': None, 'file_size': None, 'duration_ms': None,
                    'audio_sample_rate': None, 'url': None}
                properties = lines[i].split(':')[1]
                properties += ',' # make regex work for last key-value pair

                for pair in hls_regex.findall(properties):
                    key, value = pair.rstrip(',').split('=')
                    if key == 'CODECS':
                        for codec in value.strip('"').split(','):
                            update_format_with_codec_info(fmt, codec)
                    elif key == 'RESOLUTION':
                        fmt['width'], fmt['height'] = map(int, value.split('x'))
                        fmt['resolution'] = value
                    elif key == 'FRAME-RATE':
                        fmt['fps'] = int(value)
                i += 1
                fmt['url'] = lines[i]
                assert fmt['url'].startswith('http')
                fmt['ext'] = 'm3u8'
                hls_formats.append(fmt)
            i += 1
    except Exception as e:
        traceback.print_exc()
        return [], str(e)
    return hls_formats, None


def _extract_playability_error(info, player_response, error_prefix=''):
    if info['formats']:
        info['playability_status'] = None
        info['playability_error'] = None
        return

    playability_status = deep_get(player_response, 'playabilityStatus', 'status', default=None)
    info['playability_status'] = playability_status

    playability_reason = extract_str(multi_deep_get(player_response,
        ['playabilityStatus', 'reason'],
        ['playabilityStatus', 'errorScreen', 'playerErrorMessageRenderer', 'reason'],
        default='Could not find playability error')
    )

    if playability_status not in (None, 'OK'):
        info['playability_error'] = error_prefix + playability_reason
    elif not info['playability_error']: # do not override
        info['playability_error'] = error_prefix + 'Unknown playability error'

SUBTITLE_FORMATS = ('srv1', 'srv2', 'srv3', 'ttml', 'vtt')
def extract_watch_info(polymer_json):
    info = {'playability_error': None, 'error': None,
        'player_response_missing': None}

    if isinstance(polymer_json, dict):
        top_level = polymer_json
    elif isinstance(polymer_json, (list, tuple)):
        top_level = {}
        for page_part in polymer_json:
            if not isinstance(page_part, dict):
                return {'error': 'Invalid page part'}
            top_level.update(page_part)
    else:
        return {'error': 'Invalid top level polymer data'}

    error = check_missing_keys(top_level,
        ['player', 'args'],
        ['player', 'assets', 'js'],
        ['playerResponse'],
    )
    if error:
        info['playability_error'] = error

    player_response = top_level.get('playerResponse', {})

    # usually, only the embedded one has the urls
    player_args = deep_get(top_level, 'player', 'args', default={})
    if 'player_response' in player_args:
        embedded_player_response = json.loads(player_args['player_response'])
    else:
        embedded_player_response = {}

    # captions
    info['automatic_caption_languages'] = []
    info['manual_caption_languages'] = []
    info['_manual_caption_language_names'] = {}     # language name written in that language, needed in some cases to create the url
    info['translation_languages'] = []
    captions_info = player_response.get('captions', {})
    info['_captions_base_url'] = normalize_url(deep_get(captions_info, 'playerCaptionsRenderer', 'baseUrl'))
    # Sometimes the above playerCaptionsRender is randomly missing
    # Extract base_url from one of the captions by removing lang specifiers
    if not info['_captions_base_url']:
        base_url = normalize_url(deep_get(
            captions_info,
            'playerCaptionsTracklistRenderer',
            'captionTracks',
            0,
            'baseUrl'
        ))
        if base_url:
            url_parts = urllib.parse.urlparse(base_url)
            qs = urllib.parse.parse_qs(url_parts.query)
            for key in ('tlang', 'lang', 'name', 'kind', 'fmt'):
                if key in qs:
                    del qs[key]
            base_url = urllib.parse.urlunparse(url_parts._replace(
                query=urllib.parse.urlencode(qs, doseq=True)))
            info['_captions_base_url'] = base_url
    for caption_track in deep_get(captions_info, 'playerCaptionsTracklistRenderer', 'captionTracks', default=()):
        lang_code = caption_track.get('languageCode')
        if not lang_code:
            continue
        if caption_track.get('kind') == 'asr':
            info['automatic_caption_languages'].append(lang_code)
        else:
            info['manual_caption_languages'].append(lang_code)
        base_url = caption_track.get('baseUrl', '')
        lang_name = deep_get(urllib.parse.parse_qs(urllib.parse.urlparse(base_url).query), 'name', 0)
        if lang_name:
            info['_manual_caption_language_names'][lang_code] = lang_name

    for translation_lang_info in deep_get(captions_info, 'playerCaptionsTracklistRenderer', 'translationLanguages', default=()):
        lang_code = translation_lang_info.get('languageCode')
        if lang_code:
            info['translation_languages'].append(lang_code)
        if translation_lang_info.get('isTranslatable') == False:
            print('WARNING: Found non-translatable caption language')

    # formats
    _extract_formats(info, embedded_player_response)
    if not info['formats']:
        _extract_formats(info, player_response)

    # see https://github.com/user234683/youtube-local/issues/22#issuecomment-706395160
    info['player_urls_missing'] = (
        not info['formats'] and not embedded_player_response)

    # playability errors
    _extract_playability_error(info, player_response)

    # check age-restriction
    info['age_restricted'] = (info['playability_status'] == 'LOGIN_REQUIRED' and info['playability_error'] and ' age' in info['playability_error'])

    # base_js (for decryption of signatures)
    video_id = deep_get(top_level, 'playerResponse', 'videoDetails', default={}).get('videoId')
    info['base_js'] = deep_get(top_level, 'player', 'assets', 'js')
    #player_version = util.get_player_version(video_id, util.client_xhr_headers)
    player_version_re = re.compile(r'player\\?/([0-9a-fA-F]{8})\\?/')
    player_version = re.search(player_version_re, info['base_js']).group(1)
    info['player_version'] = player_version
    print('yt_data_extract: player_version is ' + player_version)
    try:
        if not os.path.exists(settings.data_dir):
            os.makedirs(settings.data_dir)
        base_js_file = settings.data_dir + '/iframe_api_base_' + player_version + '.js'
        player_url = 'https://www.youtube.com/s/player/' + player_version + '/player_ias.vflset/en_US/base.js'
    except:
        print('Unable to set base_js properties')
    info['base_js'] = player_url
    if info['base_js']:
        info['base_js'] = normalize_url(info['base_js'])
        # must uniquely identify url
        #info['player_name'] = urllib.parse.urlparse(info['base_js']).path
        info['player_name'] = base_js_file
    else:
        info['player_name'] = None

    # extract stuff from visible parts of page
    mobile = 'singleColumnWatchNextResults' in deep_get(top_level, 'response', 'contents', default={})
    if mobile:
        info.update(_extract_watch_info_mobile(top_level))
    else:
        info.update(_extract_watch_info_desktop(top_level))

    # stuff from videoDetails. Use liberal_update to prioritize info from videoDetails over existing info
    vd = deep_get(top_level, 'playerResponse', 'videoDetails', default={})
    liberal_update(info, 'title',      extract_str(vd.get('title')))
    liberal_update(info, 'duration',   extract_int(vd.get('lengthSeconds')))
    liberal_update(info, 'view_count', extract_int(vd.get('viewCount')))
    # videos with no description have a blank string
    liberal_update(info, 'description', vd.get('shortDescription'))
    liberal_update(info, 'id',          vd.get('videoId'))
    liberal_update(info, 'author',      vd.get('author'))
    liberal_update(info, 'author_id',   vd.get('channelId'))
    info['was_live'] =                  vd.get('isLiveContent')
    conservative_update(info, 'unlisted', not vd.get('isCrawlable', True))  #isCrawlable is false on limited state videos even if they aren't unlisted
    liberal_update(info, 'tags',        vd.get('keywords', []))

    # fallback stuff from microformat
    mf = deep_get(top_level, 'playerResponse', 'microformat', 'playerMicroformatRenderer', default={})
    conservative_update(info, 'title',      extract_str(mf.get('title')))
    conservative_update(info, 'duration', extract_int(mf.get('lengthSeconds')))
    # this gives the view count for limited state videos
    conservative_update(info, 'view_count', extract_int(mf.get('viewCount')))
    conservative_update(info, 'description', extract_str(mf.get('description'), recover_urls=True))
    conservative_update(info, 'author', mf.get('ownerChannelName'))
    conservative_update(info, 'author_id', mf.get('externalChannelId'))
    conservative_update(info, 'live', deep_get(mf, 'liveBroadcastDetails',
        'isLiveNow'))
    liberal_update(info, 'unlisted', mf.get('isUnlisted'))
    liberal_update(info, 'category', mf.get('category'))
    liberal_update(info, 'time_published', mf.get('publishDate'))
    liberal_update(info, 'time_uploaded', mf.get('uploadDate'))
    family_safe = mf.get('isFamilySafe')
    if family_safe is None:
        conservative_update(info, 'age_restricted', None)
    else:
        conservative_update(info, 'age_restricted', not family_safe)
    info['allowed_countries'] = mf.get('availableCountries', [])

    # other stuff
    info['author_url'] = 'https://www.youtube.com/channel/' + info['author_id'] if info['author_id'] else None
    info['storyboard_spec_url'] = deep_get(player_response, 'storyboards', 'playerStoryboardSpecRenderer', 'spec')

    return info

single_char_codes = {
    'n': '\n',
    '\\': '\\',
    '"': '"',
    "'": "'",
    'b': '\b',
    'f': '\f',
    'n': '\n',
    'r': '\r',
    't': '\t',
    'v': '\x0b',
    '0': '\x00',
    '\n': '', # backslash followed by literal newline joins lines
}
def js_escape_replace(match):
    r'''Resolves javascript string escape sequences such as \x..'''
    # some js-strings in the watch page html include them for no reason
    # https://mathiasbynens.be/notes/javascript-escapes
    escaped_sequence = match.group(1)
    if escaped_sequence[0] in ('x', 'u'):
        return chr(int(escaped_sequence[1:], base=16))

    # In javascript, if it's not one of those escape codes, it's just the
    # literal character. e.g., "\a" = "a"
    return single_char_codes.get(escaped_sequence, escaped_sequence)

# works but complicated and unsafe:
#PLAYER_RESPONSE_RE = re.compile(r'<script[^>]*?>[^<]*?var ytInitialPlayerResponse = ({(?:"(?:[^"\\]|\\.)*?"|[^"])+?});')

# Because there are sometimes additional statements after the json object
# so we just capture all of those until end of script and tell json decoder
# to ignore extra stuff after the json object
PLAYER_RESPONSE_RE = re.compile(r'<script[^>]*?>[^<]*?var ytInitialPlayerResponse = ({.*?)</script>')
INITIAL_DATA_RE = re.compile(r"<script[^>]*?>var ytInitialData = '(.+?[^\\])';")
BASE_JS_RE = re.compile(r'jsUrl":\s*"([\w\-\./]+?/base.js)"')
JS_STRING_ESCAPE_RE = re.compile(r'\\([^xu]|x..|u....)')
def extract_watch_info_from_html(watch_html):
    base_js_match = BASE_JS_RE.search(watch_html)
    player_response_match = PLAYER_RESPONSE_RE.search(watch_html)
    initial_data_match = INITIAL_DATA_RE.search(watch_html)

    if base_js_match is not None:
        base_js_url = base_js_match.group(1)
    else:
        base_js_url = None

    if player_response_match is not None:
        decoder = json.JSONDecoder()
        # this will make it ignore extra stuff after end of object
        player_response = decoder.raw_decode(player_response_match.group(1))[0]
    else:
        return {'error': 'Could not find ytInitialPlayerResponse'}
        player_response = None

    if initial_data_match is not None:
        initial_data = initial_data_match.group(1)
        initial_data = JS_STRING_ESCAPE_RE.sub(js_escape_replace, initial_data)
        initial_data = json.loads(initial_data)
    else:
        print('extract_watch_info_from_html: failed to find initialData')
        initial_data = None

    # imitate old format expected by extract_watch_info
    fake_polymer_json = {
        'player': {
            'args': {},
            'assets': {
                'js': base_js_url
            }
        },
        'playerResponse': player_response,
        'response': initial_data,
    }

    return extract_watch_info(fake_polymer_json)


def captions_available(info):
    return bool(info['_captions_base_url'])


def get_caption_url(info, language, format, automatic=False, translation_language=None):
    '''Gets the url for captions with the given language and format. If automatic is True, get the automatic captions for that language. If translation_language is given, translate the captions from `language` to `translation_language`. If automatic is true and translation_language is given, the automatic captions will be translated.'''
    url = info['_captions_base_url']
    if not url:
        return None
    url += '&lang=' + language
    url += '&fmt=' + format
    if automatic:
        url += '&kind=asr'
    elif language in info['_manual_caption_language_names']:
        url += '&name=' + urllib.parse.quote(info['_manual_caption_language_names'][language], safe='')

    if translation_language:
        url += '&tlang=' + translation_language
    return url

def update_with_new_urls(info, player_response):
    '''Inserts urls from player_response json'''
    ERROR_PREFIX = 'Error getting missing player or bypassing age-restriction: '

    try:
        player_response = json.loads(player_response)
    except json.decoder.JSONDecodeError:
        traceback.print_exc()
        info['playability_error'] = ERROR_PREFIX + 'Failed to parse json response'
        return

    _extract_formats(info, player_response)
    _extract_playability_error(info, player_response, error_prefix=ERROR_PREFIX)

def requires_decryption(info):
    return ('formats' in info) and info['formats'] and info['formats'][0]['s']

# adapted from youtube-dl and invidious:
# https://github.com/omarroth/invidious/blob/master/src/invidious/helpers/signatures.cr
signature_regex = [
r'\b(?P<var>[a-zA-Z0-9_$]+)&&\((?P=var)=(?P<sig>[a-zA-Z0-9_$]{2,})\(decodeURIComponent\((?P=var)\)\)',
             r'(?P<sig>[a-zA-Z0-9_$]+)\s*=\s*function\(\s*(?P<arg>[a-zA-Z0-9_$]+)\s*\)\s*{\s*(?P=arg)\s*=\s*(?P=arg)\.split\(\s*""\s*\)\s*;\s*[^}]+;\s*return\s+(?P=arg)\.join\(\s*""\s*\)',
             r'(?:\b|[^a-zA-Z0-9_$])(?P<sig>[a-zA-Z0-9_$]{2,})\s*=\s*function\(\s*a\s*\)\s*{\s*a\s*=\s*a\.split\(\s*""\s*\)(?:;[a-zA-Z0-9_$]{2}\.[a-zA-Z0-9_$]{2}\(a,\d+\))?',
             # Old patterns
             r'\b[cs]\s*&&\s*[adf]\.set\([^,]+\s*,\s*encodeURIComponent\s*\(\s*(?P<sig>[a-zA-Z0-9$]+)\(',
             r'\b[a-zA-Z0-9]+\s*&&\s*[a-zA-Z0-9]+\.set\([^,]+\s*,\s*encodeURIComponent\s*\(\s*(?P<sig>[a-zA-Z0-9$]+)\(',
             r'\bm=(?P<sig>[a-zA-Z0-9$]{2,})\(decodeURIComponent\(h\.s\)\)',
             # Obsolete patterns
             r'("|\')signature\1\s*,\s*(?P<sig>[a-zA-Z0-9$]+)\(',
             r'\.sig\|\|(?P<sig>[a-zA-Z0-9$]+)\(',
             r'yt\.akamaized\.net/\)\s*\|\|\s*.*?\s*[cs]\s*&&\s*[adf]\.set\([^,]+\s*,\s*(?:encodeURIComponent\s*\()?\s*(?P<sig>[a-zA-Z0-9$]+)\(',
             r'\b[cs]\s*&&\s*[adf]\.set\([^,]+\s*,\s*(?P<sig>[a-zA-Z0-9$]+)\(',
             r'\bc\s*&&\s*[a-zA-Z0-9]+\.set\([^,]+\s*,\s*\([^)]*\)\s*\(\s*(?P<sig>[a-zA-Z0-9$]+)\(']

def extract_decryption_function(info, base_js):
    '''Insert decryption function into info. Return error string if not successful.
    Decryption function is a list of list[2] of numbers.
    It is advisable to cache the decryption function (uniquely identified by info['player_name']) so base.js (1 MB) doesn't need to be redownloaded each time'''
    decrypt_function_cache = os.path.join(settings.data_dir, f'''signature_func_{info['player_version']}.js''')
    info['decryption_function'] = None
    if os.path.isfile(decrypt_function_cache):
        with open(decrypt_function_cache, 'r') as file:
            print(f'Loading decryption function from cache {os.path.basename(decrypt_function_cache)}')
            decrypt_function_js = file.read()
            info ['decryption_function'] = decrypt_function_js
            return False

    base_js_content = base_js
    for n, item in enumerate(signature_regex):
        decrypt_function_match = re.search(re.compile(item), base_js_content)
        if decrypt_function_match:
            print(f'Match found: {n}')
            sig_func_name = re.escape(decrypt_function_match.group('sig'))
            print(f'signature_function_name is {sig_func_name}')
            break
        else:
            return 'Could not find decryption function in base.js'
    sig_js_code_re = rf'({sig_func_name})' + r'''\s*=\s*(function\(\w\)\{[\S\s]*?\};)'''
    sig_js_code_match = re.search(re.compile(sig_js_code_re), base_js_content)
    if sig_js_code_match:
        sig_js_code = sig_js_code_match.group(2)
    else:
        return f'Could not find function definition for {sig_func_name}'
    global_var, var, _ = extract_player_js_global_var(base_js_content)
    sig_array_name_re = r'(?P<array_name>[\w\$]{2})\[.+?\]\(\w,\d+\);'
    sig_array_name_match = re.search(re.compile(sig_array_name_re), sig_js_code)
    if sig_array_name_match:
        sig_array_name = sig_array_name_match.group('array_name')
    else:
        return 'Could not find decryption signature array name'
    sig_array_re = rf'var {re.escape(sig_array_name)}' + r'''\s*=[\S\s]*?\};'''
    sig_array_match = re.search(re.compile(sig_array_re), base_js_content)
    if sig_array_match:
        sig_array = sig_array_match.group(0)
    else:
        return 'Could not find decryption signature array definition'
    decrypt_function_js = global_var + ';\n' + sig_array + '\n' + 'var decrypt_signature = ' + sig_js_code
    print(f'Extracted decryption function with length {len(decrypt_function_js)}')
    # Saving decryption function cache
    if not os.path.isfile(decrypt_function_cache):
        with open(decrypt_function_cache, 'wb') as file:
            file.write(decrypt_function_js.encode('utf-8'))
            print(f'Decryption function saved as {os.path.basename(decrypt_function_cache)}')
    info['decryption_function'] = decrypt_function_js
    return False

def decrypt_signatures(info):
    '''Applies info['decryption_function'] to decrypt all the signatures. Return err.'''
    if not info.get('decryption_function'):
        return 'decryption_function not in info'
    # Load decryption function into dukpy session
    decrypt_session_dukpy = dukpy.JSInterpreter()
    decrypt_session_dukpy.evaljs(info['decryption_function'])
    for format in info['formats']:
        if not format['s'] or not format['sp'] or not format['url']:
            print('Warning: s, sp, or url not in format')
            continue
        decrypt_signature_dukpy = '''decrypt_signature(dukpy['s'])'''
        signature = decrypt_session_dukpy.evaljs(decrypt_signature_dukpy, s=format['s'])
        format['url'] += '&' + format['sp'] + '=' + urllib.parse.quote(signature)

    return False

def replace_n_signatures(info):
    innertube_client = list(util.INNERTUBE_CLIENTS.keys())
    innertube_client_id = settings.innertube_client_id
    client = innertube_client[innertube_client_id]
    client_params = util.INNERTUBE_CLIENTS[client]

    if not client_params.get('REQUIRE_JS_PLAYER'):
        print('n_sig decryption is not needed for innertube client:' + client)
        return False

    n_sig = None
    player_version = info.get('player_version')
    if not player_version:
        print('n_sig_decrypt: Unable to determine player version')
        return False

    for fmt in info['formats']:
        if fmt['url']:
            media_url = fmt['url']
            params = media_url.split('&')
            for i, member in enumerate(params):
                if member.startswith('n='):
                    n_sig_index = i
                    n_sig = member.split('=')[1]

            if n_sig == None:
                error_message = 'Could not find n signature in query parameters'
                return error_message
            else:
                nsig_decrypt_code_cache = os.path.join(settings.data_dir, 'nsig_func_' + info['player_version'] + '.js')
                def _set_nsig_info():
                    if os.path.exists(nsig_decrypt_code_cache):
                        print('Loading saved nsig func: ' + nsig_decrypt_code_cache)
                        with open(nsig_decrypt_code_cache, 'r') as file:
                            js_nsig_decrypt_code = file.read()
                            info['nsig_func'] = {
                                    player_version: js_nsig_decrypt_code
                                    }
                            file.close()
                    else:
                        with open(info['player_name'], 'r') as file:
                            base_js = file.read()
                            file.close()

                        js_nsig_decrypt_code = extract_nsig_func(base_js)
                        info['nsig_func'] = {
                                player_version: js_nsig_decrypt_code
                                }

                        with open(nsig_decrypt_code_cache, 'w') as file:
                            file.write(js_nsig_decrypt_code)
                            file.close()
                            print('nsig func saved as ' + nsig_decrypt_code_cache)
                if not info.get('nsig_func'):
                    info['nsig_func'] = {}
                    _set_nsig_info()
                    js_nsig_decrypt_code = info['nsig_func'].get(player_version)
                else:
                    if info['nsig_func'].get(player_version):
                        js_nsig_decrypt_code = info['nsig_func'].get(player_version)
                    else:
                        _set_nsig_info()
                        js_nsig_decrypt_code = info['nsig_func'].get(player_version)
                n_sig_result = decrypt_n_signature(n_sig=n_sig, jscode=js_nsig_decrypt_code)
                params.pop(n_sig_index)
                params.insert(n_sig_index, 'n=' + n_sig_result)
                final_url = '&'.join(params)
                fmt['url'] = final_url
    return False

# nsig decryption
# adapted from iv-org/inv_sig_helper
NSIG_FUNCTION_ARRAYS = [ r'''null\)&&\([a-zA-Z]=(?P<nfunc>[_a-zA-Z0-9$]+)\[(?P<idx>\d+)\]\([a-zA-Z0-9]\)''',
            r'''(?x)&&\(b="n+"\[[a-zA-Z0-9.+$]+\],c=a\.get\(b\)\)&&\(c=(?P<nfunc>[a-zA-Z0-9$]+)(?:\[(?P<idx>\d+)\])?\([a-zA-Z0-9]\)'''
]

NSIG_FUNCTION_ENDINGS = [
    r'=\s*function([\S\s]*?\}\s*return [A-Za-z0-9\$]+\[[A-Za-z0-9\$]+\[\d+\]\]\([A-Za-z0-9\$]+\[\d+\]\)\s*\};)',
    r'=\s*function(\(\w\)\s*\{[\S\s]*\{return.[a-zA-Z0-9_-]+_w8_.+?\}\s*return\s*\w+\.join\(""\)\};)',
    r'=\s*function([\S\s]*?\}\s*return \w+?\.join\([^)]+\)\s*\};)',
    r'=\s*function([\S\s]*?\}\s*?return \w+?\.join\(\"\"\)\s*\};)',
    r'=\s*function([\S\s]*?\}\s*return [\W\w\\$]+?\.call\([\w\\$]+?,\"\"\)\s*\};)',
]

def extract_nsig_func(base_js):
    regex = re
    for i, member in enumerate(NSIG_FUNCTION_ARRAYS):
        func_array_re = regex.compile(member)
        func_array = regex.search(func_array_re, base_js)
        if not func_array == None:
            func_name = func_array.group(1)
            break
    NSIG_CONTEXT = 'var '+re.escape(func_name)+'\\s*=\\s*\\[(.+?)][;,]'
    func_context = regex.search(regex.compile(NSIG_CONTEXT), base_js)
    func_body_re = []
    for i, member in enumerate(NSIG_FUNCTION_ENDINGS):
        func_body_re_item = ''
        func_body_re_item += re.escape(func_context.group(1))
        func_body_re_item += member
        func_body_re.append(func_body_re_item)
    nsig_func_body = None
    for i, member in enumerate(func_body_re):
        result = regex.search(regex.compile(member), base_js)
        if result:
            nsig_func_body = result.group(1)
            print('nsig_func_body length: ' + str(len(nsig_func_body)))
            break
    if nsig_func_body:
        nsig_func_name = 'decrypt_nsig'
        full_nsig_func = 'var ' + nsig_func_name + '=function' + nsig_func_body
        return fixup_nsig_jscode(jscode=full_nsig_func, player_js=base_js)
    else:
        return None

def extract_player_js_global_var(jscode):
    regex = r'''(?x)
        'use\s+strict';\s*
        (?P<code>
            var\s+(?P<name>[a-zA-Z0-9_\$]+)\s*=\s*
            (?P<value>
                (?:"[^"\\]*(?:\\.[^"\\]*)*"|'[^'\\]*(?:\\.[^'\\]*)*')
                \.split\((?:"[^"\\]*(?:\\.[^"\\]*)*"|'[^'\\]*(?:\\.[^'\\]*)*')\)
                |\[(?:(?:"[^"\\]*(?:\\.[^"\\]*)*"|'[^'\\]*(?:\\.[^'\\]*)*')\s*,?\s*)*\]
                |"[^"]*"\.split\("[^"]*"\)
            )
        )[;,]'''
    regex_search = re.search(re.compile(regex), jscode)
    code, name, value = regex_search.group('code', 'name', 'value')
    return code, name, value

def fixup_nsig_jscode(jscode, player_js):
    param_re = re.compile(r'function\s+[a-zA-Z0-9_\$]+\s*\(([a-zA-Z0-9_\$]+)\)')
    param_search = re.search(param_re, jscode)
    if param_search:
        param_name = param_search.group(1)
    global_var, varname, _ = extract_player_js_global_var(player_js)
    escaped_varname = re.escape(varname)
    if global_var:
        print(f'Prepending n function code with global array variable {escaped_varname}')
        result = global_var + '; ' + jscode
        fixup_re = re.compile(rf''';\s*if\s*\(\s*typeof\s+[a-zA-Z0-9_\$]+\s*===?\s*(?:"undefined"|'undefined'|{escaped_varname}\[\d+\])\s*\)\s*return\s+\w+;''')
    else:
        print('No global array variable found in player JS')
        result = jscode
        fixup_re = re.compile(r';\s*if\s*\(\s*typeof\s+[a-zA-Z0-9_\$]+\s*===?\s*"undefined"\s*\)\s*return\s+\w+;')
    if fixup_re.search(result):
        result = re.sub(fixup_re, ';', result)
    else:
        print('nsig_func returned with no fixup')
    return result

def decrypt_n_signature(n_sig, jscode):
    dukpy_session = dukpy.JSInterpreter()
    # Loading the function into dukpy session
    dukpy_session.evaljs(jscode)
    #n_sig_result = dukpy_session.evaljs('decrypt_nsig("' + n_sig + '")')
    n_sig_result = dukpy_session.evaljs("decrypt_nsig(dukpy['n'])", n=n_sig)
    return n_sig_result

def append_po_token(info):
    if not settings.use_po_token:
        return False
    else:
        po_token_cache = os.path.join(settings.data_dir, 'po_token_cache.txt')
        if os.path.exists(po_token_cache):
            with open(po_token_cache, 'r') as file:
                po_token_dict = json.loads(file.read())
            info['poToken'] = po_token_dict.get('poToken')
            po_token = info['poToken']
            if po_token:
                for fmt in info['formats']:
                    fmt['url'] += f'&pot={po_token}'
                return False
