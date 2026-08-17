"""aiwatch.collector のユニットテスト。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiwatch import collector  # noqa: E402

SAMPLE_HTML = """
<article class="Box-row"><h2><a href="/a/b">a/b</a></h2><p>desc here</p>
<span>100 stars today</span></article>
<article class="Box-row"><h2><a href="/c/d">c/d</a></h2>
<span>1,234 stars today</span></article>
"""


def test_parse_trending_extracts_fields():
    entries = collector.parse_trending_html(SAMPLE_HTML)
    assert len(entries) == 2
    assert entries[0]["name"] == "a/b"
    assert entries[0]["url"] == "https://github.com/a/b"
    assert entries[0]["description"] == "desc here"
    assert entries[0]["stars_today"] == 100
    assert entries[1]["stars_today"] == 1234  # カンマ除去


def test_parse_trending_limit():
    # 2件あり limit=1 なら1件
    entries = collector.parse_trending_html(SAMPLE_HTML, limit=1)
    assert len(entries) == 1


def test_parse_trending_empty_html():
    assert collector.parse_trending_html("<html></html>") == []


def test_enrich_stars_gh_failure_returns_na(monkeypatch):
    """gh失敗時 stars_total=-1・growth_rate=0.0。"""
    monkeypatch.setattr(collector, "_gh_stargazers", lambda name, timeout=15: None)
    entry = {"name": "a/b", "stars_today": 100}
    result = collector.enrich_stars(entry)
    assert result["stars_total"] == -1
    assert result["growth_rate"] == 0.0


def test_enrich_stars_computes_growth(monkeypatch):
    monkeypatch.setattr(collector, "_gh_stargazers", lambda name, timeout=15: 1000)
    entry = {"name": "a/b", "stars_today": 100}
    result = collector.enrich_stars(entry)
    assert result["stars_total"] == 1000
    assert result["growth_rate"] == 0.1


def test_gh_auth_ok_handles_exception(monkeypatch):
    """subproc例外時 False。"""
    monkeypatch.setattr(
        "subprocess.run", lambda *a, **k: (_ for _ in ()).throw(Exception("x"))
    )
    assert collector.gh_auth_ok() is False


def test_gh_auth_ok_probes_rate_limit(monkeypatch):
    """プローブ式: gh api /rate_limit の成否で判定(gh auth status不使用)。"""
    calls = []

    class FakeRun:
        def __init__(self, rc):
            self.returncode = rc

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return FakeRun(0)

    monkeypatch.setattr("subprocess.run", fake_run)
    assert collector.gh_auth_ok() is True
    assert calls[0][:3] == ["gh", "api", "/rate_limit"]


def test_validate_url_rejects_ssrf():
    """SSRF対策: 不正スキーマ/ホストを拒否。"""
    import pytest

    with pytest.raises(ValueError):
        collector.fetch_trending_html(url="http://github.com/trending")  # http不許可
    with pytest.raises(ValueError):
        collector.fetch_trending_html(url="https://evil.example.com/trending")  # 外部ホスト
    with pytest.raises(ValueError):
        collector.fetch_trending_html(url="https://169.254.169.254/latest")  # メタデータIP
