from knowledge.llm_run_control import CircuitBreaker, RunCheckpoint, classify_provider_failure


def test_classify_provider_failure_recognizes_rate_limit_and_timeout():
    assert classify_provider_failure("provider_error:HTTPError 429") == "rate_limited"
    assert classify_provider_failure("provider_error:TimeoutError") == "timeout"
    assert classify_provider_failure("provider_error:RemoteDisconnected") == "remote_disconnected"
    assert classify_provider_failure("provider_error:IncompleteRead") == "incomplete_read"


def test_circuit_breaker_opens_after_threshold():
    breaker = CircuitBreaker(failure_threshold=2, cooldown_seconds=60)

    assert breaker.should_pause(now_seconds=100.0) is False
    breaker.record_failure(now_seconds=100.0)
    assert breaker.should_pause(now_seconds=101.0) is False
    breaker.record_failure(now_seconds=102.0)

    assert breaker.should_pause(now_seconds=103.0) is True
    assert breaker.should_pause(now_seconds=163.0) is False


def test_run_checkpoint_skips_completed_observations(tmp_path):
    checkpoint = RunCheckpoint(tmp_path / "checkpoint.jsonl")
    checkpoint.record_completed("E1", "C1", "doc1")

    assert checkpoint.is_completed("E1", "C1", "doc1") is True
    assert checkpoint.is_completed("E1", "C2", "doc1") is False
