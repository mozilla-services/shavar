class BaseError(Exception):
    "Base class for app / service specific errors."


class NoDataError(BaseError):
    "Raised when no data is found in the store."


class ParseError(BaseError):
    "Raised for errors parsing requests."


class MissingListData(BaseError):
    "Raised when we don't know about a list"

