import pytest

from youtube.yt_data_extract.common import extract_item_info


@pytest.mark.parametrize('timestamp', [
    '2mo ago', '7mo ago', '2w ago', '3d ago', '4h ago', '5m ago', '6s ago',
    '1y ago', '2 months ago', '1 year ago', '22 hours ago',
])
@pytest.mark.parametrize('source', [
    'published', 'title', 'headline', 'video_info', 'overlay', 'lockup',
])
def test_extract_relative_publication_time(timestamp, source):
    text = '10K views \u2022 Streamed ' + timestamp
    renderers = {
        'published': {'videoRenderer': {
            'publishedTimeText': {'simpleText': timestamp},
        }},
        'title': {'videoRenderer': {
            'title': {'accessibility': {'accessibilityData': {'label': text}}},
        }},
        'headline': {'videoWithContextRenderer': {
            'headline': {
                'accessibility': {'accessibilityData': {'label': text}},
            },
        }},
        'video_info': {'playlistVideoRenderer': {
            'videoInfo': {'runs': [
                {'text': '10K views'}, {'text': ' \u2022 '}, {'text': timestamp},
            ]},
        }},
        'overlay': {'shortsLockupViewModel': {
            'overlayMetadata': {'secondaryText': {'content': text}},
        }},
        'lockup': {'lockupViewModel': {
            'contentType': 'LOCKUP_CONTENT_TYPE_VIDEO',
            'metadata': {'lockupMetadataViewModel': {
                'metadata': {'contentMetadataViewModel': {
                    'metadataRows': [{'metadataParts': [
                        {'text': {'content': text}},
                    ]}],
                }},
            }},
        }},
    }

    info = extract_item_info(renderers[source])

    assert info['time_published'] == timestamp


@pytest.mark.parametrize('timestamp', [None, '', 'LIVE', 'Premieres tomorrow'])
def test_missing_relative_publication_time(timestamp):
    info = extract_item_info({'videoRenderer': {
        'publishedTimeText': (
            {'simpleText': timestamp} if timestamp is not None else None
        ),
    }})

    assert info['time_published'] is None


def test_publication_time_prefers_dedicated_field():
    info = extract_item_info({'videoRenderer': {
        'publishedTimeText': {'simpleText': '2mo ago'},
        'title': {'accessibility': {'accessibilityData': {
            'label': 'A video about events 3 years ago',
        }}},
    }})

    assert info['time_published'] == '2mo ago'
