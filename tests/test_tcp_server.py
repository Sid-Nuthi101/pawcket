"""Regression tests for TCP connection handling (decode → route → send)."""
from __future__ import annotations

import socket
import threading

import pytest


@pytest.mark.skipif(not hasattr(socket, "socketpair"), reason="no socketpair")
class TestTcpHandleConnection:
    """Ensures decode → HTTPRequest → yarn.route_to_thread → UTF-8 sendall stays wired."""

    def test_socketpair_full_request_response(self):
        from pawcket import yarn
        from tcp_server import handle_connection

        app = yarn(devmode=False)

        @app.thread("/ping")
        def _ping():
            return "pong"

        left, right = socket.socketpair()

        def serve():
            try:
                handle_connection(right, app)
            finally:
                right.close()

        th = threading.Thread(target=serve, daemon=True)
        th.start()

        try:
            left.sendall(
                b"GET /ping HTTP/1.1\r\nHost: localhost\r\nCookie: auth=t\r\n\r\n"
            )
            data = left.recv(65536)
        finally:
            left.close()

        th.join(timeout=5)
        assert not th.is_alive(), "handle_connection did not finish"
        assert b"HTTP/1.1 200" in data
        assert b"pong" in data
        assert b"Content-Length:" in data
