#!/usr/bin/env python3
"""MiniMax MCP Server - MiniMax M3をMCPツールとして提供"""

import json
import sys
import os
import urllib.request

def _load_key():
    key = os.environ.get('MINIMAX_API_KEY', '')
    if key:
        return key
    secrets = os.path.expanduser('~/.secrets.env')
    if os.path.exists(secrets):
        with open(secrets) as f:
            for line in f:
                line = line.strip()
                if line.startswith('export MINIMAX_API_KEY='):
                    return line.split('=', 1)[1].strip().strip('"').strip("'")
    return ''

MINIMAX_KEY = _load_key()
MINIMAX_URL = 'https://api.minimax.io/anthropic/v1/messages'
MODEL = 'MiniMax-M3'


def call_minimax(prompt, max_tokens=2000):
    # ステータスファイルに記録（ステータスライン表示用）
    try:
        with open('/tmp/llm-last-used.txt', 'w') as f:
            f.write('🟠 MiniMax')
    except Exception:
        pass
    if not MINIMAX_KEY:
        return 'Error: MINIMAX_API_KEY が設定されていません'
    data = json.dumps({
        'model': MODEL,
        'max_tokens': max_tokens,
        'messages': [{'role': 'user', 'content': prompt}]
    }).encode('utf-8')
    req = urllib.request.Request(
        MINIMAX_URL, data=data,
        headers={
            'x-api-key': MINIMAX_KEY,
            'anthropic-version': '2023-06-01',
            'Content-Type': 'application/json'
        }
    )
    with urllib.request.urlopen(req, timeout=300) as res:
        r = json.loads(res.read())
    for block in r.get('content', []):
        if block.get('type') == 'text':
            return block['text']
    return ''


TOOLS = [
    {
        "name": "minimax_ask",
        "description": "MiniMax M3に作業を依頼する。要約・翻訳・コード変換など大量処理・コスト効率が重要なタスクに使用。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "MiniMaxへの指示とコンテンツ"},
                "max_tokens": {"type": "integer", "description": "最大出力トークン数（デフォルト2000）", "default": 2000}
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "minimax_summarize_file",
        "description": "ファイルをMiniMaxで要約・分析する。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "処理するファイルのパス（絶対パス）"},
                "instruction": {"type": "string", "description": "処理指示（例: '30文字で要約', '英語に翻訳'）", "default": "内容を簡潔に要約してください"}
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "minimax_batch_process",
        "description": "複数ファイルをMiniMaxでまとめて処理する。大量処理に最適。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "処理するファイルパスのリスト"
                },
                "instruction": {"type": "string", "description": "各ファイルへの処理指示"}
            },
            "required": ["file_paths", "instruction"]
        }
    },
    {
        "name": "minimax_translate_file",
        "description": "ファイル全体をMiniMaxで翻訳する。大量ファイルの一括英訳に最適。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "翻訳するファイルのパス（絶対パス）"},
                "target_lang": {"type": "string", "description": "翻訳先の言語（例: en, ja, ko, zh）", "default": "en"},
                "source_lang": {"type": "string", "description": "元の言語（例: ja, en）。省略で自動検出", "default": "auto"}
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "minimax_convert_format",
        "description": "データフォーマットをMiniMaxで変換する。JSON↔YAML↔CSV等の変換に使用。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "変換するデータ内容"},
                "from_format": {"type": "string", "description": "元のフォーマット（json / yaml / csv / xml / toml）"},
                "to_format": {"type": "string", "description": "変換先フォーマット（json / yaml / csv / xml / toml）"}
            },
            "required": ["content", "from_format", "to_format"]
        }
    },
    {
        "name": "minimax_generate_test_data",
        "description": "MiniMaxでテストデータ・モックデータを生成する。開発用ダミーデータの自動作成に最適。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "schema_description": {"type": "string", "description": "データのスキーマ説明（例: 'ユーザー情報：名前、メール、年齢、住所'）"},
                "count": {"type": "integer", "description": "生成するデータ件数（デフォルト5）", "default": 5},
                "format": {"type": "string", "description": "出力フォーマット（json / csv / sql）", "default": "json"}
            },
            "required": ["schema_description"]
        }
    },
    {
        "name": "minimax_extract_keywords",
        "description": "MiniMaxでテキストからキーワード・要点を抽出する。長文からタグ・見出し自動生成に使用。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "キーワード抽出対象のテキスト"},
                "max_keywords": {"type": "integer", "description": "最大キーワード数（デフォルト10）", "default": 10}
            },
            "required": ["text"]
        }
    },
    {
        "name": "minimax_diff_summary",
        "description": "MiniMaxでgit diffの変更内容を要約する。大きな変更の全体像を素早く把握。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "diff_content": {"type": "string", "description": "git diffの内容"},
                "detail_level": {"type": "string", "description": "要約の詳細度（brief / normal / detailed）", "default": "normal"}
            },
            "required": ["diff_content"]
        }
    },
    {
        "name": "minimax_log_analysis",
        "description": "MiniMaxでログファイルを解析する。エラーログから傾向・頻度・重要パターンを抽出。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "ログファイルのパス（絶対パス）"},
                "focus": {"type": "string", "description": "分析の焦点（例: errors, performance, frequency）。省略で総合分析", "default": ""}
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "minimax_error_group",
        "description": "MiniMaxでエラーログを類似パターン別にグループ化する。大量ログから実質的なエラー種別数を抽出。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "ログファイルのパス（絶対パス）"},
                "max_groups": {"type": "integer", "description": "最大グループ数（デフォルト10）", "default": 10}
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "minimax_generate_schema",
        "description": "MiniMaxでサンプルデータからJSON Schema・TypeScript型定義を生成する。APIレスポンスの型定義に最適。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sample_data": {"type": "string", "description": "サンプルデータ（JSON・CSV等）"},
                "output_format": {"type": "string", "description": "出力形式（json_schema / typescript / zod / pydantic）。デフォルトjson_schema", "default": "json_schema"},
                "type_name": {"type": "string", "description": "型名（例: User, Order）。省略で自動命名", "default": ""}
            },
            "required": ["sample_data"]
        }
    },
    {
        "name": "minimax_clean_data",
        "description": "MiniMaxでCSV/JSONデータをクリーニングする。欠損値・表記揺れ・異常値の自動検出と修正提案。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "data": {"type": "string", "description": "クリーニング対象データ（CSV・JSON）"},
                "rules": {"type": "string", "description": "追加ルール（例: '郵便番号は7桁', '電話番号はハイフン統一'）。省略可", "default": ""}
            },
            "required": ["data"]
        }
    },
    {
        "name": "minimax_cron_helper",
        "description": "MiniMaxでcron式の生成・解読を行う。自然言語→cron式、cron式→日本語解説の双方向変換。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "cron式または自然言語のスケジュール説明"},
                "mode": {"type": "string", "description": "generate（自然言語→cron式） / explain（cron式→解説）。デフォルトgenerate", "default": "generate"}
            },
            "required": ["input"]
        }
    },
    {
        "name": "minimax_env_check",
        "description": "MiniMaxで.env・config.ymlの不整合を検出する。必須変数の抜け漏れ・型不一致・セキュリティ問題を自動発見。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": ".env または設定ファイルのパス（絶対パス）"},
                "reference": {"type": "string", "description": "期待される変数一覧・スキーマ（省略可）", "default": ""}
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "minimax_write_email",
        "description": "MiniMaxでビジネスメールの文面を生成する。日本語のビジネスメール・案内文・謝罪文等に最適。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "purpose": {"type": "string", "description": "メールの目的・内容（例: '会議の日程変更のお願い'）"},
                "tone": {"type": "string", "description": "トーン（formal / normal / casual）。デフォルトformal", "default": "formal"},
                "recipient": {"type": "string", "description": "宛先の情報（例: '取引先の田中部長'）。省略可", "default": ""},
                "context": {"type": "string", "description": "追加コンテキスト（前回のやり取り等）。省略可", "default": ""}
            },
            "required": ["purpose"]
        }
    },
    {
        "name": "minimax_summarize_url",
        "description": "MiniMaxでURLの内容を要約する。記事・ドキュメント・ブログの内容把握に使用。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Webページの本文テキスト（事前に取得済みのもの）"},
                "max_length": {"type": "integer", "description": "要約の最大文字数（デフォルト300）", "default": 300},
                "focus": {"type": "string", "description": "注目ポイント（例: 技術詳細, 価格, 期日）。省略で全体要約", "default": ""}
            },
            "required": ["content"]
        }
    },
    {
        "name": "minimax_diff_releases",
        "description": "MiniMaxで2バージョン間の差分を要約し、リリースノートを生成する。バージョンアップ時の変更概要作成に最適。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "diff_content": {"type": "string", "description": "2バージョン間のdiffまたはchangelog"},
                "from_version": {"type": "string", "description": "旧バージョン（例: v1.0.0）"},
                "to_version": {"type": "string", "description": "新バージョン（例: v2.0.0）"},
                "audience": {"type": "string", "description": "対象読者（developer / user / manager）。デフォルトdeveloper", "default": "developer"}
            },
            "required": ["diff_content", "from_version", "to_version"]
        }
    }
]


def handle_request(req):
    method = req.get('method', '')
    params = req.get('params', {})
    req_id = req.get('id')

    if method == 'initialize':
        result = {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "minimax-mcp", "version": "1.0.0"}
        }

    elif method in ('notifications/initialized', 'initialized'):
        return None

    elif method == 'tools/list':
        result = {"tools": TOOLS}

    elif method == 'tools/call':
        tool_name = params.get('name')
        args = params.get('arguments', {})

        if tool_name == 'minimax_ask':
            # M3はThinkingモデルのため最低2000トークン必要（それ以下だと空レスポンス）
            tokens = max(args.get('max_tokens', 2000), 2000)
            text = call_minimax(args['prompt'], tokens)
            result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'minimax_summarize_file':
            fp = args['file_path']
            if not os.path.exists(fp):
                result = {"content": [{"type": "text", "text": f"ファイルが見つかりません: {fp}"}], "isError": True}
            else:
                with open(fp, encoding='utf-8', errors='ignore') as f:
                    content = f.read()[:8000]
                instruction = args.get('instruction', '内容を簡潔に要約してください')
                text = call_minimax(f"{instruction}\n\n---\n{content}")
                result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'minimax_batch_process':
            instruction = args['instruction']
            outputs = []
            for fp in args['file_paths']:
                if os.path.exists(fp):
                    with open(fp, encoding='utf-8', errors='ignore') as f:
                        content = f.read()[:4000]
                    fname = os.path.basename(fp)
                    text = call_minimax(f"{instruction}\n\nファイル: {fname}\n---\n{content}")
                    outputs.append(f"[{fname}]\n{text}")
                else:
                    outputs.append(f"[{os.path.basename(fp)}] ファイルが見つかりません")
            result = {"content": [{"type": "text", "text": "\n\n".join(outputs)}]}

        elif tool_name == 'minimax_translate_file':
            fp = args['file_path']
            if not os.path.exists(fp):
                result = {"content": [{"type": "text", "text": f"ファイルが見つかりません: {fp}"}], "isError": True}
            else:
                with open(fp, encoding='utf-8', errors='ignore') as f:
                    content = f.read()[:8000]
                tgt = args.get('target_lang', 'en')
                src = args.get('source_lang', 'auto')
                src_inst = f"{src} → " if src != 'auto' else ""
                prompt = f"以下のテキストを{src_inst}{tgt}に翻訳してください。翻訳結果のみ出力。\n\n---\n{content}"
                text = call_minimax(prompt)
                result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'minimax_convert_format':
            content = args['content']
            src_fmt = args['from_format']
            tgt_fmt = args['to_format']
            prompt = f"以下の{src_fmt}データを{tgt_fmt}に変換してください。変換結果のみ出力。\n\n---\n{content}"
            text = call_minimax(prompt)
            result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'minimax_generate_test_data':
            schema = args['schema_description']
            count = args.get('count', 5)
            fmt = args.get('format', 'json')
            prompt = f"以下のスキーマに基づいて{count}件のテストデータを{fmt}形式で生成してください。日本のリアルなデータを使用。\n\nスキーマ: {schema}\n\nデータのみ出力。"
            text = call_minimax(prompt)
            result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'minimax_extract_keywords':
            text_content = args['text']
            max_kw = args.get('max_keywords', 10)
            prompt = f"以下のテキストから重要なキーワードを最大{max_kw}個抽出してください。\nキーワードをカンマ区切りで出力。\n\n---\n{text_content}"
            text = call_minimax(prompt)
            result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'minimax_diff_summary':
            diff = args['diff_content']
            detail = args.get('detail_level', 'normal')
            detail_map = {'brief': '1-2文で簡潔に', 'detailed': 'ファイルごとに詳細に'}
            detail_inst = detail_map.get(detail, 'ファイルごとに要約')
            prompt = f"以下のgit diffの変更内容を{detail_inst}まとめてください。\n\n---\n{diff[:8000]}"
            text = call_minimax(prompt)
            result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'minimax_log_analysis':
            fp = args['file_path']
            if not os.path.exists(fp):
                result = {"content": [{"type": "text", "text": f"ファイルが見つかりません: {fp}"}], "isError": True}
            else:
                with open(fp, encoding='utf-8', errors='ignore') as f:
                    content = f.read()[:8000]
                focus = args.get('focus', '')
                focus_section = f"\n分析の焦点: {focus}" if focus else "\n総合分析（エラー傾向・頻度・重要パターン）"
                prompt = f"以下のログファイルを分析してください。{focus_section}\n\nファイル: {os.path.basename(fp)}\n---\n{content}"
                text = call_minimax(prompt)
                result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'minimax_error_group':
            fp = args['file_path']
            if not os.path.exists(fp):
                result = {"content": [{"type": "text", "text": f"ファイルが見つかりません: {fp}"}], "isError": True}
            else:
                with open(fp, encoding='utf-8', errors='ignore') as f:
                    content = f.read()[:8000]
                max_g = args.get('max_groups', 10)
                prompt = f"以下のエラーログを類似パターン別にグループ化してください。最大{max_g}グループ。各グループについて：代表例、出現回数、根本原因の推定を出力。\n\n---\n{content}"
                text = call_minimax(prompt)
                result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'minimax_generate_schema':
            sample = args['sample_data']
            fmt = args.get('output_format', 'json_schema')
            type_name = args.get('type_name', '')
            tn_section = f" 型名: {type_name}" if type_name else ""
            prompt = f"以下のサンプルデータから{fmt}形式の型定義を生成してください。{tn_section}\n\n---\n{sample}\n\n型定義のみ出力。"
            text = call_minimax(prompt)
            result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'minimax_clean_data':
            data = args['data']
            rules = args.get('rules', '')
            rules_section = f"\n追加ルール:\n{rules}" if rules else ""
            prompt = f"以下のデータをクリーニングしてください。欠損値・表記揺れ・異常値を検出し、修正後のデータを出力。{rules_section}\n\n---\n{data}\n\n修正内容の説明と、クリーニング後のデータを出力。"
            text = call_minimax(prompt)
            result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'minimax_cron_helper':
            inp = args['input']
            mode = args.get('mode', 'generate')
            if mode == 'explain':
                prompt = f"以下のcron式を解説してください。実行タイミングを分かりやすく日本語で説明。\n\ncron式: {inp}"
            else:
                prompt = f"以下の自然言語のスケジュール説明からcron式を生成してください。\n5フィールド形式（分 時 日 月 曜日）で出力。解説も添える。\n\n説明: {inp}"
            text = call_minimax(prompt)
            result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'minimax_env_check':
            fp = args['file_path']
            if not os.path.exists(fp):
                result = {"content": [{"type": "text", "text": f"ファイルが見つかりません: {fp}"}], "isError": True}
            else:
                with open(fp, encoding='utf-8', errors='ignore') as f:
                    content = f.read()[:8000]
                ref = args.get('reference', '')
                ref_section = f"\n\n期待される変数:\n{ref}" if ref else ""
                prompt = f"以下の設定ファイルをチェックしてください。必須変数の抜け漏れ、型の不一致、ハードコードされたシークレット、非推奨の設定値を検出。{ref_section}\n\nファイル: {os.path.basename(fp)}\n---\n{content}"
                text = call_minimax(prompt)
                result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'minimax_write_email':
            purpose = args['purpose']
            tone = args.get('tone', 'formal')
            recipient = args.get('recipient', '')
            ctx = args.get('context', '')
            recipient_section = f"\n宛先: {recipient}" if recipient else ""
            ctx_section = f"\n\n前回のやり取り:\n{ctx}" if ctx else ""
            prompt = f"以下の目的でビジネスメールを作成してください。\nトーン: {tone}{recipient_section}\n目的: {purpose}{ctx_section}\n\n件名と本文のみ出力。"
            text = call_minimax(prompt)
            result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'minimax_summarize_url':
            content = args['content']
            max_len = args.get('max_length', 300)
            focus = args.get('focus', '')
            focus_section = f"\n注目ポイント: {focus}" if focus else ""
            prompt = f"以下のWebページ本文を{max_len}文字以内で要約してください。{focus_section}\n\n---\n{content[:8000]}"
            text = call_minimax(prompt)
            result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'minimax_diff_releases':
            diff = args['diff_content']
            from_v = args['from_version']
            to_v = args['to_version']
            audience = args.get('audience', 'developer')
            audience_map = {'user': 'エンドユーザー向け（機能追加・変更を中心に）', 'manager': 'マネージャー向け（影響範囲・リスクを中心に）'}
            audience_inst = audience_map.get(audience, '開発者向け（技術的変更内容を中心に）')
            prompt = f"以下の{from_v}→{to_v}の変更差分からリリースノートを生成してください。{audience_inst}\n\n---\n{diff[:8000]}"
            text = call_minimax(prompt)
            result = {"content": [{"type": "text", "text": text}]}

        else:
            result = {"content": [{"type": "text", "text": f"不明なツール: {tool_name}"}], "isError": True}

    else:
        result = None

    if req_id is not None and result is not None:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}
    return None


for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        req = json.loads(line)
        response = handle_request(req)
        if response:
            sys.stdout.write(json.dumps(response) + '\n')
            sys.stdout.flush()
    except Exception as e:
        try:
            req_id = json.loads(line).get('id')
        except Exception:
            req_id = None
        if req_id is not None:
            err = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": str(e)}}
            sys.stdout.write(json.dumps(err) + '\n')
            sys.stdout.flush()
