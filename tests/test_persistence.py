"""Regression tests for local file persistence."""
from __future__ import annotations

from persistence import LocalPersistence


class TestLocalPersistence:
    """Line-based store: easy to break on update vs append or ':' in values."""

    def test_save_and_retrieve_round_trip(self, tmp_path):
        path = tmp_path / "kv.txt"
        p = LocalPersistence(str(path))
        p.save_data("user", "ada")
        assert p.retrieve_data("user") == "ada"
        assert p.persistence_type == "local"

    def test_second_save_updates_same_key_without_duplicate_lines(self, tmp_path):
        path = tmp_path / "kv.txt"
        p = LocalPersistence(str(path))
        p.save_data("k", "v1")
        p.save_data("k", "v2")
        lines = [ln for ln in path.read_text().splitlines() if ln.strip()]
        assert sum(1 for ln in lines if ln.startswith("k:")) == 1
        assert p.retrieve_data("k") == "v2"

    def test_values_with_colon_round_trip(self, tmp_path):
        path = tmp_path / "kv.txt"
        p = LocalPersistence(str(path))
        value = "https://example.com:8443/path?q=a:b"
        p.save_data("url", value)
        assert p.retrieve_data("url") == value

    def test_distinct_keys_do_not_clobber(self, tmp_path):
        path = tmp_path / "kv.txt"
        p = LocalPersistence(str(path))
        p.save_data("a", "1")
        p.save_data("b", "2")
        assert p.retrieve_data("a") == "1"
        assert p.retrieve_data("b") == "2"

    def test_missing_key_returns_none(self, tmp_path):
        path = tmp_path / "kv.txt"
        path.write_text("only: other\n")
        p = LocalPersistence(str(path))
        assert p.retrieve_data("missing") is None
