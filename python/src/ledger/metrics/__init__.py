from ledger.metrics.api import MetricsAPI

_metrics_holder: list[MetricsAPI | None] = [None]


def _set_default_metrics(metrics: MetricsAPI | None) -> None:
    _metrics_holder[0] = metrics


def counter(name: str, value: float = 1.0, tags: dict[str, str] | None = None) -> None:
    if _metrics_holder[0] is not None:
        _metrics_holder[0].counter(name, value, tags)


def gauge(name: str, value: float, tags: dict[str, str] | None = None) -> None:
    if _metrics_holder[0] is not None:
        _metrics_holder[0].gauge(name, value, tags)


def histogram(name: str, value: float, tags: dict[str, str] | None = None) -> None:
    if _metrics_holder[0] is not None:
        _metrics_holder[0].histogram(name, value, tags)


__all__ = ["MetricsAPI", "counter", "gauge", "histogram"]
