#!/usr/bin/env python3
"""Offline stand-in for Codex exec's documented JSONL protocol; never contacts a provider."""
import json
import os
from pathlib import Path
import sys
import time


args = sys.argv[1:]
configs = [args[i + 1] for i, value in enumerate(args[:-1]) if value in ("-c", "--config")]
instruction = next((s.split("=", 1)[1] for s in configs if s.startswith("model_instructions_file=")), None)
schema = json.loads(Path(args[args.index("--output-schema") + 1]).read_text()) if "--output-schema" in args else None
prompt = sys.stdin.read()
record = {"args": args, "cwd": os.getcwd(), "prompt": json.loads(prompt), "schema": schema,
          "instructions": Path(json.loads(instruction)).read_text() if instruction else "",
          "api_key_present": any(os.environ.get(k) for k in ("OPENAI_API_KEY", "CODEX_API_KEY")), "pid": os.getpid()}
with open(os.environ["FAKE_CODEX_LOG"], "a") as log:
    log.write(json.dumps(record) + "\n")


def emit(event):
    print(json.dumps(event), flush=True)


mode = os.environ.get("FAKE_CODEX_MODE", "ok")
emit({"type": "thread.started", "thread_id": "fake-thread"})
emit({"type": "turn.started"})
if mode in ("login", "limit"):
    message = "Not logged in; authenticate using codex login" if mode == "login" else "Usage limit reached"
    emit({"type": "turn.failed", "error": {"message": message}})
    sys.exit(1)
if mode == "unreadable":
    print("not JSON", flush=True)
    sys.exit(1)
emit({"type": "item.completed", "item": {"id": "reason", "type": "reasoning", "text": "private reasoning"}})
emit({"type": "item.completed", "item": {"id": "comment", "type": "agent_message", "phase": "commentary",
                                           "text": "I will inspect files."}})
reply = os.environ.get("FAKE_CODEX_REPLY", '{"feedback":"Good.","speech":"Spoken feedback."}' if schema else
                       "A useful hint.\n[[SPEECH]] A useful hint.")
emit({"type": "item.completed", "item": {"id": "answer", "type": "agent_message", "text": reply}})
if mode == "wait":
    time.sleep(30)
if mode != "unfinished":
    emit({"type": "turn.completed", "usage": {"input_tokens": 35, "cached_input_tokens": 20,
                                                "output_tokens": 12, "reasoning_output_tokens": 4}})
