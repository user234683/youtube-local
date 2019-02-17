class FeedParseError(Exception):
    """Document is an invalid feed."""


class FeedDocumentError(Exception):
    """Document is not a supported file."""


class FeedXMLError(FeedDocumentError):
    """Document is not valid XML."""


class FeedJSONError(FeedDocumentError):
    """Document is not valid JSON."""
