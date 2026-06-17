---
name: reverse-engineer-song
description: YouTube動画（楽曲）をリバースエンジニアリングし、音楽/画像/動画の3モダリティの生成AI用プロンプト仕様書を出力する。CCはYouTubeを視聴できないため、Gemini API経由（scripts/api/gemini.py）で分析を委任し、CCは結果の構造化・保存に専任する。ユーザーが「逆コンパイルして」「この曲から仕様書作って」「リバースエンジニアリング」「YouTubeから分析して」「YouTubeから楽曲分析」「この動画からプロンプト抜いて」等と言った時、または /reverse-engineer-song を呼んだ時にトリガー。
---

# 楽曲逆コンパイル — 生成AI用プロンプト仕様書ウィザード

## トリガーワード
「逆コンパイルして」「この曲から仕様書作って」「リバースエンジニアリング」「YouTubeから分析して」「YouTubeから楽曲分析」「この動画からプロンプト抜いて」「/reverse-engineer-song」

## 前提知識（進行開始前に必ず読み込む）
- `references/楽曲逆コンパイル_マスタープロンプト.md`（**本体**・Geminiに投げるマスタープロンプト・分析要件4項目・出力フォーマット）

> **二重管理注記**: references のマスタープロンプトはSSOT一次ソース（`obsidian-ssot/01_DECISIONS/ai-music/2026-06-15_楽曲逆コンパイル_生成AIプロンプトマスタープロンプト.md`）の実体コピー。更新時は両方修正すること。

## 設計の核心（厳守）
- **CCはYouTube動画を視聴・聴取できない**。分析は Gemini(gemini-code) に完全委任する。
- CCの役割は **①マスタープロンプト組立 ②Gemini結果の構造検証・Markdown整形 ③保存 ④既存楽曲skillへの橋渡し** のみ。

## 進行（5フェーズ・ハイブリッド）

**🔴 = 人間判断ポイント。必ず停止してユーザー確認を待つ。** 分析は「聴かない/見ないと分からない」ので、Gemini投下・結果受領ごとに停止。

### Phase 0: 対象確認（起点）🔴

`AskUserQuestion` で確認:
```
質問:「逆コンパイルするYouTube動画のURLを教えてください」
（ユーザーがURLを回答）
質問:「分析の粒度は？」
選択肢:
  フル（4分前後・全セクション）
  フックのみ（サビ中心・1分以内）
  60秒（ショート用）
```

### Phase 1: Gemini API 自動解析

1. `references/楽曲逆コンパイル_マスタープロンプト.md` をマスタープロンプトとして使用
2. CCが `scripts/api/gemini.py` を実行し、Gemini API経由でYouTube動画を真正解析する:
   ```bash
   cd /home/yn4416/projects/claude-config
   set -a; source ~/.secrets.env; set +a
   .venv/bin/python scripts/api/gemini.py --youtube "<Phase0で取得したURL>"
   ```
3. スクリプトは標準出力にJSON `{"status","summary","full_data","error"}` を返す
   - **status=error** の場合 → ユーザーにエラー内容を提示し、手動Gemini投下（従来フロー）にフォールバックして停止 🔴
   - **status=ok** の場合 → summary を解析結果として次Phaseへ進む
4. CCは summary のみを文脈に読み込む（full_dataキャッシュは必要時のみ参照）

### Phase 2: Gemini結果受領・構造化 🔴

1. Phase 1 の summary（Gemini解析結果）を読む。詳細が必要な場合は `full_data` キャッシュファイルを追加で読み込む
2. **構造検証**（以下4点を確認）:
   - [ ] セクション1「楽曲構造・リファレンスデータ」にタイムライン表があるか
   - [ ] セクション2「音楽生成AI用プロンプト」に Style/Tags ＋ Lyrics制御タグがあるか
   - [ ] セクション3「画像生成AI用プロンプト」に3シチュエーション ＋ Negative Promptがあるか
   - [ ] セクション4「動画生成AI用モーション制御」に静寂/動的の2セクションがあるか
3. **不備あり** → ユーザーに「gemini.py に追加指示を与えて再実行しますか？」と確認し、承認なら再実行して停止 🔴
4. **全て揃い** → Markdown整形（見出し階層・コードブロック整理）し、ユーザーに最終確認提示 🔴

### Phase 3: 単独ファイル保存

1. 曲名を確認（Gemini出力の `# 【曲名】完全再現・生成AI用プロンプト仕様書` から抽出、不明ならユーザーに確認）
2. `/home/yn4416/projects/obsidian-ssot/01_DECISIONS/ai-music/YYYY-MM-DD_<曲名>_逆コンパイル仕様書.md` に保存
   - frontmatter: `project: ai-music`, `date: YYYY-MM-DD`, `tags: [ai-music, 生成AI, 逆コンパイル仕様書]`
   - 本文: Gemini出力（構造化済み）をそのまま記載
   - 末尾に「生成元: YouTube URL」「生成日時」「使用マスタープロンプト: reverse-engineer-song/references/楽曲逆コンパイル_マスタープロンプト.md」を付記
3. commit:
   ```bash
   cd /home/yn4416/projects/obsidian-ssot
   git add 01_DECISIONS/ai-music/YYYY-MM-DD_<曲名>_逆コンパイル仕様書.md
   git commit -m "feat: <曲名> 逆コンパイル仕様書（reverse-engineer-song生成）"
   ```

### Phase 4: 橋渡しオプション（双方向リンクの出口）🔴

`AskUserQuestion` で確認:
```
質問:「この仕様書を既存の楽曲制作skillに持ち込みますか？」
選択肢:
  cyber-wa-song で制作する（サイバー和モダン系）
  sangoku-song で制作する（三国志HIPHOP系）
  いいえ（仕様書保存のみで終了）
```

- **cyber-wa-song / sangoku-song 選択** → 該当skillの Phase 0「その他（カスタム）」経由で誘導。保存した仕様書のパスを伝え、世界観データとして参照するよう案内
- **いいえ** → 「仕様書を保存しました: `<パス>`」と表示して終了

## 関連skill（双方向リンク）
- `sangoku-song` — Phase 0「その他（カタログ参照）」から本skillを呼び出し可能
- `cyber-wa-song` — Phase 0「その他（カスタム）」から本skillを呼び出し可能
