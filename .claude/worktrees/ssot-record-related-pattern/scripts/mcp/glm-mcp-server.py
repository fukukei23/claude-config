#!/usr/bin/env python3
"""GLM-5.1 MCP Server - Z.AI / GLM-5.1をMCPツールとして提供
用途: コード生成・GitHub操作・Obsidian更新・ドキュメント生成など"""

import json
import sys
import os
import urllib.request

def _load_key():
    key = os.environ.get('GLM_API_KEY', '')
    if key:
        return key
    secrets = os.path.expanduser('~/.secrets.env')
    if os.path.exists(secrets):
        with open(secrets) as f:
            for line in f:
                line = line.strip()
                if line.startswith('export GLM_API_KEY='):
                    return line.split('=', 1)[1].strip().strip('"').strip("'")
    return ''

GLM_KEY = _load_key()
GLM_URL = 'https://api.z.ai/api/anthropic/v1/messages'
MODEL = 'GLM-5.1'


def call_glm(prompt, max_tokens=4000):
    # ステータスファイルに記録（ステータスライン表示用）
    try:
        with open('/tmp/llm-last-used.txt', 'w') as f:
            f.write('🟡 GLM-5.1')
    except Exception:
        pass
    if not GLM_KEY:
        return 'Error: GLM_API_KEY が設定されていません'
    data = json.dumps({
        'model': MODEL,
        'max_tokens': max_tokens,
        'messages': [{'role': 'user', 'content': prompt}]
    }).encode('utf-8')
    req = urllib.request.Request(
        GLM_URL, data=data,
        headers={
            'x-api-key': GLM_KEY,
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
        "name": "glm_ask",
        "description": "GLM-5.1に汎用的な作業を依頼する。コード生成・ドキュメント作成・分析など。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "GLMへの指示とコンテンツ"},
                "max_tokens": {"type": "integer", "description": "最大出力トークン数（デフォルト4000）", "default": 4000}
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "glm_generate_code",
        "description": "GLM-5.1でコードを生成する。大量のコード生成・定型コード・ボイラープレートに最適。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "instruction": {"type": "string", "description": "生成するコードの仕様・要件"},
                "language": {"type": "string", "description": "プログラミング言語（例: python, typescript）", "default": "python"},
                "context": {"type": "string", "description": "既存コードや参考情報（省略可）", "default": ""}
            },
            "required": ["instruction"]
        }
    },
    {
        "name": "glm_write_document",
        "description": "GLM-5.1でドキュメント・Markdownを生成する。CLAUDE.md・引き継ぎ文書・Obsidianノート・README・GitHubのPRコメントなどに使用。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "instruction": {"type": "string", "description": "作成するドキュメントの内容・目的"},
                "format": {"type": "string", "description": "フォーマット（markdown / plain / json）", "default": "markdown"},
                "context": {"type": "string", "description": "参考情報・既存内容（省略可）", "default": ""}
            },
            "required": ["instruction"]
        }
    },
    {
        "name": "glm_git_commit_message",
        "description": "GLM-5.1でgitコミットメッセージを生成する。Conventional Commits形式で出力。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "diff_or_description": {"type": "string", "description": "git diffの内容または変更内容の説明"}
            },
            "required": ["diff_or_description"]
        }
    },
    {
        "name": "glm_analyze_file",
        "description": "ファイルをGLM-5.1で分析・処理する。ログ解析・コスト計算・コードレビューに使用。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "処理するファイルのパス（絶対パス）"},
                "instruction": {"type": "string", "description": "分析・処理の指示"}
            },
            "required": ["file_path", "instruction"]
        }
    },
    {
        "name": "glm_review_code",
        "description": "GLM-5.1でコードレビューを行う。バグ検出・セキュリティ問題・改善点を指摘。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "レビュー対象ファイルのパス（絶対パス）"},
                "focus": {"type": "string", "description": "重点項目（例: security, performance, readability）。省略で総合レビュー", "default": ""}
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "glm_generate_tests",
        "description": "GLM-5.1でテストコードを生成する。ユニットテスト・統合テストの自動生成に最適。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "テスト対象のソースファイルパス（絶対パス）"},
                "framework": {"type": "string", "description": "テストフレームワーク（例: pytest, jest, vitest）", "default": "pytest"},
                "context": {"type": "string", "description": "追加のコンテキスト・要件（省略可）", "default": ""}
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "glm_explain_code",
        "description": "GLM-5.1でコードを解説する。引き継ぎ資料・学習用メモの作成に使用。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "解説対象ファイルのパス（絶対パス）"},
                "detail_level": {"type": "string", "description": "詳細度（brief / normal / detailed）", "default": "normal"}
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "glm_translate",
        "description": "GLM-5.1でテキストを翻訳する。日⇔英翻訳・README英語化・コメント翻訳に使用。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "翻訳するテキスト"},
                "source_lang": {"type": "string", "description": "元の言語（例: ja, en）", "default": "auto"},
                "target_lang": {"type": "string", "description": "翻訳先の言語（例: en, ja）", "default": "en"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "glm_refactor_suggest",
        "description": "GLM-5.1でリファクタリング提案を出す。改善案の提示のみで適用はしない。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "リファクタリング対象ファイルのパス（絶対パス）"},
                "goal": {"type": "string", "description": "リファクタリングの目標（例: パフォーマンス改善, 可読性向上）。省略で総合提案", "default": ""}
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "glm_debug_error",
        "description": "GLM-5.1でエラーメッセージから原因を推定する。エラーログ・スタックトレースを貼るだけで原因特定。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "error_message": {"type": "string", "description": "エラーメッセージ・スタックトレース"},
                "context": {"type": "string", "description": "周辺コード・環境情報（省略可）", "default": ""},
                "language": {"type": "string", "description": "プログラミング言語（例: python, typescript）", "default": ""}
            },
            "required": ["error_message"]
        }
    },
    {
        "name": "glm_security_audit",
        "description": "GLM-5.1でOWASP Top 10中心のセキュリティ監査を行う。SQLインジェクション・XSS・CSRF・認証不備等の脆弱性を検出。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "監査対象ファイルのパス（絶対パス）"},
                "framework": {"type": "string", "description": "Webフレームワーク（例: django, express, flask）。省略で自動判定", "default": ""}
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "glm_write_readme",
        "description": "GLM-5.1でコードからREADME.mdを自動生成する。プロジェクト構成・使い方・インストール手順を含む。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_dir": {"type": "string", "description": "プロジェクトディレクトリのパス（絶対パス）"},
                "language": {"type": "string", "description": "README言語（ja / en）。デフォルトja", "default": "ja"}
            },
            "required": ["project_dir"]
        }
    },
    {
        "name": "glm_generate_docs",
        "description": "GLM-5.1でdocstring・JSDoc・型コメント等のドキュメントを生成する。ドキュメント無しコードへのコメント付与に最適。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "ドキュメント生成対象ファイルのパス（絶対パス）"},
                "style": {"type": "string", "description": "docstyle（例: google, numpy, jsdoc, tsdoc）。省略で自動判定", "default": ""}
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "glm_generate_changelog",
        "description": "GLM-5.1でgit履歴からCHANGELOG.mdを生成する。バージョン別の変更履歴・リリースノート作成に使用。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "git_log": {"type": "string", "description": "git log --oneline の出力内容"},
                "version": {"type": "string", "description": "バージョンタグ（例: v2.0.0）", "default": ""}
            },
            "required": ["git_log"]
        }
    },
    {
        "name": "glm_design_api",
        "description": "GLM-5.1でOpenAPI/Routes設計書を生成する。REST APIのエンドポイント・リクエスト・レスポンス定義を出力。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "APIの要件・仕様の説明"},
                "format": {"type": "string", "description": "出力形式（openapi / markdown / typescript）。デフォルトopenapi", "default": "openapi"}
            },
            "required": ["description"]
        }
    },
    {
        "name": "glm_optimize_sql",
        "description": "GLM-5.1でSQLクエリの最適化を提案する。N+1問題検出・インデックス提案・EXPLAIN結果の分析に使用。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "SQLクエリまたはDDL"},
                "dialect": {"type": "string", "description": "データベース種類（mysql / postgresql / sqlite）。省略で汎用", "default": ""},
                "schema": {"type": "string", "description": "テーブル定義・スキーマ情報（省略可）", "default": ""}
            },
            "required": ["sql"]
        }
    },
    {
        "name": "glm_generate_regex",
        "description": "GLM-5.1で正規表現を生成・解説する。自然言語の説明から正規表現を作成。正規表現の可読性解説も可能。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "マッチさせたいパターンの自然言語説明。または解説したい正規表現"},
                "mode": {"type": "string", "description": "generate（生成） / explain（解説）。デフォルトgenerate", "default": "generate"},
                "language": {"type": "string", "description": "対象言語（python / javascript / go）。省略で汎用", "default": ""}
            },
            "required": ["description"]
        }
    },
    {
        "name": "glm_write_dockerfile",
        "description": "GLM-5.1でDockerfile・docker-compose.ymlを生成する。プロジェクト構成を読んで最適なコンテナ設定・マルチステージビルドを出力。ClaudeのAPIトークンを消費しない。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_dir": {"type": "string", "description": "プロジェクトディレクトリのパス（絶対パス）"},
                "target": {"type": "string", "description": "生成対象（dockerfile / compose / both）。デフォルトboth", "default": "both"},
                "base_image": {"type": "string", "description": "ベースイメージ指定（例: python:3.12, node:20）。省略で自動判定", "default": ""}
            },
            "required": ["project_dir"]
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
            "serverInfo": {"name": "glm-mcp", "version": "1.0.0"}
        }

    elif method in ('notifications/initialized', 'initialized'):
        return None

    elif method == 'tools/list':
        result = {"tools": TOOLS}

    elif method == 'tools/call':
        tool_name = params.get('name')
        args = params.get('arguments', {})

        if tool_name == 'glm_ask':
            text = call_glm(args['prompt'], args.get('max_tokens', 4000))
            result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'glm_generate_code':
            lang = args.get('language', 'python')
            ctx = args.get('context', '')
            ctx_section = f"\n\n参考コード・コンテキスト:\n{ctx}" if ctx else ""
            prompt = f"言語: {lang}\n\n要件:\n{args['instruction']}{ctx_section}\n\nコードのみ出力。説明は最小限に。"
            text = call_glm(prompt, 6000)
            result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'glm_write_document':
            fmt = args.get('format', 'markdown')
            ctx = args.get('context', '')
            ctx_section = f"\n\n参考情報:\n{ctx}" if ctx else ""
            prompt = f"フォーマット: {fmt}\n\n作成内容:\n{args['instruction']}{ctx_section}"
            text = call_glm(prompt, 4000)
            result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'glm_git_commit_message':
            prompt = f"""以下の変更内容に対してConventional Commits形式のコミットメッセージを生成してください。
形式: type: 説明（日本語）
typeの例: feat, fix, docs, refactor, chore, test

変更内容:
{args['diff_or_description']}

コミットメッセージのみ出力してください。"""
            text = call_glm(prompt, 200)
            result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'glm_analyze_file':
            fp = args['file_path']
            if not os.path.exists(fp):
                result = {"content": [{"type": "text", "text": f"ファイルが見つかりません: {fp}"}], "isError": True}
            else:
                with open(fp, encoding='utf-8', errors='ignore') as f:
                    content = f.read()[:10000]
                prompt = f"{args['instruction']}\n\nファイル: {os.path.basename(fp)}\n---\n{content}"
                text = call_glm(prompt, 4000)
                result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'glm_review_code':
            fp = args['file_path']
            if not os.path.exists(fp):
                result = {"content": [{"type": "text", "text": f"ファイルが見つかりません: {fp}"}], "isError": True}
            else:
                with open(fp, encoding='utf-8', errors='ignore') as f:
                    content = f.read()[:10000]
                focus = args.get('focus', '')
                focus_section = f"\n重点項目: {focus}" if focus else "\n総合レビュー（バグ・セキュリティ・パフォーマンス・可読性）"
                prompt = f"以下のコードをレビューしてください。問題があれば深刻度（高/中/低）付きで指摘し、改善案を提示してください。{focus_section}\n\nファイル: {os.path.basename(fp)}\n---\n{content}"
                text = call_glm(prompt, 4000)
                result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'glm_generate_tests':
            fp = args['file_path']
            if not os.path.exists(fp):
                result = {"content": [{"type": "text", "text": f"ファイルが見つかりません: {fp}"}], "isError": True}
            else:
                with open(fp, encoding='utf-8', errors='ignore') as f:
                    content = f.read()[:8000]
                fw = args.get('framework', 'pytest')
                ctx = args.get('context', '')
                ctx_section = f"\n追加要件: {ctx}" if ctx else ""
                prompt = f"テストフレームワーク: {fw}\n\n以下のソースコードに対するテストコードを生成してください。正常系・異常系・エッジケースを網羅すること。{ctx_section}\n\nファイル: {os.path.basename(fp)}\n---\n{content}\n\nテストコードのみ出力。"
                text = call_glm(prompt, 6000)
                result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'glm_explain_code':
            fp = args['file_path']
            if not os.path.exists(fp):
                result = {"content": [{"type": "text", "text": f"ファイルが見つかりません: {fp}"}], "isError": True}
            else:
                with open(fp, encoding='utf-8', errors='ignore') as f:
                    content = f.read()[:10000]
                detail = args.get('detail_level', 'normal')
                detail_map = {'brief': '簡潔に（主要な関数・クラスの役割のみ）', 'detailed': '詳細に（行ごとの解説付き）'}
                detail_inst = detail_map.get(detail, '標準的に（関数単位で解説）')
                prompt = f"以下のコードを{detail_inst}解説してください。\n\nファイル: {os.path.basename(fp)}\n---\n{content}"
                text = call_glm(prompt, 4000)
                result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'glm_translate':
            src = args.get('source_lang', 'auto')
            tgt = args.get('target_lang', 'en')
            src_section = f"（{src} → {tgt}）" if src != 'auto' else f"（→ {tgt}）"
            prompt = f"以下のテキストを翻訳してください{src_section}。翻訳結果のみ出力。\n\n{args['text']}"
            text = call_glm(prompt, 4000)
            result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'glm_refactor_suggest':
            fp = args['file_path']
            if not os.path.exists(fp):
                result = {"content": [{"type": "text", "text": f"ファイルが見つかりません: {fp}"}], "isError": True}
            else:
                with open(fp, encoding='utf-8', errors='ignore') as f:
                    content = f.read()[:10000]
                goal = args.get('goal', '')
                goal_section = f"\n目標: {goal}" if goal else ""
                prompt = f"以下のコードのリファクタリング提案をしてください。改善点・理由・リファクタリング後のコード例を提示。{goal_section}\n\nファイル: {os.path.basename(fp)}\n---\n{content}"
                text = call_glm(prompt, 6000)
                result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'glm_debug_error':
            err_msg = args['error_message']
            ctx = args.get('context', '')
            lang = args.get('language', '')
            ctx_section = f"\n\n周辺コード・環境情報:\n{ctx}" if ctx else ""
            lang_section = f"\n言語: {lang}" if lang else ""
            prompt = f"以下のエラーの原因を特定し、解決策を提案してください。{lang_section}\n\nエラー:\n{err_msg}{ctx_section}\n\n考えられる原因と修正方法を出力。"
            text = call_glm(prompt, 4000)
            result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'glm_security_audit':
            fp = args['file_path']
            if not os.path.exists(fp):
                result = {"content": [{"type": "text", "text": f"ファイルが見つかりません: {fp}"}], "isError": True}
            else:
                with open(fp, encoding='utf-8', errors='ignore') as f:
                    content = f.read()[:10000]
                fw = args.get('framework', '')
                fw_section = f"\nフレームワーク: {fw}" if fw else ""
                prompt = f"以下のコードをOWASP Top 10の観点でセキュリティ監査してください。SQLインジェクション、XSS、CSRF、認証・認可の不備、機密情報の漏洩等を検出し、深刻度（高/中/低）と修正方法を提示してください。{fw_section}\n\nファイル: {os.path.basename(fp)}\n---\n{content}"
                text = call_glm(prompt, 4000)
                result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'glm_write_readme':
            pdir = args['project_dir']
            if not os.path.exists(pdir):
                result = {"content": [{"type": "text", "text": f"ディレクトリが見つかりません: {pdir}"}], "isError": True}
            else:
                import subprocess
                files = subprocess.run(['find', pdir, '-maxdepth', '2', '-type', 'f', '-not', '-path', '*/node_modules/*', '-not', '-path', '*/.git/*', '-not', '-path', '*/__pycache__/*'], capture_output=True, text=True, timeout=10).stdout[:4000]
                lang = args.get('language', 'ja')
                prompt = f"以下のプロジェクト構成からREADME.mdを生成してください。言語: {lang}\n含める内容: プロジェクト名、概要、機能一覧、インストール手順、使い方、設定、ライセンス。\n\nプロジェクト構成:\n{files}"
                text = call_glm(prompt, 4000)
                result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'glm_generate_docs':
            fp = args['file_path']
            if not os.path.exists(fp):
                result = {"content": [{"type": "text", "text": f"ファイルが見つかりません: {fp}"}], "isError": True}
            else:
                with open(fp, encoding='utf-8', errors='ignore') as f:
                    content = f.read()[:10000]
                style = args.get('style', '')
                style_section = f"\nドキュメントスタイル: {style}" if style else ""
                prompt = f"以下のコードにドキュメントコメント（docstring/JSDoc等）を追加してください。関数・クラスの説明、引数、戻り値、例外を記述。既存コードは変更せずコメントのみ追加。{style_section}\n\nファイル: {os.path.basename(fp)}\n---\n{content}"
                text = call_glm(prompt, 6000)
                result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'glm_generate_changelog':
            git_log = args['git_log']
            version = args.get('version', '')
            ver_section = f"\nバージョン: {version}" if version else ""
            prompt = f"以下のgitコミット履歴からCHANGELOG.mdを生成してください。カテゴリ別（Added/Changed/Fixed/Removed）に整理し、各エントリは簡潔に。{ver_section}\n\nコミット履歴:\n{git_log[:8000]}"
            text = call_glm(prompt, 4000)
            result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'glm_design_api':
            desc = args['description']
            fmt = args.get('format', 'openapi')
            prompt = f"以下の要件からREST APIの設計書を{fmt}形式で生成してください。エンドポイント、HTTPメソッド、リクエスト/レスポンスのスキーマ、ステータスコードを含める。\n\n要件:\n{desc}"
            text = call_glm(prompt, 6000)
            result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'glm_optimize_sql':
            sql = args['sql']
            dialect = args.get('dialect', '')
            schema = args.get('schema', '')
            dialect_section = f"\nDB: {dialect}" if dialect else ""
            schema_section = f"\n\nテーブル定義:\n{schema}" if schema else ""
            prompt = f"以下のSQLクエリを最適化してください。N+1問題の検出、インデックス提案、クエリの書き直しを含める。{dialect_section}\n\nSQL:\n{sql}{schema_section}\n\n最適化後のSQLと、変更理由を出力。"
            text = call_glm(prompt, 4000)
            result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'glm_generate_regex':
            desc = args['description']
            mode = args.get('mode', 'generate')
            lang = args.get('language', '')
            lang_section = f"\n言語: {lang}" if lang else ""
            if mode == 'explain':
                prompt = f"以下の正規表現を詳細に解説してください。各部分が何にマッチするかを説明。{lang_section}\n\n正規表現: {desc}"
            else:
                prompt = f"以下の要件を満たす正規表現を生成してください。{lang_section}\n\n要件: {desc}\n\n正規表現と、テストケース（マッチ例・非マッチ例）を出力。"
            text = call_glm(prompt, 2000)
            result = {"content": [{"type": "text", "text": text}]}

        elif tool_name == 'glm_write_dockerfile':
            pdir = args['project_dir']
            if not os.path.exists(pdir):
                result = {"content": [{"type": "text", "text": f"ディレクトリが見つかりません: {pdir}"}], "isError": True}
            else:
                import subprocess
                files = subprocess.run(['find', pdir, '-maxdepth', '2', '-type', 'f', '-not', '-path', '*/node_modules/*', '-not', '-path', '*/.git/*', '-not', '-path', '*/__pycache__/*'], capture_output=True, text=True, timeout=10).stdout[:4000]
                target = args.get('target', 'both')
                base = args.get('base_image', '')
                base_section = f"\nベースイメージ: {base}" if base else ""
                target_section = f"\n生成対象: {target}"
                prompt = f"以下のプロジェクト構成から最適なDocker設定を生成してください。{target_section}{base_section}\nマルチステージビルドを検討し、セキュリティベストプラクティスに従うこと。\n\nプロジェクト構成:\n{files}"
                text = call_glm(prompt, 4000)
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
