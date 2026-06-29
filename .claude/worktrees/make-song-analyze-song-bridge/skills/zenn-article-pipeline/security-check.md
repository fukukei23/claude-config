# セキュリティスキャンルール

## 自動検出パターン

### 必ずマスキング

| パターン | 正規表現 | 置換後 |
|---------|---------|--------|
| VPS IP | `\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}`（私有IP以外） | `XXX.XXX.XXX.XXX` |
| 独自ドメイン | `[a-z0-9-]+\.(com|net|org|dev|io)`（example除く） | `your-xxx.example.com` |
| SSHユーザー名 | `ssh \w+@` | `ssh your_username@` |
| APIキー実値 | `sk-[a-zA-Z0-9]{20,}` | 即削除 |
| Discord Bot Token | `MTQ[a-zA-Z0-9]+` | 即削除 |
| 個人パス | `/home/[a-z]+/` | `/home/your_username/` |

### 許可（マスキング不要）

| パターン | 理由 |
|---------|------|
| `sk-abc123...` 等のサンプル値 | 実在しないため安全 |
| `github.com/username/repo` | 公開リポジトリは既知情報 |
| `zenn.dev/username/articles/` | 公開済み記事は既知情報 |
| `localhost`, `127.0.0.1`, `0.0.0.0` | 開発用アドレス |
| `192.168.x.x`, `10.x.x.x`, `172.16-31.x.x` | プライベートIPは直接特定不可 |

## 一括スキャンコマンド

```bash
# 個人情報・機密情報
grep -rn "sk-[a-zA-Z0-9]\{10\}\|MTQ[a-zA-Z0-9]\{5\}\|BSA[a-zA-Z0-9]\{5\}" articles/ | grep -v "_INDEX"

# ドメイン・IP・ユーザー名
grep -rn "yn4416\|flopenclaw\|162\.43\|192\.168\.[0-9]\+\.[0-9]\+" articles/ | grep -v "_INDEX"
```

## 修正後の確認

スキャン結果が0件になるまで修正を繰り返す。
