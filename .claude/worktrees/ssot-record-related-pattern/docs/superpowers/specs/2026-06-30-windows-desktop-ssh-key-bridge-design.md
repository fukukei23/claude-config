# Windows Desktop版 Claude Code のGitHub認証 設計

## 背景・課題

- Windows Desktop版Claude CodeのBashツール（Git Bash/MINGW64）から`git push`すると`Permission denied (publickey)`で失敗する
- 調査の結果、Windows側`C:\Users\yn441\.ssh`にはGitHub用の秘密鍵が一切存在せず（`known_hosts`のみ）、本物の鍵（`id_ed25519`）はWSL側`~/.ssh`にのみ存在することが判明した
- 両環境とも`ssh-agent`は起動しておらず、gitはデフォルトの鍵ファイル探索に依存している

## 検討した案の変遷

### 案A: WSL側の既存鍵をWindows側からUNC経由で参照（最初に採用→却下）

Windows側の`~/.ssh/config`で`IdentityFile`をUNCパス（`//wsl.localhost/Ubuntu/home/yn4416/.ssh/id_ed25519`）に向ける。

実機検証では`ssh -i`・`git fetch`・`git push`いずれも成功し、技術的には動作した。しかしGLMレビューで以下の懸念が指摘され、再検討の結果却下した:
- OpenSSHは通常、秘密鍵のパーミッションが緩い場合に警告・拒否するが、UNCパス越しだとこのチェックが機能しない可能性が高く、本来の安全機構を迂回している
- Windows側が万一侵害された場合、UNC経由でWSL側の本鍵（GitHubアカウント全体にアクセス可能な唯一の鍵）まで到達されるリスクがある（侵害時の被害範囲＝ブラストレディウスが環境分離している場合より大きい）
- `\\wsl.localhost\...`はMicrosoftが互換性を保証する正式なシステムパスではなく、将来のWindows Update・WSLアーキテクチャ変更で動かなくなるリスクがある

### 案B: Windows Desktop専用の新しい鍵ペアを発行（検討したが見送り）

`ssh-keygen`でWindows用に新規鍵を作成し、GitHubアカウントに2つ目のSSH鍵として追加登録する。環境ごとに鍵を分離するベストプラクティスで、却下した案Aの懸念（ブラストレディウス）を解消できる。

ただし、最終的に採用した案2（HTTPS + gh CLI）の方が鍵管理そのものから解放される点で優れていたため、こちらは不採用とした。

### 案C: WSL側の秘密鍵をWindows側にファイルコピー（却下）

最も手軽だが、同じ秘密鍵を2つのOS環境に複製することになり、片方が漏れた場合に両方失効が必要になるなどセキュリティ衛生上劣る。

## 採用案: HTTPS + GitHub CLI（`gh`）

SSH鍵の運用そのものをやめ、HTTPS経由のgit操作をGitHub CLI（`gh`）の認証情報（Windows資格情報マネージャー連携）に任せる。

### 採用理由

- SSH鍵を一切増やさない・複製しない・UNC経由の参照も行わないため、案A/B/Cすべてが抱えていた「秘密鍵そのものの管理」という問題が構造的になくなる
- `gh`は`winget`で即座にインストール可能（`winget search GitHub.cli`で存在確認済み、インストールに追加の前提条件は不要）
- 認証情報はWindows資格情報マネージャーが管理するため、`\\wsl.localhost\...`のようなWSLの実装詳細への依存がなくなる（将来のWindows Update等で壊れるリスクを案A/Bより低減できる）

### 共有リポジトリ問題の解決（重要な設計判断）

Windowsからは`\\wsl.localhost\...`経由でWSL側と**同じ物理リポジトリファイル**（`.git/config`を含む）を見ているため、各リポジトリの`git remote`URLを直接書き換えると、WSL CLI版の動作（現在SSHで正常動作している）にも影響してしまう。

これを避けるため、**個々のリポジトリの`remote` URLは変更せず**、Windows側のグローバルgitconfig（`C:\Users\yn441\.gitconfig`）にのみ以下の書き換えルールを追加する:

```
[url "https://github.com/"]
	insteadOf = git@github.com:
```

`C:\Users\yn441\.gitconfig`と WSL側の`~/.gitconfig`（実体は`/home/yn4416/.gitconfig`）は完全に別ファイルであることを確認済み（`git config --global --list --show-origin`で実体パスを確認）。そのため、このルールはWindows側のgit実行時にのみ適用され、WSL CLI版の動作には一切影響しない。

### 処理内容

1. `winget install GitHub.cli` でインストール
2. `gh auth login` を実行し、ブラウザでGitHub認証する（**ここはユーザー操作が必要** — ブラウザでのデバイスコード承認を伴うため自動化できない）
3. `C:\Users\yn441\.gitconfig` に上記`insteadOf`ルールを追加する
4. `claude-config`・`obsidian-ssot`それぞれで`git push`が成功することを確認する

### 安全性・スコープ

- 秘密鍵ファイルの新規作成・コピー・UNC参照を一切行わない
- 変更はWindows側のグローバルgitconfigの1ルール追加のみ。リポジトリ本体（`.git/config`）・WSL側の設定は無変更
- ロールバックは`C:\Users\yn441\.gitconfig`から該当の`[url ...]`セクションを削除するだけ（`gh`のアンインストールは任意、残しておいても害はない）

### 残るスコープ外の事項（このspecでは扱わない）

- `gh auth login`の認証フロー自体（デバイスコード方式かブラウザログイン方式か等）はplan策定時にユーザーと確認する
- 他のSSHホスト（GitHub以外）への接続設定は本specの対象外（今回`insteadOf`は`github.com`専用ルールのみ追加する）

## テスト方針（plan策定時に詳細化）

- `gh auth status`で認証済みであることを確認
- `claude-config`・`obsidian-ssot`双方で`git push`が成功することを確認
- WSL CLI版側の`git push`/`git pull`が引き続き正常動作すること（SSH接続のまま変化なし）を確認
- Windows側`C:\Users\yn441\.gitconfig`の変更がWSL側`~/.gitconfig`に波及していないことを確認
