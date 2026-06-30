#!/usr/bin/env python3
"""Z.AI Video Generation MCP Server - 公式 CogVideoX-3 REST API を直接呼び出すMCPサーバー
用途: 短い動画の生成（テキスト→動画）。GLM_API_KEY（Z.AI APIキー）を流用。
第三者npmパッケージは使わず、公式RESTエンドポイントをurllibで直接叩くシンプルな実装。
"""

import json
import sys
import os
import urllib.request
import urllib.error

SECRETS_PATH = os.path.expanduser('~/.secrets.env')


def _load_env_value(key):
    if not os.path.exists(SECRETS_PATH):
        return ''
    with open(SECRETS_PATH, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('export '):
                line = line[len('export '):]
            if line.startswith(key + '='):
                return line.split('=', 1)[1].strip().strip('"').strip("'")
    return ''


API_KEY = _load_env_value('GLM_API_KEY') or os.environ.get('GLM_API_KEY', '')
BASE_URL = 'https://api.z.ai/api/paas/v4'
GENERATE_URL = f'{BASE_URL}/videos/generations'
RESULT_URL = f'{BASE_URL}/async-result/{{id}}'
MODEL = 'cogvideox-3'


def _request(url, method='GET', body=None):
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json',
    }
    data = json.dumps(body).encode('utf-8') if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as res:
            return json.loads(res.read())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8', errors='ignore')
        return {'error': f'HTTP {e.code}: {err_body}'}
    except Exception as e:
        return {'error': str(e)}


def submit_video_task(prompt, size=None, duration=None, fps=None, with_audio=None):
    body = {'model': MODEL, 'prompt': prompt}
    if size:
        body['size'] = size
    if duration:
        body['duration'] = duration
    if fps:
        body['fps'] = fps
    if with_audio is not None:
        body['with_audio'] = with_audio
    return _request(GENERATE_URL, method='POST', body=body)


def query_video_task(task_id):
    return _request(RESULT_URL.format(id=task_id), method='GET')


TOOLS = [
    {
        "name": "zai_generate_video",
        "description": "Z.AI公式CogVideoX-3モデルでテキストから短い動画を生成する。非同期タスクとして送信し、task_idを返す。完了確認には zai_query_video を使う。コストが発生するため、ユーザーが明示的に依頼した場合のみ使用すること。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "動画生成のプロンプト（英語推奨）"},
                "size": {"type": "string", "description": "解像度。例: 1280x720, 1920x1080, 3840x2160（省略可）"},
                "duration": {"type": "integer", "description": "動画の長さ（秒）。5 または 10。デフォルト5"},
                "fps": {"type": "integer", "description": "フレームレート。30 または 60。デフォルト30"},
                "with_audio": {"type": "boolean", "description": "音声を含めるか（省略可）"}
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "zai_query_video",
        "description": "zai_generate_videoで送信した動画生成タスクの状態を確認し、完了していれば動画URLを取得する。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "zai_generate_videoが返したタスクID（id）"}
            },
            "required": ["task_id"]
        }
    }
]


def handle_request(req):
    method = req.get('method')
    req_id = req.get('id')

    if method == 'initialize':
        result = {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "zai-video-mcp", "version": "1.0.0"}
        }
    elif method == 'notifications/initialized':
        return None
    elif method == 'tools/list':
        result = {"tools": TOOLS}
    elif method == 'tools/call':
        params = req.get('params', {})
        tool_name = params.get('name')
        args = params.get('arguments', {})

        if not API_KEY:
            return {"jsonrpc": "2.0", "id": req_id,
                    "result": {"content": [{"type": "text", "text": "GLM_API_KEY が見つかりません（~/.secrets.env を確認してください）"}], "isError": True}}

        if tool_name == 'zai_generate_video':
            prompt = args.get('prompt', '')
            res = submit_video_task(
                prompt,
                size=args.get('size'),
                duration=args.get('duration'),
                fps=args.get('fps'),
                with_audio=args.get('with_audio'),
            )
            if 'error' in res:
                result = {"content": [{"type": "text", "text": f"動画生成リクエストに失敗しました: {res['error']}"}], "isError": True}
            else:
                task_id = res.get('id', '')
                status = res.get('task_status', '')
                result = {"content": [{"type": "text", "text": f"動画生成タスクを送信しました。Task ID: {task_id} / status: {status}\nzai_query_video で完了を確認してください。"}]}

        elif tool_name == 'zai_query_video':
            task_id = args.get('task_id', '')
            res = query_video_task(task_id)
            if 'error' in res:
                result = {"content": [{"type": "text", "text": f"状態確認に失敗しました: {res['error']}"}], "isError": True}
            else:
                status = res.get('task_status', '')
                if status == 'SUCCESS':
                    videos = res.get('video_result', [])
                    urls = '\n'.join(f"- {v.get('url')}" for v in videos)
                    result = {"content": [{"type": "text", "text": f"動画生成が完了しました。\n{urls}"}]}
                elif status == 'FAIL':
                    result = {"content": [{"type": "text", "text": f"動画生成に失敗しました: {json.dumps(res, ensure_ascii=False)}"}], "isError": True}
                else:
                    result = {"content": [{"type": "text", "text": f"処理中です（status: {status}）。しばらく待ってから再度確認してください。"}]}
        else:
            result = {"content": [{"type": "text", "text": f"不明なツール: {tool_name}"}], "isError": True}
    else:
        return None

    if req_id is not None:
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
