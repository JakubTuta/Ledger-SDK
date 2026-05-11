import ledger.metrics.aggregator as aggregator_module


class MetricsAPI:
    def __init__(self, aggregator: aggregator_module.Aggregator) -> None:
        self._aggregator = aggregator

    def counter(self, name: str, value: float = 1.0, tags: dict[str, str] | None = None) -> None:
        self._aggregator.counter(name, value, tags)

    def gauge(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        self._aggregator.gauge(name, value, tags)

    def histogram(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        self._aggregator.histogram(name, value, tags)
