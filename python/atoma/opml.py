from datetime import datetime
from io import BytesIO
from typing import Optional, List
from xml.etree.ElementTree import Element

import attr

from .utils import parse_xml, get_text, get_int, get_datetime


@attr.s
class OPMLOutline:
    text: Optional[str] = attr.ib()
    type: Optional[str] = attr.ib()
    xml_url: Optional[str] = attr.ib()
    description: Optional[str] = attr.ib()
    html_url: Optional[str] = attr.ib()
    language: Optional[str] = attr.ib()
    title: Optional[str] = attr.ib()
    version: Optional[str] = attr.ib()

    outlines: List['OPMLOutline'] = attr.ib()


@attr.s
class OPML:
    title: Optional[str] = attr.ib()
    owner_name: Optional[str] = attr.ib()
    owner_email: Optional[str] = attr.ib()
    date_created: Optional[datetime] = attr.ib()
    date_modified: Optional[datetime] = attr.ib()
    expansion_state: Optional[str] = attr.ib()

    vertical_scroll_state: Optional[int] = attr.ib()
    window_top: Optional[int] = attr.ib()
    window_left: Optional[int] = attr.ib()
    window_bottom: Optional[int] = attr.ib()
    window_right: Optional[int] = attr.ib()

    outlines: List[OPMLOutline] = attr.ib()


def _get_outlines(element: Element) -> List[OPMLOutline]:
    rv = list()

    for outline in element.findall('outline'):
        rv.append(OPMLOutline(
            outline.attrib.get('text'),
            outline.attrib.get('type'),
            outline.attrib.get('xmlUrl'),
            outline.attrib.get('description'),
            outline.attrib.get('htmlUrl'),
            outline.attrib.get('language'),
            outline.attrib.get('title'),
            outline.attrib.get('version'),
            _get_outlines(outline)
        ))

    return rv


def _parse_opml(root: Element) -> OPML:
    head = root.find('head')
    body = root.find('body')

    return OPML(
        get_text(head, 'title'),
        get_text(head, 'ownerName'),
        get_text(head, 'ownerEmail'),
        get_datetime(head, 'dateCreated'),
        get_datetime(head, 'dateModified'),
        get_text(head, 'expansionState'),
        get_int(head, 'vertScrollState'),
        get_int(head, 'windowTop'),
        get_int(head, 'windowLeft'),
        get_int(head, 'windowBottom'),
        get_int(head, 'windowRight'),
        outlines=_get_outlines(body)
    )


def parse_opml_file(filename: str) -> OPML:
    """Parse an OPML document from a local XML file."""
    root = parse_xml(filename).getroot()
    return _parse_opml(root)


def parse_opml_bytes(data: bytes) -> OPML:
    """Parse an OPML document from a byte-string containing XML data."""
    root = parse_xml(BytesIO(data)).getroot()
    return _parse_opml(root)


def get_feed_list(opml_obj: OPML) -> List[str]:
    """Walk an OPML document to extract the list of feed it contains."""
    rv = list()

    def collect(obj):
        for outline in obj.outlines:
            if outline.type == 'rss' and outline.xml_url:
                rv.append(outline.xml_url)

            if outline.outlines:
                collect(outline)

    collect(opml_obj)
    return rv
