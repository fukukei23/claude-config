#!/usr/bin/env python3
import argparse, re, sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

SCORE_THRESHOLD = 60
MAX_LINKS_PER_FILE = 3
MAX_LINKS_TOTAL = 30
SCAN_DIRS = ["00_SYSTEM","01_DECISIONS","20_PUBLISHING","30_RESEARCH","40_CAREER","50_PROJECTS"]
SKIP_PATTERNS = [re.compile(p) for p in [r"^_INDEX\.md$",r"^README\.md$",r"^CLAUDE\.md$",r"knowledge-graph"]]
STOPWORDS = {"the","and","for","with","that","this","from","are","was","not","has","its","our","can","all","one","but","you","have","been","will","they","when","what","how","use"}


def parse_frontmatter(text):
    fm = {}
    if not text.startswith("---"):
        return fm
    end = text.find("\n---", 3)
    if end == -1:
        return fm
    for line in text[3:end].splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k, v = k.strip(), v.strip()
        fm[k] = [t.strip().strip("\"'") for t in v[1:-1].split(",") if t.strip()] if v.startswith("[") else v
    return fm


def _parse_link_policy_frontmatter(text: str) -> dict:
    """方針ファイル用の YAML 形式 frontmatter パーサ（parse_frontmatter の補助）。

    parse_frontmatter は INI 風（key: "v1", "v2"）にしか対応しないため、
    YAML のリスト形式（key:\\n  - "v1"\\n  - "v2"）を自前で解釈する。
    """
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    body = text[3:end]
    fm: dict = {}
    current_key = None
    for line in body.splitlines():
        # リスト要素行: "  - \"value\""
        stripped = line.strip()
        if stripped.startswith("- ") and current_key is not None:
            v = stripped[2:].strip().strip('"').strip("'")
            fm.setdefault(current_key, []).append(v)
            continue
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            k = k.strip()
            v = v.strip()
            current_key = k
            if v == "":
                fm[k] = []
            elif v.startswith("[") and v.endswith("]"):
                # INI 風リスト
                fm[k] = [t.strip().strip("\"'") for t in v[1:-1].split(",") if t.strip()]
            else:
                fm[k] = v.strip('"').strip("'")
                # 次の行がリストの可能性に備え current_key は維持
        else:
            current_key = None
    return fm


def parse_link_policy(ssot_dir: Path) -> dict:
    """00_SYSTEM/リンク運用方針.md の frontmatter をパース。

    Returns:
        {
            "allowed_dirs": [Path, ...] | None,   # 許可層の絶対パス一覧
            "forbidden_dirs": [Path, ...],        # 禁止層の絶対パス一覧
        }
    """
    policy_path = ssot_dir / "00_SYSTEM" / "リンク運用方針.md"
    if not policy_path.exists():
        # 方針ファイルなし → 既存挙動（全ファイル許可）
        return {"allowed_dirs": None, "forbidden_dirs": []}
    try:
        text = policy_path.read_text(encoding="utf-8")
        fm = _parse_link_policy_frontmatter(text)
        allowed = fm.get("allowed_dirs", [])
        excluded = fm.get("excluded_subdirs", [])
        forbidden = fm.get("forbidden_dirs", [])

        allowed_paths = [ssot_dir / d for d in allowed]
        # excluded_subdirs は allowed_paths 全体から除外
        excluded_set = {str(ssot_dir / e) for e in excluded}
        allowed_paths = [p for p in allowed_paths if str(p) not in excluded_set]

        forbidden_paths = [ssot_dir / d for d in forbidden]
        return {"allowed_dirs": allowed_paths, "forbidden_dirs": forbidden_paths}
    except Exception as e:
        print(f"[WARN] 方針ファイルパース失敗: {e} → 全ファイル許可にフォールバック")
        return {"allowed_dirs": None, "forbidden_dirs": []}


def extract_keywords(text):
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4:]
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"\[\[.*?\]\]|\[.*?\]\(.*?\)|[#>|*`_~]", " ", text)
    ja = set(re.findall(r"[぀-鿿]{2,}", text))
    en = {w.lower() for w in re.findall(r"[a-zA-Z]{3,}", text) if w.lower() not in STOPWORDS}
    return ja | en


def file_date(path):
    m = re.match(r"(\d{4}-\d{2}-\d{2})", path.stem)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d")
        except ValueError:
            pass
    return None


def existing_links(text):
    return set(re.findall(r"\[\[([^\]]+)\]\]", text))


def score_pair(a, b):
    s = 0
    ap, bp = a["fm"].get("project", ""), b["fm"].get("project", "")
    if ap and bp and ap == bp:
        s += 40
    ct = len(set(a["fm"].get("tags", [])) & set(b["fm"].get("tags", [])))
    s += 30 if ct >= 3 else 10 if ct >= 1 else 0
    ck = len(a["keywords"] & b["keywords"])
    s += 20 if ck >= 10 else 15 if ck >= 5 else 0
    da, db = a["date"], b["date"]
    if da and db and abs((da - db).days) <= 7:
        s += 10
    if b["path"].stem in a["links"] or a["path"].stem in b["links"]:
        s -= 20
    return s


def add_link(path, target):
    text = path.read_text(encoding="utf-8")
    link = f"[[{target}]]"
    if link in text:
        return False
    if "## 関連" in text:
        path.write_text(text.rstrip() + f"\n- {link}\n", encoding="utf-8")
    else:
        path.write_text(text.rstrip() + f"\n\n## 関連\n- {link}\n", encoding="utf-8")
    return True


def load_files(ssot_dir):
    files = []
    for d in SCAN_DIRS:
        sp = ssot_dir / d
        if not sp.exists():
            continue
        for p in sp.rglob("*.md"):
            if any(pat.search(p.name) for pat in SKIP_PATTERNS):
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except Exception:
                continue
            fm = parse_frontmatter(text)
            files.append({
                "path": p,
                "fm": fm,
                "keywords": extract_keywords(text),
                "links": existing_links(text),
                "date": file_date(p),
            })
    return files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ssot-dir", default=str(Path.home() / "projects/obsidian-ssot"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    ssot_dir = Path(args.ssot_dir)
    print(f"SSOT: {ssot_dir}")
    files = load_files(ssot_dir)
    print(f"対象ファイル数: {len(files)}")

    candidates = []
    n = len(files)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = files[i], files[j]
            same_dir = a["path"].parent == b["path"].parent
            same_proj = a["fm"].get("project") and a["fm"].get("project") == b["fm"].get("project")
            common_kw = len(a["keywords"] & b["keywords"]) >= 5
            if not (same_dir or same_proj or common_kw):
                continue
            s = score_pair(a, b)
            if s >= SCORE_THRESHOLD:
                candidates.append((s, i, j))

    candidates.sort(key=lambda x: -x[0])
    print(f"閾値({SCORE_THRESHOLD}点)以上のペア数: {len(candidates)}")

    added_per = defaultdict(int)
    total = 0
    results = []

    for score, i, j in candidates:
        if total >= MAX_LINKS_TOTAL:
            break
        a, b = files[i], files[j]
        as_, bs_ = a["path"].stem, b["path"].stem

        if added_per[i] < MAX_LINKS_PER_FILE and bs_ not in a["links"]:
            if args.dry_run:
                print(f"  [DRY] {a['path'].name} -> [[{bs_}]] ({score}pt)")
            elif add_link(a["path"], bs_):
                a["links"].add(bs_)
                added_per[i] += 1
                total += 1
                results.append(f"  {a['path'].relative_to(ssot_dir)} -> [[{bs_}]] ({score}pt)")

        if total >= MAX_LINKS_TOTAL:
            break

        if added_per[j] < MAX_LINKS_PER_FILE and as_ not in b["links"]:
            if args.dry_run:
                print(f"  [DRY] {b['path'].name} -> [[{as_}]] ({score}pt)")
            elif add_link(b["path"], as_):
                b["links"].add(as_)
                added_per[j] += 1
                total += 1
                results.append(f"  {b['path'].relative_to(ssot_dir)} -> [[{as_}]] ({score}pt)")

    for r in results:
        print(r)

    print(f"\n追加リンク数: {total}/{MAX_LINKS_TOTAL}")

    if not args.dry_run and total > 0:
        today = datetime.now().strftime("%Y-%m-%d")
        rp = ssot_dir / f"01_DECISIONS/claude-code/{today}_knowledge-lint-実行.md"
        body = "\n".join(results)
        rp.write_text(
            f"---\nproject: claude-code\ndate: {today}\ntags: [knowledge-lint, 自動実行, リンク付与]\n---\n\n"
            f"# Knowledge Lint 実行記録\n\n実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"対象ファイル数: {len(files)}\n追加リンク数: {total}\n\n{body}\n",
            encoding="utf-8",
        )
        print(f"記録: {rp.relative_to(ssot_dir)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
