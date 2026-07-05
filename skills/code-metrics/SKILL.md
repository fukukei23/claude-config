---
name: code-metrics
description: >
  Gitリポジトリのコード行数・テストケース数を正確に計測しSSOTに記録。「本当にファイルを読んで計測した」ことを3層で証明（推測禁止）。
  「/code-metrics」「コード行数を計測して」「テストケース数を計測して」「ポートフォリオの数字を確認して」「実績数値を実測して」「自己PRの数字を確認して」等で発火。経歴書の数字確認や過去計測の更新にも。
---

# code-metrics スキル

ポートフォリオ・経歴書に記載するコード行数・テストケース数を、実ファイルから正確に計測してSSOTに記録する。
「なんとなく」「推測」での回答は禁止。必ず実測値を出すこと。

---

## 除外ルール（必ず適用）

以下のディレクトリは計測から除外する（過去の計測でこれらが混入して数字が狂った経験から）：

```python
EXCLUDE_DIRS = {
    # ミューテーションテスト生成物（NexusCoreで5.5万行が誤混入した）
    "mutants",
    # 外部評価フレームワーク（evalplus等が混入することがある）
    "evaluation",
    # 廃止コード
    "archive",
    # Python仮想環境
    ".venv", "venv", "env",
    # システム生成物
    "__pycache__", ".pytest_cache", ".mypy_cache", ".tox", "htmlcov",
    # JS生成物
    "node_modules", "dist", "build",
    # ドットディレクトリ全般（.git, .github, .cursor等）
    # → dirname.startswith(".") で一括除外
}
```

**計測対象拡張子**: `.py` `.ts` `.tsx` `.js` `.jsx`

**テスト判定**:
- ファイル名に `test_` `_test` `.test.` `.spec.` を含む
- `tests/` または `test/` ディレクトリ配下

---

## Phase 1: リポジトリ一覧の確認

`~/projects/` 配下の全gitリポジトリを列挙し、以下の**ガイド・設定系は自動除外**してアプリリポジトリのみに絞る：

```
除外パターン: obsidian-ssot, claude-code-guide, ssot-guide, *-guide,
              fukukei23*, zenn, interview-prep, claude-config, krokod-setup,
              stit-irg-template, aasdf-sample*, ai-augmented*, GAS
```

対象リポジトリ一覧をユーザーに提示して確認を得てから次フェーズへ。

---

## Phase 2: コード行数の計測

スキル同梱の `~/.claude/skills/code-metrics/scripts/measure_code.py` を実行する（内容は以下の通り。無い場合はこの内容で同パスに保存する）。

```python
#!/usr/bin/env python3
"""
コード行数計測スクリプト（code-metricsスキル用）
除外ディレクトリ・異常値検出・内訳出力つき
"""
import os, sys, random
from collections import defaultdict

BASE_DIR = "/home/yn4416/projects"

EXCLUDE_DIRS = {
    "mutants", "evaluation", "archive",
    ".venv", "venv", "env", ".env",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".tox", "htmlcov",
    "node_modules", "dist", "build", "site-packages",
    ".eggs", "__pypackages__",
}
APP_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx"}
TEST_KEYWORDS = {"test_", "_test", ".test.", ".spec."}

def is_excluded(dirname):
    return dirname in EXCLUDE_DIRS or dirname.startswith(".")

def is_test(path):
    parts = path.split(os.sep)
    if "tests" in parts or "test" in parts:
        return True
    return any(kw in os.path.basename(path) for kw in TEST_KEYWORDS)

def count_lines(f):
    try:
        return sum(1 for _ in open(f, encoding="utf-8", errors="ignore"))
    except:
        return 0

def measure_repo(repo_path):
    """1リポジトリを計測して結果を返す"""
    dir_stats = defaultdict(lambda: {"app": 0, "test": 0, "app_f": 0, "test_f": 0})
    all_app_files = []
    all_test_files = []

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if not is_excluded(d)]
        rel = root.replace(repo_path, "").lstrip("/")
        top = rel.split("/")[0] if rel else "(root)"

        for fname in files:
            ext = os.path.splitext(fname)[1]
            if ext not in APP_EXTS:
                continue
            fpath = os.path.join(root, fname)
            lines = count_lines(fpath)
            size = os.path.getsize(fpath)

            if is_test(fpath):
                dir_stats[top]["test"] += lines
                dir_stats[top]["test_f"] += 1
                all_test_files.append((lines, size, fpath))
            else:
                dir_stats[top]["app"] += lines
                dir_stats[top]["app_f"] += 1
                all_app_files.append((lines, size, fpath))

    return dir_stats, all_app_files, all_test_files

# === メイン処理 ===
repos = sys.argv[1:] if len(sys.argv) > 1 else []
if not repos:
    print("使用方法: python3 measure_code.py <repo1> <repo2> ...")
    sys.exit(1)

grand_app = grand_test = grand_app_f = grand_test_f = 0
all_app_sample = []
all_test_sample = []
warnings = []

for repo_name in repos:
    repo_path = os.path.join(BASE_DIR, repo_name)
    if not os.path.isdir(repo_path):
        print(f"⚠️  {repo_name}: 見つかりません")
        continue

    dir_stats, app_files, test_files = measure_repo(repo_path)
    app_total = sum(l for l,s,f in app_files)
    test_total = sum(l for l,s,f in test_files)
    app_fcount = len(app_files)
    test_fcount = len(test_files)

    print(f"\n{'='*55}")
    print(f"  {repo_name}")
    print(f"{'='*55}")
    print(f"  アプリ: {app_total:>8,}行 / {app_fcount}ファイル  "
          f"(平均 {app_total//app_fcount if app_fcount else 0}行/ファイル)")
    print(f"  テスト: {test_total:>8,}行 / {test_fcount}ファイル  "
          f"(平均 {test_total//test_fcount if test_fcount else 0}行/ファイル)")

    # ディレクトリ別内訳
    print(f"\n  ─ ディレクトリ別 ─")
    for d, s in sorted(dir_stats.items()):
        if s["app"] + s["test"] > 0:
            print(f"  {d:<22} APP {s['app']:>7,}行({s['app_f']}F)  "
                  f"TEST {s['test']:>7,}行({s['test_f']}F)")

    # 異常値チェック
    for lines, size, fpath in sorted(app_files + test_files, reverse=True)[:5]:
        bytes_per_line = size / lines if lines > 0 else 0
        rel = fpath.replace(repo_path, "")
        if lines > 10000:
            warnings.append(f"⚠️  {repo_name}{rel}: {lines:,}行（10,000行超）→ 生成物の可能性を確認してください")
        if bytes_per_line > 200 or bytes_per_line < 5:
            warnings.append(f"⚠️  {repo_name}{rel}: {bytes_per_line:.0f}バイト/行（異常値）")

    grand_app += app_total
    grand_test += test_total
    grand_app_f += app_fcount
    grand_test_f += test_fcount
    all_app_sample.extend(app_files)
    all_test_sample.extend(test_files)

# === グランドトータル ===
print(f"\n{'='*55}")
print(f"  合計")
print(f"{'='*55}")
print(f"  アプリコード: {grand_app:>8,}行 ({grand_app/10000:.2f}万行) / {grand_app_f}ファイル")
print(f"  テストコード: {grand_test:>8,}行 ({grand_test/10000:.2f}万行) / {grand_test_f}ファイル")

# === 異常値警告 ===
if warnings:
    print(f"\n{'─'*55}")
    print("  【要確認】異常値")
    for w in warnings:
        print(f"  {w}")

# === Layer 1: ランダムサンプル ===
print(f"\n{'─'*55}")
print("  【検証 Layer1】ランダムサンプル（実ファイル確認）")
sample_pool = all_app_sample + all_test_sample
if len(sample_pool) >= 3:
    samples = random.sample(sample_pool, 3)
    for lines, size, fpath in samples:
        print(f"\n  📄 {fpath.replace(BASE_DIR, '')} ({lines:,}行)")
        try:
            with open(fpath, encoding="utf-8", errors="ignore") as f:
                for i, line in enumerate(f):
                    if i >= 5:
                        break
                    print(f"     {i+1}: {line.rstrip()}")
        except:
            print("     (読み取り失敗)")

# === Layer 2: サイズ整合性 ===
print(f"\n{'─'*55}")
print("  【検証 Layer2】最大ファイルのバイト整合性")
if all_app_sample:
    largest = max(all_app_sample, key=lambda x: x[0])
    lines, size, fpath = largest
    bpl = size / lines if lines > 0 else 0
    status = "✅ 正常" if 10 <= bpl <= 500 else "⚠️ 要確認"
    print(f"  最大ファイル: {fpath.replace(BASE_DIR, '')} ({lines:,}行, {size:,}バイト)")
    print(f"  1行あたり {bpl:.1f}バイト → {status}")

print()
```

実行コマンド：
```bash
python3 ~/.claude/skills/code-metrics/scripts/measure_code.py NexusCore atelier-kyo-manager reserve-optimizer ...
```

---

## Phase 3: 「本当に読んだ」証明

スクリプトが以下を自動出力する：

**Layer 1 — ランダムサンプル**
計測したファイルからランダム3件を選び、実際の冒頭5行を表示。
「このファイルが存在して内容がある」ことを証明する。

**Layer 2 — バイトサイズ整合性**
最大ファイルのバイト数÷行数で「1行あたりのバイト数」を算出。
正常範囲: 10〜500バイト/行（それ以外は生成物の疑い）

**Layer 3 — git log確認**
各リポジトリに対して以下を表示：
```bash
git -C ~/projects/<repo> log --oneline | wc -l   # 総コミット数
git -C ~/projects/<repo> log -1 --format="%ci %s"  # 最終コミット
```

---

## Phase 4: テストケース数の計測

**Python (pytest):**
```bash
cd ~/projects/<repo>
python3 -m pytest --collect-only -q 2>/dev/null | tail -1
```
→ `X tests collected` の数字を取得

**JavaScript (jest/カスタム):**
```bash
# node が使えるか確認
. ~/.nvm/nvm.sh && node --version

# jest の場合
npx jest --listTests 2>/dev/null | wc -l

# カスタムランナー（reserve-optimizer等）の場合
find tests/ -name "*.test.js" | xargs grep -c "test(\|it(" 2>/dev/null | awk -F: '{s+=$2} END{print s}' 
```
→ カスタムランナーの場合は「概算」と明記する

---

## Phase 5: 異常値チェック

スクリプトが自動検出するが、以下は**手動で追加確認**すること：

| 条件 | アクション |
|---|---|
| ファイルが10,000行超 | ファイル冒頭20行を確認してコメント/生成物か判定 |
| ディレクトリ平均が300行超 | そのディレクトリの中身をlsして確認 |
| バイト/行が10未満 | 1バイト文字の連続ファイル（バイナリ混入の疑い） |
| バイト/行が500超 | 1行が異常に長い（minified JS等） |

---

## Phase 6: SSOT記録

結果を以下に保存：

**記録先**: `~/projects/obsidian-ssot/40_CAREER/02_実績検証/YYYY-MM-DD_コード行数計測.md`

```markdown
---
date: YYYY-MM-DD
tags: [実績検証, コード計測]
---

# コード行数計測結果

## 計測条件
- 除外ディレクトリ: mutants/ evaluation/ archive/ .venv/ 等
- 計測日: YYYY-MM-DD
- 計測スクリプト: ~/.claude/skills/code-metrics/scripts/measure_code.py

## 結果

| リポジトリ | アプリ行数 | テスト行数 |
|---|---|---|
| ... | ... | ... |
| **合計** | **XX万行** | **XX万行** |

## 3層検証
- Layer1 サンプル: ✅
- Layer2 サイズ整合: ✅
- Layer3 git log: ✅

## テストケース数
| リポジトリ | テスト数 | 計測方法 |
|---|---|---|
...
```

その後：
```bash
cd ~/projects/obsidian-ssot
git add -A
git commit -m "record: コード行数実測 YYYY-MM-DD（全プロジェクト）"
git push
```

`40_CAREER/02_実績検証/_INDEX.md` の照合サマリー表も更新すること。

---

## Phase 7: 完了報告

```
✅ 計測完了

📊 計測結果
アプリコード: XX万行 / XXXファイル（XX件除外: mutants等）
テストコード: XX万行 / XXXファイル
テストケース総数: X,XXX件

🔍 実測の証明（3層）
Layer1: ランダム3サンプルの冒頭5行を確認 ✅
Layer2: 最大ファイルのバイト整合性 OK（XX バイト/行）✅
Layer3: git log 確認済み（最終コミット: YYYY-MM-DD）✅

📁 SSOT記録: 40_CAREER/02_実績検証/YYYY-MM-DD_コード行数計測.md
🔗 コミット: XXXXXXX
```

---

## 注意事項

- **推測で答えない** — 実行前に数字を言わない。必ずスクリプト実行後に答える
- **mutants/ の罠** — NexusCoreにはmutants/が5.5万行含まれていた。必ず除外確認する
- **テストフレームワークを確認してから計測** — pytest/jest/カスタムで方法が違う
- **計測スクリプトは毎回保存する** — `~/.claude/skills/code-metrics/scripts/measure_code.py` に上書き保存して再利用可能にする（2026-07-03 監査Phase2でホーム直下からスキル同梱へ移設。count_code.py / count_tests.sh / audit_nexuscore.py / read_xlsx.py / update_xlsx.py も同フォルダ）
