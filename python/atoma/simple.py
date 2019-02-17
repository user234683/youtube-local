"""Simple API that abstracts away the differences between feed types."""

from datetime import datetime, timedelta
import html
import os
from typing import Optional, List, Tuple
import urllib.parse

import attr

from . import atom, rss, json_feed
from .exceptions import (
    FeedParseError, FeedDocumentError, FeedXMLError, FeedJSONError
)


@attr.s
class Attachment:
    link: str = attr.ib()
    mime_type: Optional[str] = attr.ib()
    title: Optional[str] = attr.ib()
    size_in_bytes: Optional[int] = attr.ib()
    duration: Optional[timedelta] = attr.ib()


@attr.s
class Article:
    id: str = attr.ib()
    title: Optional[str] = attr.ib()
    link: Optional[str] = attr.ib()
    content: str = attr.ib()
    published_at: Optional[datetime] = attr.ib()
    updated_at: Optional[datetime] = attr.ib()
    attachments: List[Attachment] = attr.ib()


@attr.s
class Feed:
    title: str = attr.ib()
    subtitle: Optional[str] = attr.ib()
    link: Optional[str] = attr.ib()
    updated_at: Optional[datetime] = attr.ib()
    articles: List[Article] = attr.ib()


def _adapt_atom_feed(atom_feed: atom.AtomFeed) -> Feed:
    articles = list()
    for entry in atom_feed.entries:
        if entry.content is not None:
            content = entry.content.value
        elif entry.summary is not None:
            content = entry.summary.value
        else:
            content = ''
        published_at, updated_at = _get_article_dates(entry.published,
                                                      entry.updated)
        # Find article link and attachments
        article_link = None
        attachments = list()
        for candidate_link in entry.links:
            if candidate_link.rel in ('alternate', None):
                article_link = candidate_link.href
            elif candidate_link.rel == 'enclosure':
                attachments.append(Attachment(
                    title=_get_attachment_title(candidate_link.title,
                                                candidate_link.href),
                    link=candidate_link.href,
                    mime_type=candidate_link.type_,
                    size_in_bytes=candidate_link.length,
                    duration=None
                ))

        if entry.title is None:
            entry_title = None
        elif entry.title.text_type in (atom.AtomTextType.html,
                                       atom.AtomTextType.xhtml):
            entry_title = html.unescape(entry.title.value).strip()
        else:
            entry_title = entry.title.value

        articles.append(Article(
            entry.id_,
            entry_title,
            article_link,
            content,
            published_at,
            updated_at,
            attachments
        ))

    # Find feed link
    link = None
    for candidate_link in atom_feed.links:
        if candidate_link.rel == 'self':
            link = candidate_link.href
            break

    return Feed(
        atom_feed.title.value if atom_feed.title else atom_feed.id_,
        atom_feed.subtitle.value if atom_feed.subtitle else None,
        link,
        atom_feed.updated,
        articles
    )


def _adapt_rss_channel(rss_channel: rss.RSSChannel) -> Feed:
    articles = list()
    for item in rss_channel.items:
        attachments = [
            Attachment(link=e.url, mime_type=e.type, size_in_bytes=e.length,
                       title=_get_attachment_title(None, e.url), duration=None)
            for e in item.enclosures
        ]
        articles.append(Article(
            item.guid or item.link,
            item.title,
            item.link,
            item.content_encoded or item.description or '',
            item.pub_date,
            None,
            attachments
        ))

    if rss_channel.title is None and rss_channel.link is None:
        raise FeedParseError('RSS feed does not have a title nor a link')

    return Feed(
        rss_channel.title if rss_channel.title else rss_channel.link,
        rss_channel.description,
        rss_channel.link,
        rss_channel.pub_date,
        articles
    )


def _adapt_json_feed(json_feed: json_feed.JSONFeed) -> Feed:
    articles = list()
    for item in json_feed.items:
        attachments = [
            Attachment(a.url, a.mime_type,
                       _get_attachment_title(a.title, a.url),
                       a.size_in_bytes, a.duration)
            for a in item.attachments
        ]
        articles.append(Article(
            item.id_,
            item.title,
            item.url,
            item.content_html or item.content_text or '',
            item.date_published,
            item.date_modified,
            attachments
        ))

    return Feed(
        json_feed.title,
        json_feed.description,
        json_feed.feed_url,
        None,
        articles
    )


def _get_article_dates(published_at: Optional[datetime],
                       updated_at: Optional[datetime]
                       ) -> Tuple[Optional[datetime], Optional[datetime]]:
    if published_at and updated_at:
        return published_at, updated_at

    if updated_at:
        return updated_at, None

    if published_at:
        return published_at, None

    raise FeedParseError('Article does not have proper dates')


def _get_attachment_title(attachment_title: Optional[str], link: str) -> str:
    if attachment_title:
        return attachment_title

    parsed_link = urllib.parse.urlparse(link)
    return os.path.basename(parsed_link.path)


def _simple_parse(pairs, content) -> Feed:
    is_xml = True
    is_json = True
    for parser, adapter in pairs:
        try:
            return adapter(parser(content))
        except FeedXMLError:
            is_xml = False
        except FeedJSONError:
            is_json = False
        except FeedParseError:
            continue

    if not is_xml and not is_json:
        raise FeedDocumentError('File is not a supported feed type')

    raise FeedParseError('File is not a valid supported feed')


def simple_parse_file(filename: str) -> Feed:
    """Parse an Atom, RSS or JSON feed from a local file."""
    pairs = (
        (rss.parse_rss_file, _adapt_rss_channel),
        (atom.parse_atom_file, _adapt_atom_feed),
        (json_feed.parse_json_feed_file, _adapt_json_feed)
    )
    return _simple_parse(pairs, filename)


def simple_parse_bytes(data: bytes) -> Feed:
    """Parse an Atom, RSS or JSON feed from a byte-string containing data."""
    pairs = (
        (rss.parse_rss_bytes, _adapt_rss_channel),
        (atom.parse_atom_bytes, _adapt_atom_feed),
        (json_feed.parse_json_feed_bytes, _adapt_json_feed)
    )
    return _simple_parse(pairs, data)
