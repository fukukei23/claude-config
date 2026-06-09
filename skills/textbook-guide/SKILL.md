---
name: textbook-guide
description: >
  語彙帳・教科書・チートシート型のインタラクティブHTMLガイドサイトを新規作成・章追加するスキル。
  単一HTMLファイル・アコーディオン展開・ダーク/ライト切替・GitHub Pages公開まで一気に実行。
  「語彙帳作って」「教科書作って」「チートシート作って」「チュートリアル作って」「/textbook-guide」でトリガー。
user-invocable: true
---

# textbook-guide

## トリガーワード
新規: 「語彙帳作って」「教科書作って」「チートシート作って」「チュートリアル作って」「/textbook-guide new」
追加: 「章追加して」「/textbook-guide add」

## guide-builderとの使い分け
| | guide-builder | textbook-guide |
|---|---|---|
| 構成 | Markdown→HTML・複数ファイル | 単一HTMLファイル |
| 内容 | 詳細ガイド | 語彙帳・チートシート |
| UI | ページ遷移 | アコーディオン展開 |

## STEP 0: モード判定
既存リポジトリ名 → add / 新テーマ → new / 不明なら確認

## STEP 1: ヒアリング（new）
1メッセージで: タイトル/コンセプト・読者・章構成案・リポジトリ名

## STEP 2: 既存ガイドスキャン → 相互リンク選択

リストアップしてユーザーに選ばせる。選ばなくてもOK。

## STEP 3: デザイン継承
標準CSS変数（既存ガイドと統一）:
--bg:#1e1e2e / --bg-raised:#262638 / --accent:#7c3aed / --fg:#e4e4f0
ライト: --bg:#f8f9fa / --bg-raised:#fff / --fg:#2d2d3f

## STEP 4: 構成提示・確認
タイトル・URL・章構成・相互リンク先をユーザーに提示してOKをもらう

## STEP 5: HTML生成
index.html 1ファイル。外部依存なし。
必須: タイトル/コンセプトボックス・テーマ切替・相互リンクナビ・アコーディオン・フッター
アコーディオンJS:
  function toggle(h){const i=h.closest(".acc-item"),o=i.classList.contains("open");i.classList.toggle("open",!o);const k=i.dataset.key;if(k)localStorage.setItem("acc_"+k,(!o).toString());}
  document.querySelectorAll(".acc-item[data-key]").forEach(i=>{const k=i.dataset.key;if(localStorage.getItem("acc_"+k)==="true")i.classList.add("open");});
品質: モバイル対応・ライト/ダーク両対応・全data-key・外部CDN禁止

## STEP 6: GitHub + Pages
Initialized empty Git repository in //wsl.localhost/Ubuntu/home/yn4416/.git/

## STEP 7: SSOT記録
- 01_DECISIONS/career/YYYY-MM-DD_<repo>-作成.md 作成
- 00_SYSTEM/リポジトリ索引.md + repo-index.yaml 追記
- 10_DAILY/YYYY-MM-DD.md 追記

## add モード
STEP1: 章構成確認 → STEP2: 内容ヒアリング → STEP3: HTML編集+push → STEP4: 日記更新のみ

## 完了メッセージ
✅ textbook-guide 完了
📖 タイトル / 🌐 URL（数分で反映）/ 📁 ローカルパス / 📝 SSOT記録パス
