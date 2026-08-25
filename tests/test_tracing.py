"""bizstruct_ml.observability.tracing — optional, non-blocking Langfuse tracing."""
import contextlib

import pytest

from bizstruct_ml.observability import tracing


@pytest.fixture(autouse=True)
def _reset_tracing_client_cache():
    """tracing._client / _client_init_attempted are module-level caches —
    reset them around every test so tests don't leak state into each other."""
    tracing._client = None
    tracing._client_init_attempted = False
    yield
    tracing._client = None
    tracing._client_init_attempted = False


class _FakeObservation:
    def __init__(self, name: str, kwargs: dict):
        self.name = name
        self.kwargs = kwargs
        self.updates: list[dict] = []

    def update(self, **kwargs):
        self.updates.append(kwargs)
        return self


class _FakeCM:
    def __init__(self, obs: _FakeObservation):
        self._obs = obs

    def __enter__(self):
        return self._obs

    def __exit__(self, *exc):
        return False  # never suppress


class _FakeClient:
    def __init__(self):
        self.spans_created: list[_FakeObservation] = []
        self.current_span_updates: list[dict] = []
        self.flushed = False

    def start_as_current_observation(self, *, name, as_type="span", **kwargs):
        obs = _FakeObservation(name, {"as_type": as_type, **kwargs})
        self.spans_created.append(obs)
        return _FakeCM(obs)

    def update_current_span(self, **kwargs):
        self.current_span_updates.append(kwargs)

    def flush(self):
        self.flushed = True


# ── Disabled by default (no keys configured in the test environment) ──────────

def test_disabled_by_default_yields_noop_and_never_raises():
    with tracing.trace_block_generation(
        project_id="p1", block="architecture", mode="pipeline",
        attempt_number=1, domain_version="0.1.0",
    ) as root:
        assert root is tracing.NOOP
        with tracing.span("fetch_project") as s:
            assert s is tracing.NOOP
        with tracing.generation_span("llm_call", model="gpt-4o") as g:
            g.update(output={"a": 1})  # must not raise even though disabled
        tracing.update_current_span(metadata={"llm_retry_count": 0})  # must not raise

    tracing.flush()  # must not raise


async def test_aflush_disabled_returns_immediately():
    await tracing.aflush()  # must not raise, must not hang


# ── Mocked client: spans actually get created with expected structure ─────────

def test_mocked_client_creates_expected_span_tree(monkeypatch):
    fake = _FakeClient()
    tracing._client_init_attempted = True
    tracing._client = fake
    monkeypatch.setattr("langfuse.propagate_attributes", lambda **kw: contextlib.nullcontext())

    with tracing.trace_block_generation(
        project_id="proj-1", block="architecture", mode="pipeline",
        attempt_number=2, domain_version="0.1.0",
    ):
        with tracing.span("fetch_project"):
            pass
        with tracing.span("build_prompt") as bp:
            bp.update(output={"context_blocks": ["empathy_map"]})
        with tracing.generation_span("llm_call", model="gpt-4o", input=[{"role": "user"}]) as gen:
            gen.update(output={"epicenter": "customer_driven"}, usage_details={"input": 10, "output": 5})
        with tracing.span("postprocess") as pp:
            pp.update(output={"epicenter": "customer_driven"})
        with tracing.span("send_hook") as hs:
            hs.update(output={"status_code": 200})
        tracing.update_current_span(metadata={"llm_retry_count": 0})

    names = [s.name for s in fake.spans_created]
    assert names == ["generate_block", "fetch_project", "build_prompt", "llm_call", "postprocess", "send_hook"]

    llm_span = fake.spans_created[3]
    assert llm_span.kwargs["as_type"] == "generation"
    assert llm_span.kwargs["model"] == "gpt-4o"
    assert llm_span.updates[-1]["usage_details"] == {"input": 10, "output": 5}

    assert fake.current_span_updates == [{"metadata": {"llm_retry_count": 0}}]


def test_generation_span_records_usage_and_model(monkeypatch):
    fake = _FakeClient()
    tracing._client_init_attempted = True
    tracing._client = fake

    with tracing.generation_span("llm_call", model="gpt-4o-mini") as gen:
        gen.update(usage_details={"input": 100, "output": 40, "total": 140})

    span = fake.spans_created[0]
    assert span.kwargs["model"] == "gpt-4o-mini"
    assert span.updates[0]["usage_details"] == {"input": 100, "output": 40, "total": 140}


# ── A tracing failure never breaks the caller's own code ───────────────────────

def test_exception_inside_span_is_not_swallowed_by_tracing(monkeypatch):
    fake = _FakeClient()
    tracing._client_init_attempted = True
    tracing._client = fake

    with pytest.raises(ValueError, match="boom"):
        with tracing.span("fetch_project"):
            raise ValueError("boom")


def test_client_that_raises_on_every_call_does_not_break_generation(monkeypatch):
    class _ExplodingClient:
        def start_as_current_observation(self, **kwargs):
            raise RuntimeError("langfuse is down")

        def update_current_span(self, **kwargs):
            raise RuntimeError("langfuse is down")

        def flush(self):
            raise RuntimeError("langfuse is down")

    tracing._client_init_attempted = True
    tracing._client = _ExplodingClient()
    monkeypatch.setattr(
        "langfuse.propagate_attributes",
        lambda **kw: (_ for _ in ()).throw(RuntimeError("also down")),
    )

    ran = {"body": False}
    with tracing.trace_block_generation(
        project_id="p1", block="architecture", mode="pipeline",
        attempt_number=1, domain_version="0.1.0",
    ):
        with tracing.span("fetch_project"):
            ran["body"] = True
        tracing.update_current_span(metadata={"x": 1})

    assert ran["body"] is True
    tracing.flush()  # must not raise despite the exploding client


def test_get_client_construction_failure_disables_tracing_gracefully(monkeypatch):
    monkeypatch.setattr("bizstruct_ml.observability.tracing.settings.langfuse_public_key", "pk-test")
    monkeypatch.setattr("bizstruct_ml.observability.tracing.settings.langfuse_secret_key", "sk-test")
    assert tracing.settings.langfuse_enabled is True

    class _BoomLangfuse:
        def __init__(self, **kwargs):
            raise RuntimeError("construction failed")

    monkeypatch.setattr("langfuse.Langfuse", _BoomLangfuse)

    client = tracing._get_client()
    assert client is None
    # subsequent calls must still no-op cleanly, not retry-and-crash
    with tracing.span("x") as s:
        assert s is tracing.NOOP
