#!/usr/bin/env python3
import datetime as dt
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path


CONFIG_PATH = Path.home() / ".claude" / "fallback-config.json"


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def classify_error(text: str, cfg: dict) -> str:
    body = (text or "").lower()
    do_not = cfg["fallback"]["do_not_fallback_on"]
    fallback_on = cfg["fallback"]["fallback_on"]

    for code in do_not["http_status_codes"]:
        if re.search(rf"\b{code}\b", body):
            return "non_retryable_http"
    for kw in do_not["error_keywords"]:
        if kw in body:
            return "non_retryable_keyword"

    for code in fallback_on["http_status_codes"]:
        if re.search(rf"\b{code}\b", body):
            return "retryable_http"
    for kw in fallback_on["error_keywords"]:
        if kw in body:
            return "retryable_keyword"

    return "unknown"


def run_claude(args: list[str], env: dict) -> tuple[int, str, str, float]:
    started = time.time()
    proc = subprocess.run(
        ["claude", *args],
        capture_output=True,
        text=True,
        env=env,
    )
    elapsed_ms = round((time.time() - started) * 1000, 2)
    return proc.returncode, proc.stdout or "", proc.stderr or "", elapsed_ms


def print_output(stdout: str, stderr: str) -> None:
    if stdout:
        sys.stdout.write(stdout)
    if stderr:
        sys.stderr.write(stderr)


def write_log(config: dict, payload: dict) -> None:
    log_dir = Path(config["logging"]["dir"])
    log_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{config['logging']['file_prefix']}-{dt.date.today().isoformat()}.jsonl"
    out = log_dir / filename
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def make_secondary_env(config: dict, base_env: dict) -> dict:
    env = dict(base_env)
    minimax_cfg = config["minimax"]
    key_name = minimax_cfg["env_api_key_name"]
    key_value = base_env.get(key_name) or os.environ.get(key_name)
    if not key_value:
        raise RuntimeError(f"{key_name} is not set. Cannot fallback to MiniMax.")

    env["ANTHROPIC_BASE_URL"] = minimax_cfg["base_url"]
    env["ANTHROPIC_AUTH_TOKEN"] = key_value
    env["ANTHROPIC_DEFAULT_OPUS_MODEL"] = minimax_cfg["model_map"]["opus"]
    env["ANTHROPIC_DEFAULT_SONNET_MODEL"] = minimax_cfg["model_map"]["sonnet"]
    env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = minimax_cfg["model_map"]["haiku"]
    return env


def main() -> int:
    args = sys.argv[1:]
    simulate_primary_failure = False
    if "--simulate-primary-failure" in args:
        args = [a for a in args if a != "--simulate-primary-failure"]
        simulate_primary_failure = True
    if not args:
        print("Usage: claude-fallback <claude args...>", file=sys.stderr)
        return 2

    config = load_config()
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    command_str = "claude " + " ".join(shlex.quote(a) for a in args)
    base_env = dict(os.environ)

    retries = int(config["fallback"]["retry"]["primary_retries"])
    delay_s = float(config["fallback"]["retry"]["primary_retry_delay_seconds"])

    first_error = ""
    first_class = "none"
    primary_attempts = retries + 1

    for i in range(primary_attempts):
        if simulate_primary_failure:
            code = 1
            out = ""
            err = "simulated primary failure: timeout"
            elapsed_ms = 0.01
        else:
            code, out, err, elapsed_ms = run_claude(args, base_env)
        combined = f"{out}\n{err}"
        error_class = classify_error(combined, config)

        write_log(
            config,
            {
                "ts": now,
                "provider": "glm",
                "attempt": i + 1,
                "latency_ms": elapsed_ms,
                "exit_code": code,
                "error_class": error_class,
                "fallback_triggered": False,
                "command": command_str,
            },
        )

        if code == 0:
            print_output(out, err)
            return 0

        first_error = combined
        first_class = error_class
        if simulate_primary_failure:
            break
        if i < retries:
            time.sleep(delay_s)

    if first_class not in {"retryable_http", "retryable_keyword", "unknown"}:
        print_output("", first_error)
        return 1

    try:
        env2 = make_secondary_env(config, base_env)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        print_output("", first_error)
        return 1

    code2, out2, err2, elapsed_ms2 = run_claude(args, env2)
    write_log(
        config,
        {
            "ts": now,
            "provider": "minimax",
            "attempt": 1,
            "latency_ms": elapsed_ms2,
            "exit_code": code2,
            "error_class": classify_error(f"{out2}\n{err2}", config),
            "fallback_triggered": True,
            "command": command_str,
        },
    )
    print_output(out2, err2)
    return code2


if __name__ == "__main__":
    raise SystemExit(main())
