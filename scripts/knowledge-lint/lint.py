#!/usr/bin/env python3
import argparse, os, re, sys
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
    """本文中の既存リンクから「リンク先のstem」のsetを返す（[[stem]]/[[path]]/[text](path) 全形式対応）"""
    links = set()
    for m in re.findall(r"\[\[([^\]]+)\]\]", text):
        links.add(Path(m.replace(".md", "")).stem)
    for m in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
        links.add(Path(m.replace(".md", "")).stem)
    return links


def read_policy(ssot_dir):
    """00_SYSTEM/リンク運用方針.md の frontmatter を読む（[[ ]] 許可層判定用）"""
    p = ssot_dir / "00_SYSTEM" / "リンク運用方針.md"
    if not p.exists():
        return {}
    return parse_frontmatter(p.read_text(encoding="utf-8"))


def link_format(target_path, src_path, ssot_dir, policy):
    """方針に従い [[stem]]（許可層）か [stem](相対path)（禁止層）かを出し分け"""
    try:
        rel = target_path.relative_to(ssot_dir)
    except ValueError:
        rel = None
    top = rel.parts[0] if rel and rel.parts else None
    allowed = policy.get("allowed_dirs", [])
    excluded = policy.get("excluded_subdirs", [])
    in_excluded = any(str(rel).startswith(e) for e in excluded) if rel else False
    if top in allowed and not in_excluded:
        return f"[[{target_path.stem}]]"
    rel_link = os.path.relpath(target_path, src_path.parent)
    return f"[{target_path.stem}]({rel_link})"


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


def add_link(path, target_path, ssot_dir, policy):
    text = path.read_text(encoding="utf-8")
    link = link_format(target_path, path, ssot_dir, policy)
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
    policy = read_policy(ssot_dir)
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
        la = link_format(b["path"], a["path"], ssot_dir, policy)
        lb = link_format(a["path"], b["path"], ssot_dir, policy)

        if added_per[i] < MAX_LINKS_PER_FILE and bs_ not in a["links"]:
            if args.dry_run:
                print(f"  [DRY] {a['path'].name} -> {la} ({score}pt)")
            elif add_link(a["path"], b["path"], ssot_dir, policy):
                a["links"].add(bs_)
                added_per[i] += 1
                total += 1
                results.append(f"  {a['path'].relative_to(ssot_dir)} -> {la} ({score}pt)")

        if total >= MAX_LINKS_TOTAL:
            break

        if added_per[j] < MAX_LINKS_PER_FILE and as_ not in b["links"]:
            if args.dry_run:
                print(f"  [DRY] {b['path'].name} -> {lb} ({score}pt)")
            elif add_link(b["path"], a["path"], ssot_dir, policy):
                b["links"].add(as_)
                added_per[j] += 1
                total += 1
                results.append(f"  {b['path'].relative_to(ssot_dir)} -> {lb} ({score}pt)")

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
