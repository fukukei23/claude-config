#!/usr/bin/env python3
"""
wikilink → 標準Markdown 変換スクリプト（one-shot・実行後自削除）
全 [[ ]] を [text](src相対path) に変換。## 関連セクションの重複をuniq化。
"""
import argparse
import os
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


SCAN_DIRS = ["00_SYSTEM", "01_DECISIONS", "20_PUBLISHING", "30_RESEARCH",
             "40_CAREER", "50_PROJECTS", "70_PROMPTS", "99_ARCHIVE"]
SKIP_SUFFIXES = (".backup",)
WIKILINK_RE = re.compile(r"(!?)\[\[([^\]]+)\]\]")


def build_stem_index(vault: Path) -> dict:
    """vault内全ファイルの {stem: [path,...]} を構築（.md/.png/.jpg等すべて）"""
    idx = defaultdict(list)
    for d in SCAN_DIRS:
        sp = vault / d
        if not sp.exists():
            continue
        for p in sp.rglob("*"):
            if p.is_file() and not p.name.startswith("."):
                idx[p.stem].append(p)
    return idx


def resolve_stem(stem: str, idx: dict):
    """stem解決。戻り値: (path, status)。status: ok/conflict/notfound"""
    paths = idx.get(stem, [])
    if len(paths) == 1:
        return (paths[0], "ok")
    if len(paths) > 1:
        return (paths, "conflict")
    return (None, "notfound")


def to_relative_path(target: Path, src: Path) -> str:
    """srcファイル位置からのtargetへの相対path"""
    return os.path.relpath(target, src.parent)


def convert_wikilink(match_text: str, src: Path, vault: Path, idx: dict):
    """
    単一wikilinkを変換。戻り値: (result_text, status)
    status: ok/conflict/notfound/skip
    """
    m = WIKILINK_RE.match(match_text)
    if not m:
        return (match_text, "skip")
    embed, inner = m.group(1), m.group(2)

    # エイリアス [[stem|表示名]] or [[path|表示名]]
    display = None
    if "|" in inner:
        inner, display = inner.split("|", 1)
        inner = inner.strip()
        display = display.strip()

    # 外部URL・見出し → スキップ
    if inner.startswith(("http://", "https://", "#")):
        return (match_text, "skip")

    # フルパス形式 [[01_DECISIONS/x/a.md]]
    if "/" in inner or inner.endswith(".md") or inner.endswith((".png", ".jpg", ".jpeg", ".gif", ".pdf")):
        target_name = inner.split("/")[-1]
        target = vault / inner if not inner.startswith("/") else vault / inner.lstrip("/")
        if not target.exists():
            # 完全一致で見つからない → stemでフォールバック
            stem = Path(inner.rstrip("/").replace(".md", "")).stem
            t, st = resolve_stem(stem, idx)
            if st == "ok":
                target = t
            else:
                return (match_text, "notfound")
        label = display if display else Path(target_name).stem
        rel = to_relative_path(target, src)
        return (f"{embed}[{label}]({rel})", "ok")

    # stem形式 [[a]]
    stem = inner
    path, status = resolve_stem(stem, idx)
    if status != "ok":
        return (match_text, status)
    label = display if display else stem
    rel = to_relative_path(path, src)
    return (f"{embed}[{label}]({rel})", "ok")


def process_file(src: Path, vault: Path, idx: dict, warnings: list):
    """1ファイルのwikilinkを全変換。## 関連セクションの重複をuniq化。
    戻り値: (変換数, スキップ数)"""
    try:
        text = src.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = src.read_text(encoding="utf-8", errors="replace")
    converted = 0
    skipped = 0

    def replacer(m):
        nonlocal converted, skipped
        result, status = convert_wikilink(m.group(0), src, vault, idx)
        if status == "ok":
            converted += 1
            return result
        elif status in ("conflict", "notfound"):
            skipped += 1
            warnings.append(f"[{status}] {src.relative_to(vault)}: {m.group(0)}")
            return m.group(0)  # 元のまま保持
        else:  # skip（外部URL等）
            return m.group(0)

    text = WIKILINK_RE.sub(replacer, text)

    # ## 関連セクションの重複uniq化
    text = dedupe_related_section(text)

    src.write_text(text, encoding="utf-8")
    return (converted, skipped)


def dedupe_related_section(text: str) -> str:
    """## 関連セクション内の重複行をuniq化。空になったらセクション削除。"""
    lines = text.split("\n")
    out = []
    in_related = False
    related_lines = []
    related_start_idx = -1

    for i, line in enumerate(lines):
        if line.strip() == "## 関連":
            in_related = True
            related_start_idx = len(out)
            out.append(line)
            continue
        if in_related:
            # 次のセクション見出し or 空行連続で終端
            if line.startswith("## ") or (line.strip() == "" and related_lines):
                # セクション終了 → uniq化して書き込み
                seen = []
                for rl in related_lines:
                    norm = rl.strip().lower()
                    # path正規化: 拡張子・末尾スラッシュ揺れを吸収
                    norm = re.sub(r"\]\([^)]+\)", "](NORM)", norm)  # path部分を正規化
                    if norm not in seen:
                        seen.append(norm)
                        out.append(rl)
                related_lines = []
                in_related = False
                out.append(line)
            elif line.strip().startswith("- "):
                related_lines.append(line)
            else:
                related_lines.append(line)
        else:
            out.append(line)

    # ファイル末尾で関連セクションが続いている場合の処理
    if in_related and related_lines:
        seen = []
        deduped = []
        for rl in related_lines:
            norm = re.sub(r"\]\([^)]+\)", "](NORM)", rl.strip().lower())
            if norm not in seen:
                seen.append(norm)
                deduped.append(rl)
        # 末尾の重複を差し替え
        out = out[:related_start_idx + 1] + deduped

    result = "\n".join(out)
    # 空の ## 関連（直後にセクションなし）を削除
    result = re.sub(r"## 関連\s*\n\s*$", "", result)
    result = re.sub(r"## 関連\s*\n(\s*## )", r"\1", result)
    return result


def backup_vault(vault: Path) -> Path:
    """vault内の全.mdをバックアップディレクトリにコピー"""
    ts = datetime.now().strftime("%Y%m%d")
    backup_dir = vault / f".backup-wikilinks-{ts}"
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    for d in SCAN_DIRS:
        sp = vault / d
        if not sp.exists():
            continue
        for p in sp.rglob("*.md"):
            if any(str(p).endswith(s) for s in SKIP_SUFFIXES):
                continue
            rel = p.relative_to(vault)
            dst = backup_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
    return backup_dir


def main():
    parser = argparse.ArgumentParser(description="wikilink → 標準Markdown 変換（one-shot）")
    parser.add_argument("--ssot-dir", default=str(Path.home() / "projects" / "obsidian-ssot"))
    parser.add_argument("--dry-run", action="store_true", help="変換せず結果のみ表示")
    parser.add_argument("--dir", help="対象ディレクトリ限定（テスト用）")
    parser.add_argument("--no-backup", action="store_true", help="バックアップ省略")
    args = parser.parse_args()

    vault = Path(args.ssot_dir)
    if not vault.exists():
        print(f"❌ vault不在: {vault}", file=sys.stderr)
        return 1

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 変換開始 vault={vault}")

    # バックアップ
    if not args.dry_run and not args.no_backup:
        bd = backup_vault(vault)
        print(f"✅ バックアップ: {bd}")

    idx = build_stem_index(vault)
    print(f"📁 stem index構築: {len(idx)}件")

    warnings = []
    total_converted = 0
    total_skipped = 0
    files_changed = 0

    # 対象ファイル収集
    targets = []
    dirs = [args.dir] if args.dir else SCAN_DIRS
    for d in dirs:
        sp = vault / d
        if not sp.exists():
            continue
        targets.extend(sp.rglob("*.md"))

    for src in targets:
        if any(str(src).endswith(s) for s in SKIP_SUFFIXES):
            continue
        if args.dry_run:
            try:
                text = src.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                # 部分的エンコーディング混入は errors=replace でフォールバック
                text = src.read_text(encoding="utf-8", errors="replace")
            matches = WIKILINK_RE.findall(text)
            if matches:
                print(f"  [DRY] {src.relative_to(vault)}: {len(matches)}件")
            continue
        try:
            before = src.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            warnings.append(f"[decode-error] {src.relative_to(vault)}: UTF-8 decode失敗・スキップ")
            continue
        c, s = process_file(src, vault, idx, warnings)
        after = src.read_text(encoding="utf-8")
        if before != after:
            files_changed += 1
        total_converted += c
        total_skipped += s

    # 警告ログ
    if warnings:
        log_path = vault / "convert-warnings.log"
        log_path.write_text("\n".join(warnings) + "\n", encoding="utf-8")
        print(f"⚠️ 警告: {len(warnings)}件 → {log_path}")

    print(f"\n=== サマリー ===")
    print(f"変更ファイル: {files_changed}")
    print(f"変換リンク: {total_converted}")
    print(f"スキップ: {total_skipped}")
    if args.dry_run:
        print("（dry-run・ファイル未変更）")
    return 0


if __name__ == "__main__":
    sys.exit(main())