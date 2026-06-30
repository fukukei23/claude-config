# Windows Desktop版 Claude Code のSSH鍵共有 設計

## 背景・課題

- Windows Desktop版Claude CodeのBashツール（Git Bash/MINGW64）から`git push`すると`Permission denied (publickey)`で失敗する
- 調査の結果、Windows側`C:\Users\yn441\.ssh`にはGitHub用の秘密鍵が一切存在せず（`known_hosts`のみ）、本物の鍵（`id_ed25519`）はWSL側`~/.ssh`にのみ存在することが判明した
- 両環境とも`ssh-agent`は起動しておらず、gitはデフォルトの鍵ファイル探索に依存している

## 検討した3案

### 案A: WSL側の既存鍵をWindows側からUNC経由で参照（採用）
Windows側の`~/.ssh/config`で`IdentityFile`をUNCパス（`//wsl.localhost/Ubuntu/home/yn4416/.ssh/id_ed25519`）に向ける。

### 案B: Windows Desktop専用の新しい鍵ペアを発行
`ssh-keygen`でWindows用に新規鍵を作成し、GitHubアカウントに2つ目のSSH鍵として追加登録する。環境ごとに鍵を分離するベストプラクティスだが、GitHub側の手動登録が必要。

### 案C: WSL側の秘密鍵をWindows側にファイルコピー
最も手軽だが、同じ秘密鍵を2つのOS環境に複製することになり、片方が漏れた場合に両方失効が必要になるなどセキュリティ衛生上案Bより劣る。

## 採用案: 案A（UNC経由でWSL側の既存鍵を参照）

### 実証済みの動作確認

実装前に一時的な`ssh -F <一時config>`で以下を実機検証し、いずれも成功した:
- `ssh -i "//wsl.localhost/Ubuntu/home/yn4416/.ssh/id_ed25519" -T git@github.com` → `Hi fukukei23! You've successfully authenticated...`（認証成功。exit code 1はGitHub仕様上の正常終了）
- `GIT_SSH_COMMAND="ssh -F <一時config>" git fetch origin`（claude-configリポジトリ） → 成功
- `GIT_SSH_COMMAND="ssh -F <一時config>" git push`（claude-configリポジトリ） → 成功、実際にコミットがリモートに反映された

当初「OpenSSHはUNC経由のファイルを権限エラーで拒否する可能性がある」と懸念していたが、実機では問題なく動作した。この懸念は払拭されたため、案Bの「環境分離のメリット」と天秤にかけても、**鍵を増やさず・GitHub側の設定変更もゼロで完結する案Aを採用する**。

### 採用理由

- 秘密鍵の実体はWSL側1箇所のみで完結し、複製されない（案Cより安全）
- GitHubアカウント側の設定変更が不要（案Bより手間が少ない）
- 実機検証済みで動作確実性が高い

### 処理内容

`C:\Users\yn441\.ssh\config` を新規作成する（現状このファイルは存在しない）:

```
Host github.com
  HostName github.com
  User git
  IdentityFile //wsl.localhost/Ubuntu/home/yn4416/.ssh/id_ed25519
  IdentitiesOnly yes
```

- `IdentitiesOnly yes`: 他の鍵を誤って試行させない
- `Host github.com`に限定し、他のSSHホストへの接続には影響を与えない

### 安全性・スコープ

- 秘密鍵ファイル自体はコピーも生成もしない。WSL側の既存ファイルを参照するだけ
- 設定は`Host github.com`に限定。他のリモートサーバーへのSSH接続には影響しない
- ロールバックは`C:\Users\yn441\.ssh\config`を削除するだけ

### 残るスコープ外の事項（このspecでは扱わない）

- WSLディストロが完全に停止している状態からの初回アクセスでは、`\\wsl.localhost\...`の解決に数秒のラグが生じる可能性がある（本セッション中に一度I/Oエラーが発生した実績あり）。致命的な失敗ではなく許容トレードオフとする
- `ssh-agent`の常駐化・WSL側とのエージェント転送（agent forwarding）は今回は扱わない。現状の鍵ファイル直接参照方式で要件を満たすため、必要になれば将来別途検討する

## テスト方針（plan策定時に詳細化）

- `C:\Users\yn441\.ssh\config`作成後、設定ファイルを使わない素の`git push`（`claude-config`・`obsidian-ssot`双方）が成功することを確認
- 他のSSHホスト（あれば）への接続が影響を受けていないことを確認
- WSL CLI版側のgit push/pullに影響がないことを確認（Windows側の設定ファイルのみの変更のため、本来影響しないはず）
