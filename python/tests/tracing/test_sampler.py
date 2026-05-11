import ledger.tracing.sampler as sampler_module


def test_sample_rate_1_always_sends():
    s = sampler_module.ErrorBiasedHeadSampler(rate=1.0)
    for _ in range(20):
        decision = s.should_sample("any_trace_id")
        assert decision == sampler_module.SamplingDecision.RECORD_AND_SEND


def test_sample_rate_0_never_sends():
    s = sampler_module.ErrorBiasedHeadSampler(rate=0.0)
    for _ in range(20):
        decision = s.should_sample("any_trace_id")
        assert decision == sampler_module.SamplingDecision.RECORD_ONLY


def test_sample_is_deterministic():
    s = sampler_module.ErrorBiasedHeadSampler(rate=0.5)
    trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    first = s.should_sample(trace_id)
    for _ in range(10):
        assert s.should_sample(trace_id) == first


def test_sample_rate_half_roughly_half():
    s = sampler_module.ErrorBiasedHeadSampler(rate=0.5)
    import ledger.tracing.ids as ids_module

    decisions = [s.should_sample(ids_module.generate_trace_id()) for _ in range(1000)]
    send_count = sum(1 for d in decisions if d == sampler_module.SamplingDecision.RECORD_AND_SEND)
    assert 300 < send_count < 700
