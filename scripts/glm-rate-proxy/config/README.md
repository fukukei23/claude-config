# config.json — glm-rate-proxy 実行時設定（正本・唯一）

`~/.config/glm-rate-proxy/config.json` は**本ファイルへのsymlink**（2026-08-29 单一ソース化）。
それ以外の値は `src/glm_rate_proxy/config.py` の DEFAULTS に従う（ここには意図的な上書きのみ書く）。
経緯: 2026-08-29までプロジェクト内configが「誰も読まない鏡像」で、実体は~/.config側にある二重構造だった（編集が効かない事故の真因）。symlink化で解決。
