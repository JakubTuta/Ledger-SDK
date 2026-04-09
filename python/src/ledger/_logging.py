import logging

_logger = logging.getLogger("ledger")
if not _logger.handlers:
    _logger.addHandler(logging.NullHandler())


def get_logger() -> logging.Logger:
    return _logger
