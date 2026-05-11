import enum


class SamplingDecision(enum.Enum):
    RECORD_AND_SEND = "record_and_send"
    RECORD_ONLY = "record_only"


class ErrorBiasedHeadSampler:
    def __init__(self, rate: float) -> None:
        self.rate = rate

    def should_sample(self, trace_id: str) -> SamplingDecision:
        if self.rate >= 1.0:
            return SamplingDecision.RECORD_AND_SEND
        if self.rate <= 0.0:
            return SamplingDecision.RECORD_ONLY
        if (hash(trace_id) % 10000) < int(self.rate * 10000):
            return SamplingDecision.RECORD_AND_SEND
        return SamplingDecision.RECORD_ONLY
