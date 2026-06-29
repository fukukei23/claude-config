# Windows Desktop版 Claude Code の WSLパス変換フック 設計

## 背景・課題

- このPCではWSL2 Ubuntu と Windows Desktop版 Claude Code を並行のメイン環境として使う運用にしている
- handoff・SKILL.md・SSOT等の共有ファイルは主にWSL CLI版で書かれ、`~/projects/obsidian-ssot/...` のようなUnixパス（`$HOME`基準）で記述されることが多い
- Windows Desktop版のBashツールはGit Bash(MINGW64)上で動作し、そこでの `$HOME` は `/c/Users/yn441` に解決される。そのため `~/projects/...` 形式のパスはそのまま実行できず、毎回 `\\wsl.localhost\Ubuntu\home\yn4416\` への変換が必要
- 変換漏れはコマンド実行失敗や誤動作につながり、Claude自身がセッションごとに変換コストを払うことになる。人間（ユーザー）はこの混乱で困っていないが、Claude Code自身の作業遅延・ミスのリスクを取り除きたい

## 検討して却下した案

### 案: `/etc/fstab`編集 or `/home/yn4416`シンボリックリンク（OSレベルマウント）
- UNC先（`\\wsl.localhost\Ubuntu\home\yn4416`）へのシンボリックリンク作成自体は管理者権限不要で成功することを実証済み（`/tmp`配下でテスト）
- しかし `/home/yn4416` という固定パスとして使うには `C:\Program Files\Git\etc\fstab` の編集が必要で管理者権限を要する
- かつこれは `/home/yn4416/...` 形式の絶対パスのみを解決し、実際に多用される `~/projects/...`（`$HOME`基準）は解決しない
- 影響範囲もこのPC上の全Git Bash利用（VSCodeターミナル等）に及び、Claude Code専用にできない
- **却下理由**: 手間とリスクに対して効果が限定的

### 案: `$HOME`環境変数をWindows全体のGit Bash設定で上書き
- `~/projects/...` は解決できるが、Git/SSH等の他ツールが同じGit Bash上で `$HOME` を見て `.gitconfig` や `.ssh` を探すため、Windows版Git Bashの他の用途すべてに副作用が及ぶ
- **却下理由**: 危険度 中〜高

### 案: `settings.json` の `env.HOME` をUNCパスに上書き
- Claude Code設定の `env` フィールドはBashツール起動プロセスに環境変数を注入できる公式機能だが、調査の結果以下のリスクが判明：
  - Claude Code本体（Node.jsプロセス）自体にも`HOME`が伝播し、`~/.claude/`配下（スキル・ログ・セッション履歴等）の読み書きがUNC経路に巻き込まれる可能性がある（未検証だが影響範囲が広すぎる）
  - Git Bash(MSYS)はUNCパスの扱いが弱く、`git status`の著しい遅延・失敗や `find`/`grep -r` の速度劣化など既知の問題がある
  - `$HOME`という基盤変数を変えること自体が、個別コマンドでUNCパスを使うこと（実証済みで安全）とは質的に異なるリスクを持つ
- **却下理由**: `$HOME`という基盤変数を変更するアプローチ全般に共通するリスク（MSYSのUNC弱さ・Claude Code本体への副作用）を払拭できない

## 採用案: PreToolUseフックによるコマンド文字列の前処理変換

`$HOME`やOS設定は一切変更せず、**Bashツールが実行する直前のコマンド文字列だけを書き換える**。

### 採用理由
- 個別コマンドの引数としてUNCパス（`//wsl.localhost/Ubuntu/home/yn4416/...`）を使うこと自体は本セッションで実証済みで問題なく動く（`ls`/`grep`/`cat`等）
- `$HOME`環境変数やGit Bash本体の設定を一切変更しないため、却下した3案が抱える問題（MSYSのUNC-on-HOME問題、Claude Code本体への副作用、Git Bash全体への影響）が構造的に発生しない
- Claude Codeの`PreToolUse`フックには公式に `updatedInput.command` でツール入力を書き換える仕組みがあり（`hookSpecificOutput.permissionDecision: "allow"` + `updatedInput`をexit 0で出力）、この用途に適合する
- このプロジェクトには既に `PreToolUse`/`PostToolUse` フックを使い、Windows側の`settings.json`からWSL内のPythonスクリプトを `wsl bash -c "python3 /home/yn4416/.claude/scripts/security/check-command-safety.py ..."` の形で呼ぶ既存パターンがあり、それに揃えられる

### 処理内容

1. 新規スクリプト `path-rewrite.py` をWSL側 `/home/yn4416/.claude/scripts/security/` に追加（既存の `check-command-safety.py` と同じ管理下）
2. PreToolUseフックとして以下を `settings.json` に追加（**Windows Desktop版の`settings.json`にのみ**。WSL CLI版は元々問題ないため不要）
   - `matcher`: `Bash`（既存フックの`matcher: ""`=全ツールとは違い、Bash専用に限定する）
   - `command`: `wsl bash -c "python3 /home/yn4416/.claude/scripts/security/path-rewrite.py"`
3. スクリプトの処理:
   - stdinから渡される hook入力JSONの `tool_input.command` を読む
   - コマンド文字列中の `~/`（先頭または空白・引用符直後に出現するトークン）を正規表現で `//wsl.localhost/Ubuntu/home/yn4416/` に置換
   - 置換が発生した場合のみ、以下をexit code 0で標準出力に書く:
     ```json
     {
       "hookSpecificOutput": {
         "hookEventName": "PreToolUse",
         "permissionDecision": "allow",
         "updatedInput": { "command": "<変換後のコマンド文字列>" }
       }
     }
     ```
   - 置換が発生しない場合は何も出力せず終了（素通り）

### 安全性・スコープ

- `$HOME`環境変数・Git Bash本体の設定・OSのマウント設定は一切変更しない
- 影響範囲はWindows Desktop版のBashツール呼び出しのみ。ユーザーが別途開く他のGit Bash・VSCodeターミナルには影響しない
- ロールバックは `settings.json` から該当フックエントリを削除するだけ

### 残るスコープ外の事項（このspecでは扱わない）

- `~/projects/...` 以外の表記（`/home/yn4416/...` の絶対パス形式、Windowsネイティブパスが明示的に必要な場面）は対象外。引き続き手動で `\\wsl.localhost\Ubuntu\home\yn4416\` への変換が必要
- 共有ファイル（handoff/SKILL.md/SSOT）側の表記ルール変更は本specの範囲外（必要なら別途検討）

## テスト方針（plan策定時に詳細化）

- Windows Desktop版で `ls ~/projects/obsidian-ssot` のようなコマンドが変換なしで成功することを確認
- `~`を含まないコマンド（変換不要なコマンド）が変化なく実行されることを確認（フックが誤って何かを書き換えないこと）
- WSLディストロが起動していない状態からの初回実行で、致命的な失敗や長時間ブロックが起きないことを確認
- WSL CLI版側の動作に変化がないことを確認（フックがWindows版`settings.json`のみに追加されているため、本来影響しないはずだが確認する）
