class HTMLParsingException(Exception):
    """
    This exception is thrown when the html tags are not parsed.
    Based on the type of exception, we shall be creating statistics.
    """
    pass


class ProxyFailureException(Exception):
    """
    This exception is thrown when the poxy is failed.
    Based on the type of exception, we shall be creating statistics.
    """
    pass