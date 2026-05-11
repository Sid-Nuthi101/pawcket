"""Integration-style tests for Session + PawprintProxy + yarn.route_to_thread wiring."""
from __future__ import annotations

import asyncio
import json
import threading
from unittest.mock import MagicMock, patch
from urllib.parse import quote, unquote

import pytest

from session import PawprintProxy, Session, _current_session


def _make_request(
    *,
    path: str = "/t",
    method: str = "GET",
    cookies: dict | None = None,
) -> MagicMock:
    r = MagicMock()
    r.path = path
    r.method = method
    r.cookies = dict(cookies) if cookies else {}
    return r


def _session_cookie_payload(data: dict) -> str:
    return quote(json.dumps(data, separators=(",", ":")))


class TestSessionCookieRoundTrip:
    def test_loads_url_encoded_json_and_serializes_back(self):
        payload = {"user": "ada", "n": 1}
        raw = _session_cookie_payload(payload)
        s = Session(raw)
        assert dict(s) == payload
        round_raw = s.as_cookie_value()
        assert json.loads(unquote(round_raw)) == payload

    def test_invalid_json_does_not_raise_and_leaves_session_empty(self):
        s = Session("%%%not-json%%%")
        assert dict(s) == {}
        assert s.modified is False
        assert s.accessed is False

    def test_non_dict_json_does_not_merge(self):
        s = Session(quote(json.dumps(["a", "b"])))
        assert dict(s) == {}

    def test_none_and_blank_skip_load(self):
        assert dict(Session(None)) == {}
        assert dict(Session("")) == {}
        assert dict(Session("   ")) == {}


class TestSessionAccessModifiedFlags:
    def test_getitem_sets_accessed_only_when_key_exists(self):
        s = Session(_session_cookie_payload({"a": 1}))
        s.accessed = s.modified = False
        _ = s["a"]
        assert s.accessed is True
        assert s.modified is False

    def test_setitem_sets_both_flags(self):
        s = Session()
        s["k"] = "v"
        assert s.accessed is True
        assert s.modified is True

    def test_get_sets_accessed_not_modified(self):
        s = Session(_session_cookie_payload({"x": 2}))
        s.accessed = s.modified = False
        assert s.get("x") == 2
        assert s.accessed is True
        assert s.modified is False

    def test_pop_sets_both_flags(self):
        s = Session(_session_cookie_payload({"y": 3}))
        s.accessed = s.modified = False
        assert s.pop("y") == 3
        assert s.accessed is True
        assert s.modified is True

    def test_clear_sets_both_flags(self):
        s = Session(_session_cookie_payload({"z": 1}))
        s.accessed = s.modified = False
        s.clear()
        assert s.accessed is True
        assert s.modified is True

    def test_update_sets_both_flags(self):
        s = Session()
        s.accessed = s.modified = False
        s.update({"a": 1})
        assert s.accessed is True
        assert s.modified is True


class TestPawprintProxyWithContextVar:
    def test_proxy_reads_and_writes_bound_session(self):
        from pawcket import pawprint  # import after conftest path setup

        inner = Session(_session_cookie_payload({"existing": True}))
        token = _current_session.set(inner)
        try:
            assert pawprint["existing"] is True
            pawprint["new"] = 42
            assert inner["new"] == 42
            assert inner.modified is True
        finally:
            _current_session.reset(token)

    def test_proxy_uses_pawprintproxy_type(self):
        proxy = PawprintProxy()
        s = Session()
        token = _current_session.set(s)
        try:
            proxy["k"] = 1
            assert s["k"] == 1
        finally:
            _current_session.reset(token)

    def test_two_threads_hammering_pawprint_stay_isolated(self):
        """Each thread's ContextVar binding must not leak into the other (PEP 567 / thread copy)."""
        from pawcket import pawprint

        errors: list[BaseException] = []
        lock = threading.Lock()

        def worker(label: str) -> None:
            token = None
            try:
                s = Session(_session_cookie_payload({"owner": label}))
                token = _current_session.set(s)
                for _ in range(2000):
                    pawprint["hot"] = label
                    pawprint["n"] = len(label)
                    assert pawprint["owner"] == label, "proxy read saw wrong session"
                    assert pawprint["hot"] == label, "stale hot key"
                    assert s["hot"] == label, "backing dict out of sync with proxy"
                    assert s["owner"] == label
            except BaseException as exc:
                with lock:
                    errors.append(exc)
            finally:
                if token is not None:
                    _current_session.reset(token)

        a = threading.Thread(target=worker, args=("thread-a",), name="session-test-a")
        b = threading.Thread(target=worker, args=("thread-bbbbb",), name="session-test-b")
        a.start()
        b.start()
        a.join()
        b.join()
        assert not errors, errors

    def test_threads_synchronized_barrier_still_isolated(self):
        """Both threads enter the same phase together; writes must not cross contexts."""
        from pawcket import pawprint

        barrier = threading.Barrier(2)
        errors: list[BaseException] = []

        def worker(label: str) -> None:
            token = None
            try:
                s = Session()
                token = _current_session.set(s)
                barrier.wait()
                pawprint["phase"] = label
                pawprint["only_here"] = f"data-{label}"
                barrier.wait()
                assert pawprint["phase"] == label
                assert pawprint["only_here"] == f"data-{label}"
                assert dict(s)["phase"] == label
                assert dict(s)["only_here"] == f"data-{label}"
            except BaseException as exc:
                errors.append(exc)
            finally:
                if token is not None:
                    _current_session.reset(token)

        threads = [
            threading.Thread(target=worker, args=("left",)),
            threading.Thread(target=worker, args=("right",)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors, errors

    def test_two_asyncio_tasks_interleaved_stay_isolated(self):
        """Tasks must each keep their own _current_session across await boundaries."""
        from pawcket import pawprint

        errors: list[BaseException] = []

        async def task(label: str) -> None:
            token = None
            try:
                s = Session(_session_cookie_payload({"task": label}))
                token = _current_session.set(s)
                for i in range(300):
                    pawprint["i"] = i
                    pawprint["who"] = label
                    await asyncio.sleep(0)
                    assert pawprint["task"] == label
                    assert pawprint["who"] == label
                    assert pawprint["i"] == i
                    assert s["who"] == label
            except BaseException as exc:
                errors.append(exc)
            finally:
                if token is not None:
                    _current_session.reset(token)

        async def runner() -> None:
            await asyncio.gather(task("alpha"), task("beta"))

        asyncio.run(runner())
        assert not errors, errors


class TestRouteToThreadSessionIntegration:
    @pytest.fixture
    def app(self):
        from pawcket import yarn

        return yarn(devmode=False)

    def test_existing_session_cookie_restores_state_and_modified_after_write(
        self, app
    ):
        from pawcket import pawprint

        cookie = _session_cookie_payload({"tier": "free"})

        @app.thread("/mutate")
        def _mutate():
            pawprint["tier"] = "pro"
            return "upgraded"

        req = _make_request(
            path="/mutate",
            cookies={"auth": "existing-auth", "pawcket_session": cookie},
        )
        resp = app.route_to_thread(req)
        assert resp.status_code == 200
        assert resp.body == "upgraded"
        assert resp.headers["X-Pawcket-Session-Accessed"] == "true"
        assert resp.headers["X-Pawcket-Session-Modified"] == "true"
        assert "X-Pawcket-Session-Data" in resp.headers
        restored = Session(resp.headers["X-Pawcket-Session-Data"])
        assert restored["tier"] == "pro"

    def test_read_only_session_access_sets_header_without_set_cookie_payload(
        self, app
    ):
        from pawcket import pawprint

        cookie = _session_cookie_payload({"id": 9})

        @app.thread("/peek")
        def _peek():
            assert pawprint.get("id") == 9
            return "ok"

        req = _make_request(
            path="/peek",
            cookies={"auth": "a", "pawcket_session": cookie},
        )
        resp = app.route_to_thread(req)
        assert resp.status_code == 200
        assert resp.headers["X-Pawcket-Session-Accessed"] == "true"
        assert resp.headers["X-Pawcket-Session-Modified"] == "false"
        assert "X-Pawcket-Session-Data" not in resp.headers

    def test_no_session_touch_leaves_accessed_modified_false(self, app):
        @app.thread("/noop")
        def _noop():
            return "static"

        req = _make_request(
            path="/noop",
            cookies={"auth": "z", "pawcket_session": _session_cookie_payload({})},
        )
        resp = app.route_to_thread(req)
        assert resp.headers["X-Pawcket-Session-Accessed"] == "false"
        assert resp.headers["X-Pawcket-Session-Modified"] == "false"

    def test_missing_auth_cookie_uses_mocked_random_string(self, app):
        from pawcket import pawprint

        @app.thread("/set")
        def _set():
            pawprint["x"] = 1
            return "done"

        with patch("pawcket.random_string", return_value="fixed-auth-token"):
            req = _make_request(path="/set", cookies={})
            resp = app.route_to_thread(req)

        assert resp.status_code == 200
        set_cookie = resp.headers.get("Set-Cookie")
        assert set_cookie is not None
        flat = set_cookie if isinstance(set_cookie, str) else "\n".join(set_cookie)
        assert "auth=fixed-auth-token" in flat.replace(" ", "")

    def test_corrupt_session_cookie_still_allows_handler_to_set_values(self, app):
        from pawcket import pawprint

        @app.thread("/recover")
        def _recover():
            pawprint["clean"] = True
            return "ok"

        req = _make_request(
            path="/recover",
            cookies={"auth": "x", "pawcket_session": "not-valid-json%%%"},
        )
        resp = app.route_to_thread(req)
        assert resp.status_code == 200
        assert resp.headers["X-Pawcket-Session-Modified"] == "true"
        data_hdr = resp.headers.get("X-Pawcket-Session-Data")
        assert data_hdr
        assert Session(data_hdr)["clean"] is True
