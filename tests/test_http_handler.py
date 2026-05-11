"""Regression tests for HTTP request parsing and response serialization."""
from __future__ import annotations

from http_handler import HTTPCookie, HTTPRequest, HTTPResponse, make_response


def _minimal_get(path: str, *, cookie: str | None = None) -> str:
    lines = [f"GET {path} HTTP/1.1", "Host: 127.0.0.1"]
    if cookie is not None:
        lines.append(f"Cookie: {cookie}")
    return "\r\n".join(lines) + "\r\n\r\n"


class TestHTTPRequestParsing:
    """Guards wire-format parsing used by tcp_server.handle_connection."""

    def test_parses_method_path_version_and_lowercase_headers(self):
        raw = _minimal_get("/mutate", cookie="auth=abc; pawcket_session=xyz")
        req = HTTPRequest(raw)
        assert req.method == "GET"
        assert req.path == "/mutate"
        assert req.http_version == "HTTP/1.1"
        assert req.headers["host"] == "127.0.0.1"
        assert req.cookies["auth"] == "abc"
        assert req.cookies["pawcket_session"] == "xyz"

    def test_none_request_data_is_safe_noop(self):
        req = HTTPRequest(None)
        assert req.method == ""
        assert req.path == ""
        assert req.cookies == {}

    def test_cookie_values_preserve_equals_in_value(self):
        raw = _minimal_get("/", cookie="token=abc=def")
        req = HTTPRequest(raw)
        assert req.cookies["token"] == "abc=def"


class TestHTTPResponseAndMakeResponse:
    """Catches regressions in framing (length, cookies) that break real clients."""

    def test_content_length_counts_utf8_bytes_not_codepoints(self):
        r = HTTPResponse()
        r.body = "η"
        serialized = str(r)
        assert "Content-Length: 2\r\n" in serialized

    def test_set_cookie_accumulates_multiple_cookies_as_list(self):
        r = HTTPResponse()
        r.set_cookie(HTTPCookie("a", "1"))
        r.set_cookie(HTTPCookie("b", "2"))
        assert isinstance(r.headers["Set-Cookie"], list)
        assert len(r.headers["Set-Cookie"]) == 2
        out = str(r)
        assert out.count("Set-Cookie:") == 2

    def test_make_response_merges_extra_headers(self):
        r = make_response("x", headers={"X-Custom": "yes"})
        assert r.headers["X-Custom"] == "yes"
        assert r.body == "x"
