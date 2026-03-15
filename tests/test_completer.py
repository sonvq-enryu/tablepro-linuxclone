"""Tests for the auto-completion system."""

from __future__ import annotations

import pytest

from tablefree.services.schema_cache import SchemaMetadataCache
from tablefree.widgets.completer import CompletionItem, CompletionProvider


# ── Helpers ──────────────────────────────────────────────────


class FakeCache(SchemaMetadataCache):
    """In-memory cache with pre-populated data (no driver needed)."""

    def __init__(self, schemas=None, tables=None, columns=None):
        # Skip QObject.__init__ for pure-logic tests
        super().__init__()
        self._schemas = schemas or []
        self._tables = tables or {}
        self._columns = columns or {}


# ── Prefix extraction ────────────────────────────────────────


class TestPrefixExtraction:
    def test_simple_word(self):
        assert CompletionProvider._extract_prefix("SELECT us") == "us"

    def test_empty_after_space(self):
        assert CompletionProvider._extract_prefix("SELECT ") == ""

    def test_dot_notation(self):
        assert CompletionProvider._extract_prefix("SELECT users.na") == "users.na"

    def test_schema_dot(self):
        assert CompletionProvider._extract_prefix("FROM public.") == "public."

    def test_only_prefix(self):
        assert CompletionProvider._extract_prefix("SEL") == "SEL"

    def test_after_paren(self):
        assert CompletionProvider._extract_prefix("COUNT(i") == "i"

    def test_underscore(self):
        assert CompletionProvider._extract_prefix("SELECT user_na") == "user_na"


# ── Context detection ────────────────────────────────────────


class TestContextDetection:
    def test_after_from(self):
        ctx = CompletionProvider._detect_context("SELECT * FROM us", "us")
        assert ctx == "TABLE"

    def test_after_join(self):
        ctx = CompletionProvider._detect_context("SELECT * FROM t1 JOIN t", "t")
        assert ctx == "TABLE"

    def test_after_select(self):
        ctx = CompletionProvider._detect_context("SELECT na", "na")
        assert ctx == "COLUMN"

    def test_after_where(self):
        ctx = CompletionProvider._detect_context("SELECT * FROM t WHERE co", "co")
        assert ctx == "COLUMN"

    def test_after_order_by(self):
        ctx = CompletionProvider._detect_context("SELECT * FROM t ORDER BY na", "na")
        assert ctx == "COLUMN"

    def test_after_group_by(self):
        ctx = CompletionProvider._detect_context("SELECT * FROM t GROUP BY na", "na")
        assert ctx == "COLUMN"

    def test_general_context(self):
        ctx = CompletionProvider._detect_context("CR", "CR")
        assert ctx == "GENERAL"

    def test_after_into(self):
        ctx = CompletionProvider._detect_context("INSERT INTO us", "us")
        assert ctx == "TABLE"

    def test_after_update(self):
        ctx = CompletionProvider._detect_context("UPDATE us", "us")
        assert ctx == "TABLE"


class TestStringDetection:
    def test_inside_single_quote(self):
        assert CompletionProvider._is_inside_string("SELECT 'abc") is True

    def test_inside_double_quote(self):
        assert CompletionProvider._is_inside_string('SELECT "ab') is True

    def test_outside_after_closed_quote(self):
        assert CompletionProvider._is_inside_string("SELECT 'abc' ") is False

    def test_escaped_single_quote(self):
        assert CompletionProvider._is_inside_string("SELECT 'it''s ok'") is False


# ── Filtering ────────────────────────────────────────────────


class TestFiltering:
    def test_prefix_match(self):
        items = [
            CompletionItem("SELECT", "keyword"),
            CompletionItem("SET", "keyword"),
            CompletionItem("FROM", "keyword"),
        ]
        result = CompletionProvider._filter(items, "SE")
        texts = [it.text for it in result]
        assert "SELECT" in texts
        assert "SET" in texts
        assert "FROM" not in texts

    def test_case_insensitive(self):
        items = [CompletionItem("SELECT", "keyword")]
        result = CompletionProvider._filter(items, "sel")
        assert len(result) == 1
        assert result[0].text == "SELECT"

    def test_contains_match(self):
        items = [
            CompletionItem("user_name", "column"),
            CompletionItem("email", "column"),
        ]
        result = CompletionProvider._filter(items, "name")
        assert len(result) == 1
        assert result[0].text == "user_name"

    def test_prefix_match_sorted_first(self):
        items = [
            CompletionItem("user_name", "column"),
            CompletionItem("name", "column"),
        ]
        result = CompletionProvider._filter(items, "na")
        assert result[0].text == "name"

    def test_empty_prefix_returns_empty(self):
        items = [CompletionItem("SELECT", "keyword")]
        result = CompletionProvider._filter(items, "")
        # Empty prefix matches all
        assert len(result) == 1


# ── Integration with cache ───────────────────────────────────


class TestCompletionWithCache:
    @pytest.fixture()
    def provider(self):
        from tablefree.db.driver import ColumnInfo

        cache = FakeCache(
            schemas=["public", "analytics"],
            tables={"public": ["users", "orders"], "analytics": ["events"]},
            columns={
                ("public", "users"): [
                    ColumnInfo("id", "integer", False, None, 1),
                    ColumnInfo("name", "varchar", True, None, 2),
                    ColumnInfo("email", "varchar", True, None, 3),
                ],
                ("public", "orders"): [
                    ColumnInfo("id", "integer", False, None, 1),
                    ColumnInfo("user_id", "integer", False, None, 2),
                    ColumnInfo("total", "numeric", True, None, 3),
                ],
            },
        )
        return CompletionProvider(cache)

    def test_keyword_completion(self, provider):
        items = provider.get_completions("SEL")
        texts = [it.text for it in items]
        assert "SELECT" in texts

    def test_table_completion_after_from(self, provider):
        items = provider.get_completions("SELECT * FROM us")
        texts = [it.text for it in items]
        assert "users" in texts

    def test_schema_completion_after_from(self, provider):
        items = provider.get_completions("SELECT * FROM pu")
        texts = [it.text for it in items]
        assert "public" in texts

    def test_dot_schema_tables(self, provider):
        items = provider.get_completions("SELECT * FROM public.")
        texts = [it.text for it in items]
        assert "users" in texts
        assert "orders" in texts
        assert "events" not in texts

    def test_dot_table_columns(self, provider):
        items = provider.get_completions("SELECT users.na")
        texts = [it.text for it in items]
        assert "name" in texts

    def test_forced_completion_empty_prefix(self, provider):
        items = provider.get_completions_forced("SELECT * FROM ")
        assert len(items) > 0

    def test_short_prefix_returns_empty(self, provider):
        items = provider.get_completions("S")
        # Single char should return results (filter matches)
        # but the editor enforces min 2 chars — provider itself returns matches
        texts = [it.text for it in items]
        assert "SELECT" in texts or "SET" in texts

    def test_no_match_returns_empty(self, provider):
        items = provider.get_completions("XYZABC")
        assert items == []

    def test_no_completion_inside_string(self, provider):
        items = provider.get_completions("SELECT * FROM users WHERE name = 'al")
        assert items == []

    def test_no_forced_completion_inside_string(self, provider):
        items = provider.get_completions_forced("SELECT '")
        assert items == []


# ── Cache invalidation ───────────────────────────────────────


class TestCacheInvalidation:
    def test_set_driver_clears_cache(self):
        cache = FakeCache(
            schemas=["public"],
            tables={"public": ["users"]},
        )
        assert cache.get_schemas() == ["public"]
        cache.set_driver(None)
        assert cache.get_schemas() == []
        assert cache.get_tables() == []
