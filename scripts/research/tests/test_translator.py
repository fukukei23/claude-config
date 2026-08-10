"""aiwatch.translator のユニットテスト。"""
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiwatch.models import RepoStats  # noqa: E402
from aiwatch.translator import (  # noqa: E402
    build_prompt,
    parse_translation_json,
    translate_descriptions,
)


class _FakeResp:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._data


def _repo(name="a/b", desc="A tool"):
    return RepoStats(name, f"https://github.com/{name}", desc, 100, 1000, 0.1, "初見")


def test_parse_translation_json_pure():
    assert parse_translation_json('{"a/b": "ほげ"}') == {"a/b": "ほげ"}


def test_parse_translation_json_with_prose():
    text = '結果です。\n```json\n{"a/b": "ほげ"}\n```\nよろしく'
    assert parse_translation_json(text) == {"a/b": "ほげ"}


def test_parse_translation_json_invalid():
    assert parse_translation_json("not json at all") == {}
    assert parse_translation_json("{}") == {}


def test_build_prompt_contains_all_items():
    p = build_prompt([("a/b", "A tool"), ("c/d", "Another")])
    assert "a/b" in p and "c/d" in p
    assert "JSON" in p


def test_translate_descriptions_success():
    def fake_post(url, headers=None, json=None, timeout=None):
        return _FakeResp({
            "content": [{"type": "text", "text": '{"a/b": "ツールA"}'}],
            "usage": {"input_tokens": 50, "output_tokens": 10},
        })

    mapping, stats = translate_descriptions([_repo()], api_key="k", requester=fake_post)
    assert mapping == {"a/b": "ツールA"}
    assert stats["ok"] is True
    assert stats["tokens_in"] == 50
    assert stats["tokens_out"] == 10


def test_translate_descriptions_http_error_fallback():
    def fake_post(url, headers=None, json=None, timeout=None):
        return _FakeResp({}, status=500)

    mapping, stats = translate_descriptions([_repo()], api_key="k", requester=fake_post)
    assert mapping == {}
    assert stats["ok"] is False


def test_translate_descriptions_no_api_key(monkeypatch):
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    mapping, stats = translate_descriptions([_repo()], api_key="")
    assert mapping == {}
    assert stats["ok"] is False


def test_translate_descriptions_empty_repos():
    mapping, stats = translate_descriptions([], api_key="k")
    assert mapping == {}
    assert stats["ok"] is False


def test_translate_descriptions_invalid_json_fallback():
    def fake_post(url, headers=None, json=None, timeout=None):
        return _FakeResp({
            "content": [{"type": "text", "text": "JSONじゃない"}],
            "usage": {"input_tokens": 5, "output_tokens": 5},
        })

    mapping, stats = translate_descriptions([_repo()], api_key="k", requester=fake_post)
    assert mapping == {}
    assert stats["ok"] is False
