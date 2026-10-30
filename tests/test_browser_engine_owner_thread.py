"""Deterministic coverage of ThreadOwnedEngineHandle (P10-R1 independent
verification Finding 2).

Playwright's sync API is greenlet-bound to the thread that created it; the
prior close path called ``context.close()`` from a fresh background thread
and the real container run raised ``greenlet.error: Cannot switch to a
different thread``, masked by the completion-flag logic. These tests prove
the remediated ownership model with no Playwright dependency: every
operation AND close execute on the single owner thread; close exceptions
and timeouts are raised to the caller (never swallowed); a wedged owner
thread triggers the independent /proc-based forced-cleanup watchdog.
"""
from __future__ import annotations

import threading

import pytest

from aos.browser.engine import ThreadOwnedEngineHandle


class RecordingInner:
    """Fake inner engine handle recording which thread ran each call."""

    def __init__(self) -> None:
        self.call_threads: dict[str, int] = {}
        self.closed = False

    def navigate(self, url, *, request_validator):  # noqa: ANN001
        self.call_threads["navigate"] = threading.get_ident()
        return ("navigated", url, request_validator(url))

    def read_visible_text(self):  # noqa: ANN201
        self.call_threads["read_visible_text"] = threading.get_ident()
        return "text"

    def fill(self, locator, value):  # noqa: ANN001
        self.call_threads["fill"] = threading.get_ident()
        return True

    def close(self) -> None:
        self.call_threads["close"] = threading.get_ident()
        self.closed = True


class FakeTracker:
    def __init__(self, *, terminate_result: bool = True) -> None:
        self.terminate_calls: list[float] = []
        self.terminate_result = terminate_result

    def terminate_tree(self, *, timeout_seconds: float) -> bool:
        self.terminate_calls.append(timeout_seconds)
        return self.terminate_result

    def sandbox_verified(self) -> bool:
        return True


def _spawn(inner, tracker=None, *, call_timeout=5.0, close_timeout=1.0):  # noqa: ANN001
    return ThreadOwnedEngineHandle.spawn(
        lambda: inner, tracker=tracker,
        call_timeout_seconds=call_timeout, close_timeout_seconds=close_timeout,
    )


def test_every_operation_and_close_run_on_the_same_owner_thread():
    inner = RecordingInner()
    handle = _spawn(inner, FakeTracker())
    handle.navigate("https://x.example/", request_validator=lambda _u: True)
    handle.read_visible_text()
    handle.fill(object(), "v")
    handle.close()
    caller = threading.get_ident()
    owner_idents = set(inner.call_threads.values())
    assert len(owner_idents) == 1, "all calls must run on exactly one thread"
    assert caller not in owner_idents, "the owner thread must not be the caller thread"
    assert inner.call_threads.keys() == {"navigate", "read_visible_text", "fill", "close"}
    assert inner.closed is True


def test_request_validator_callback_executes_on_owner_thread():
    inner = RecordingInner()
    handle = _spawn(inner, FakeTracker())
    seen: list[int] = []
    handle.navigate("https://x.example/", request_validator=lambda _u: seen.append(threading.get_ident()) or True)
    handle.close()
    assert seen == [inner.call_threads["navigate"]]


def test_bootstrap_exception_is_reraised_on_the_calling_thread():
    def bad_bootstrap():  # noqa: ANN202
        raise ValueError("bootstrap exploded")

    with pytest.raises(ValueError, match="bootstrap exploded"):
        ThreadOwnedEngineHandle.spawn(bad_bootstrap, tracker=FakeTracker(), call_timeout_seconds=1.0, close_timeout_seconds=1.0)


def test_inner_operation_exception_propagates_and_handle_stays_usable():
    class RaisingInner(RecordingInner):
        def read_visible_text(self):  # noqa: ANN201
            raise RuntimeError("engine op failed")

    inner = RaisingInner()
    handle = _spawn(inner, FakeTracker())
    with pytest.raises(RuntimeError, match="engine op failed"):
        handle.read_visible_text()
    assert handle.fill(object(), "v") is True  # still alive after an op error
    handle.close()


def test_close_exception_is_raised_to_caller_and_tree_still_swept():
    class CloseFailInner(RecordingInner):
        def close(self) -> None:
            super().close()
            raise RuntimeError("close exploded")

    tracker = FakeTracker()
    handle = _spawn(CloseFailInner(), tracker)
    with pytest.raises(RuntimeError, match="close exploded"):
        handle.close()
    assert tracker.terminate_calls, "forced /proc sweep must still run after a failed graceful close"
    assert handle.is_alive() is False


def test_close_timeout_forces_process_tree_termination_and_raises():
    release = threading.Event()

    class HangingCloseInner(RecordingInner):
        def close(self) -> None:
            release.wait(timeout=30)  # simulates a wedged Playwright driver

    tracker = FakeTracker()
    handle = _spawn(HangingCloseInner(), tracker, close_timeout=0.2)
    with pytest.raises(TimeoutError, match="graceful browser close did not complete"):
        handle.close()
    assert tracker.terminate_calls, "the independent watchdog must terminate the real tree"
    release.set()


def test_close_timeout_reports_failed_forced_cleanup():
    release = threading.Event()

    class HangingCloseInner(RecordingInner):
        def close(self) -> None:
            release.wait(timeout=30)

    handle = _spawn(HangingCloseInner(), FakeTracker(terminate_result=False), close_timeout=0.2)
    with pytest.raises(TimeoutError, match="forced process-tree cleanup also FAILED"):
        handle.close()
    release.set()


def test_wedged_operation_times_out_and_forces_cleanup():
    release = threading.Event()

    class HangingInner(RecordingInner):
        def navigate(self, url, *, request_validator):  # noqa: ANN001
            release.wait(timeout=30)

    tracker = FakeTracker()
    handle = _spawn(HangingInner(), tracker, call_timeout=0.2)
    with pytest.raises(TimeoutError, match="did not complete within the bounded timeout"):
        handle.navigate("https://x.example/", request_validator=lambda _u: True)
    assert tracker.terminate_calls
    assert handle.is_alive() is False
    release.set()


def test_close_is_idempotent_and_calls_after_close_are_rejected():
    inner = RecordingInner()
    handle = _spawn(inner, FakeTracker())
    handle.close()
    handle.close()  # second close is a silent no-op
    with pytest.raises(RuntimeError, match="closed"):
        handle.read_visible_text()


def test_leftover_tree_after_graceful_close_is_surfaced():
    # Graceful close succeeded but real processes remained -- must raise,
    # never silently report success.
    handle = _spawn(RecordingInner(), FakeTracker(terminate_result=False))
    with pytest.raises(TimeoutError, match="still existed after forced cleanup"):
        handle.close()
