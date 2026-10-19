"""Exceptions for the pagination framework.
"""

class PaginationError(Exception):
    """Base class for pagination related errors."""
    pass


class InvalidPageError(PaginationError):
    """Raised when a page identifier is malformed or invalid."""
    pass


class EmptyPaginatorError(PaginationError):
    """Raised when attempting to paginate an empty collection."""
    pass


class PageOutOfBoundsError(PaginationError):
    """Raised when navigation attempts to go beyond available pages."""
    pass
