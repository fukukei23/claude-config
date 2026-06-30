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
   - stdinから渡される hook入力JSONの `tool_input.command` を読む（コマンドライン引数ではなくstdin経由で受け取り、ユーザー/LLM生成文字列をシェル引数に渡さない）
   - コマンド文字列中で **既知のホワイトリストプレフィックス**（`~/projects/`、`~/.claude/`、`/home/yn4416/projects/`、`/home/yn4416/.claude/`）に一致する箇所のみを対応するUNCパス（`//wsl.localhost/Ubuntu/home/yn4416/projects/`、`//wsl.localhost/Ubuntu/home/yn4416/.claude/`）へ単純な文字列置換する（後述「ホワイトリスト方式にした理由」）。絶対パス形式（`/home/yn4416/...`）もWSL CLI版の共有ファイルに出現しうるため対象に含める（GLMレビューで指摘）
   - 置換が発生した場合のみ、以下をexit code 0で標準出力に書く（stderrには何も書かない）:
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
   - ホワイトリストはスクリプト先頭の配列定数として定義し、将来必要なプレフィックスが増えたら1行追加するだけで対応できるようにする

### ホワイトリスト方式にした理由（2回のレビューを経て確定）

**1回目（MiniMaxレビュー）**: 当初の「`~/`を正規表現で機械的に検出して置換する」案は、`echo ~`のようなBash自身のホーム展開を期待するコマンド、変数展開（`${HOME}/...`）、引用符・ヒアドキュメント内の`~/`など、文字列マッチだけでは「本当にWSLパスとして書かれた`~/`」と「Bash側のホーム展開に委ねるべき`~/`」を区別できないと指摘された。これを受けて一度「明示マーカー`@wsl:`方式」に変更した。

**2回目（Sonnetレビュー）**: マーカー方式は安全だが、既存のhandoff/SKILL.md/SSOTにはマーカーが付いていない（WSL CLI版で書かれており、書き手にマーカーを付ける動機がない）。そのため「既存の共有ファイルには効かず、Claude自身が`@wsl:`を書き忘れないようにする」という、結局は元の問題（変換し忘れるリスク）と同質の負荷が残ることが判明した。

**結論**: このセッションでの実際のgrep調査で、共有ファイル内のWSLパスは `~/projects/...` と `~/.claude/...` の2パターンに事実上限定されることが分かっている。汎用的な`~/`ではなく、**この2つの既知の固定プレフィックスのみ**を置換対象にすることで、
- `echo ~`や`${HOME}/...`等、ホーム展開を意図した記述が`~/projects/`や`~/.claude/`から始まることは現実的にない（誤爆リスクは正規表現案より大幅に低い）
- 書き手が何か注釈を覚える必要がなく、**既存の共有ファイルにも自動的に効く**（マーカー方式の欠点を解消）
を両立できる。将来新しいプレフィックスのパスが必要になった場合のみ、ホワイトリストに追記して対応する。

### 実装前の検証ステップ（plan化時に必須）

`updatedInput.command` がBashツールの実際の実行コマンドに反映されることは仕様上可能だが、本プロジェクトでの実機検証はまだ行っていない。実装の最初のタスクとして、ダミーのPreToolUseフック（例: 常に`command`の末尾に目印文字列を追記する）で実際にBash実行結果が変わることを確認してから、本実装に進む。

### 安全性・スコープ

- `$HOME`環境変数・Git Bash本体の設定・OSのマウント設定は一切変更しない
- 影響範囲はWindows Desktop版のBashツール呼び出しのみ。ユーザーが別途開く他のGit Bash・VSCodeターミナルには影響しない
- ロールバックは `settings.json` から該当フックエントリを削除するだけ

### 残るスコープ外の事項（このspecでは扱わない）

- ホワイトリストに含まれない `~/`形式パス（`~/projects/`・`~/.claude/`以外）、`/home/yn4416/...` の絶対パス形式、Windowsネイティブパスが明示的に必要な場面は対象外。引き続き手動で `\\wsl.localhost\Ubuntu\home\yn4416\` への変換が必要
- **Bashツール以外（Read/Write/Edit等）への波及は対象外**。これらのツールはファイルパスを直接引数に取るため、`~`展開の経路がBashとは異なり、本フック（matcher=Bash）では救えない。共有ファイルを開く際はBash経由（`cat`等）にするか、引き続き呼び出し側でパスを変換する
- フックの起動レイテンシ（`wsl bash -c "python3 ..."` を毎回起動するコスト。WSLディストロが停止中だと数秒のブロックが発生し得る）は許容トレードオフとして受け入れる。実装後に体感が問題になれば、Windows側の常駐プロセス化等の最適化を別途検討する

## 実装後のE2E検証で判明した2つの相互作用（Task5で発見）

### 1. `wsl bash -c "..."`でラップしたコマンド内のパスも書き換えられる

フックはBashツールに渡されるコマンド文字列全体を見るため、`wsl bash -c "cat /home/yn4416/.claude/settings.json"`のように**WSL内部で実行するつもりのコマンドを`wsl bash -c`でラップした場合でも**、内側の`/home/yn4416/.claude/`がUNCパスに書き換わってしまう。UNCパス（`//wsl.localhost/...`）はWindows側からのみ意味を持つ表記であり、WSL内部からは解決できないため、このケースではコマンドが壊れる。

**実害は小さい**: 本フック導入後は、そもそも`~/projects/...`・`~/.claude/...`等のホワイトリスト対象パスを**`wsl bash -c`でラップする必要がなくなる**（直接実行で解決するため）。CLAUDE.mdの「Cronや自動実行では`wsl bash -c`経由で呼ぶこと」という既存ルールは、対話的なBashツール呼び出しではなく自動実行（cron等、本フックが効かない文脈）向けの指示であり、通常のBashツール呼び出しでは今後`wsl bash -c`ラップを使わず直接パスを書けばよい。

### 2. 既にUNC形式で書かれたパスの中に部分文字列として再マッチする

`//wsl.localhost/Ubuntu/home/yn4416/projects/claude-config`のように、**既にUNC形式で手書きしたパス**であっても、その中に`/home/yn4416/projects/`という部分文字列が含まれるため、ホワイトリストの絶対パスルールが再度マッチし、`//wsl.localhost/Ubuntu//wsl.localhost/Ubuntu/home/yn4416/projects/claude-config`のように二重化して壊れる。

**回避策（運用ルール）**: フック導入後は、Windows Desktop版でWSLパスを書く際は**常に`~/projects/...`・`~/.claude/...`等のホワイトリスト表記を使い、UNCパスを手書きしない**。フックが自動的に変換するため、手書きのUNCパスはむしろ誤爆の原因になる。

これらは「既知の制約」として受け入れ、即座のコード修正は行わない（プレフィックスマッチに開始位置アンカー`^`や単語境界を入れる改修は将来の拡張候補とする）。

## GLMレビューでの追加指摘と判断（3回目のレビュー）

- **採用**: 絶対パス形式（`/home/yn4416/projects/`・`/home/yn4416/.claude/`）もホワイトリストに追加した（上記「処理内容」に反映済み）
- **既知の制約として明記（対応しない）**: 単純な文字列置換であるため、ヒアドキュメントやクォート内の文字列（例: `grep -r 'memo:~/projects/x'` のような検索文字列自体）に偶然これらのプレフィックスが含まれる場合、意図せず書き換わる。発生頻度は低いと判断し、MVPでは許容する
- **不採用（実証結果と矛盾するため）**: 「UNCパスはスラッシュ形式(`//wsl.localhost/...`)ではなくバックスラッシュ形式(`\\wsl.localhost\...`)にすべき」という指摘。本セッション内で `cd "//wsl.localhost/Ubuntu/home/yn4416"`・`ls`・UNC先へのシンボリックリンク作成を実際にスラッシュ形式で繰り返し実行し、すべて正常動作することを実証済みのため、現行のスラッシュ形式を維持する
- **将来の拡張候補（今回のMVPではスコープ外のまま据え置き）**:
  - `PreToolUse`のmatcherを`Read`/`Write`/`Edit`にも広げ、`tool_input.file_path`を同様にホワイトリスト置換する（Bash以外への波及というスコープ外事項を将来解消する選択肢）
  - WSL起動レイテンシを避けるため、`wsl bash -c "python3 ..."`の代わりにWindowsネイティブのNode.jsスクリプトで同じ文字列置換を行う（既存パターンとの整合より速度を優先したい場合の代替）

## テスト方針（plan策定時に詳細化）

- Windows Desktop版で `ls ~/projects/obsidian-ssot` ・`cat ~/.claude/CLAUDE.md` のようなコマンドが変換なしで成功することを確認
- ホワイトリストに含まれない`~/`（例: `echo ~`、`~/Desktop/...`）が変化せずそのまま実行されることを確認（誤爆しないこと）
- `~`を含まないコマンドが変化なく実行されることを確認（フックが誤って何かを書き換えないこと）
- WSLディストロが起動していない状態からの初回実行で、致命的な失敗や長時間ブロックが起きないことを確認
- WSL CLI版側の動作に変化がないことを確認（フックがWindows版`settings.json`のみに追加されているため、本来影響しないはずだが確認する）
