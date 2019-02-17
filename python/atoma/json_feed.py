from datetime import datetime, timedelta
import json
from typing import Optional, List

import attr

from .exceptions import FeedParseError, FeedJSONError
from .utils import try_parse_date


@attr.s
class JSONFeedAuthor:

    name: Optional[str] = attr.ib()
    url: Optional[str] = attr.ib()
    avatar: Optional[str] = attr.ib()


@attr.s
class JSONFeedAttachment:

    url: str = attr.ib()
    mime_type: str = attr.ib()
    title: Optional[str] = attr.ib()
    size_in_bytes: Optional[int] = attr.ib()
    duration: Optional[timedelta] = attr.ib()


@attr.s
class JSONFeedItem:

    id_: str = attr.ib()
    url: Optional[str] = attr.ib()
    external_url: Optional[str] = attr.ib()
    title: Optional[str] = attr.ib()
    content_html: Optional[str] = attr.ib()
    content_text: Optional[str] = attr.ib()
    summary: Optional[str] = attr.ib()
    image: Optional[str] = attr.ib()
    banner_image: Optional[str] = attr.ib()
    date_published: Optional[datetime] = attr.ib()
    date_modified: Optional[datetime] = attr.ib()
    author: Optional[JSONFeedAuthor] = attr.ib()

    tags: List[str] = attr.ib()
    attachments: List[JSONFeedAttachment] = attr.ib()


@attr.s
class JSONFeed:

    version: str = attr.ib()
    title: str = attr.ib()
    home_page_url: Optional[str] = attr.ib()
    feed_url: Optional[str] = attr.ib()
    description: Optional[str] = attr.ib()
    user_comment: Optional[str] = attr.ib()
    next_url: Optional[str] = attr.ib()
    icon: Optional[str] = attr.ib()
    favicon: Optional[str] = attr.ib()
    author: Optional[JSONFeedAuthor] = attr.ib()
    expired: bool = attr.ib()

    items: List[JSONFeedItem] = attr.ib()


def _get_items(root: dict) -> List[JSONFeedItem]:
    rv = []
    items = root.get('items', [])
    if not items:
        return rv

    for item in items:
        rv.append(_get_item(item))

    return rv


def _get_item(item_dict: dict) -> JSONFeedItem:
    return JSONFeedItem(
        id_=_get_text(item_dict, 'id', optional=False),
        url=_get_text(item_dict, 'url'),
        external_url=_get_text(item_dict, 'external_url'),
        title=_get_text(item_dict, 'title'),
        content_html=_get_text(item_dict, 'content_html'),
        content_text=_get_text(item_dict, 'content_text'),
        summary=_get_text(item_dict, 'summary'),
        image=_get_text(item_dict, 'image'),
        banner_image=_get_text(item_dict, 'banner_image'),
        date_published=_get_datetime(item_dict, 'date_published'),
        date_modified=_get_datetime(item_dict, 'date_modified'),
        author=_get_author(item_dict),
        tags=_get_tags(item_dict, 'tags'),
        attachments=_get_attachments(item_dict, 'attachments')
    )


def _get_attachments(root, name) -> List[JSONFeedAttachment]:
    rv = list()
    for attachment_dict in root.get(name, []):
        rv.append(JSONFeedAttachment(
            _get_text(attachment_dict, 'url', optional=False),
            _get_text(attachment_dict, 'mime_type', optional=False),
            _get_text(attachment_dict, 'title'),
            _get_int(attachment_dict, 'size_in_bytes'),
            _get_duration(attachment_dict, 'duration_in_seconds')
        ))
    return rv


def _get_tags(root, name) -> List[str]:
    tags = root.get(name, [])
    return [tag for tag in tags if isinstance(tag, str)]


def _get_datetime(root: dict, name, optional: bool=True) -> Optional[datetime]:
    text = _get_text(root, name, optional)
    if text is None:
        return None

    return try_parse_date(text)


def _get_expired(root: dict) -> bool:
    if root.get('expired') is True:
        return True

    return False


def _get_author(root: dict) -> Optional[JSONFeedAuthor]:
    author_dict = root.get('author')
    if not author_dict:
        return None

    rv = JSONFeedAuthor(
        name=_get_text(author_dict, 'name'),
        url=_get_text(author_dict, 'url'),
        avatar=_get_text(author_dict, 'avatar'),
    )
    if rv.name is None and rv.url is None and rv.avatar is None:
        return None

    return rv


def _get_int(root: dict, name: str, optional: bool=True) -> Optional[int]:
    rv = root.get(name)
    if not optional and rv is None:
        raise FeedParseError('Could not parse feed: "{}" int is required but '
                             'is empty'.format(name))

    if optional and rv is None:
        return None

    if not isinstance(rv, int):
        raise FeedParseError('Could not parse feed: "{}" is not an int'
                             .format(name))

    return rv


def _get_duration(root: dict, name: str,
                  optional: bool=True) -> Optional[timedelta]:
    duration = _get_int(root, name, optional)
    if duration is None:
        return None

    return timedelta(seconds=duration)


def _get_text(root: dict, name: str, optional: bool=True) -> Optional[str]:
    rv = root.get(name)
    if not optional and rv is None:
        raise FeedParseError('Could not parse feed: "{}" text is required but '
                             'is empty'.format(name))

    if optional and rv is None:
        return None

    if not isinstance(rv, str):
        raise FeedParseError('Could not parse feed: "{}" is not a string'
                             .format(name))

    return rv


def parse_json_feed(root: dict) -> JSONFeed:
    return JSONFeed(
        version=_get_text(root, 'version', optional=False),
        title=_get_text(root, 'title', optional=False),
        home_page_url=_get_text(root, 'home_page_url'),
        feed_url=_get_text(root, 'feed_url'),
        description=_get_text(root, 'description'),
        user_comment=_get_text(root, 'user_comment'),
        next_url=_get_text(root, 'next_url'),
        icon=_get_text(root, 'icon'),
        favicon=_get_text(root, 'favicon'),
        author=_get_author(root),
        expired=_get_expired(root),
        items=_get_items(root)
    )


def parse_json_feed_file(filename: str) -> JSONFeed:
    """Parse a JSON feed from a local json file."""
    with open(filename) as f:
        try:
            root = json.load(f)
        except json.decoder.JSONDecodeError:
            raise FeedJSONError('Not a valid JSON document')

    return parse_json_feed(root)


def parse_json_feed_bytes(data: bytes) -> JSONFeed:
    """Parse a JSON feed from a byte-string containing JSON data."""
    try:
        root = json.loads(data)
    except json.decoder.JSONDecodeError:
        raise FeedJSONError('Not a valid JSON document')

    return parse_json_feed(root)
