try:
    from importlib.metadata import version

    __version__ = version("ledger-sdk")
except Exception:
    __version__ = "1.2.2"
