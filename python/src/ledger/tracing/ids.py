import os


def generate_trace_id() -> str:
    return os.urandom(16).hex()


def generate_span_id() -> str:
    return os.urandom(8).hex()
