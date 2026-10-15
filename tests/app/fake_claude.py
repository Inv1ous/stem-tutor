#!/usr/bin/env python3
"""Stand-in for `claude -p` in tests. FAKE_CLAUDE_MODE: ok | login | limit | leak | speech | speech_fence |
speech_empty. Logs argv to FAKE_CLAUDE_LOG."""
import json, os, sys

mode = os.environ.get("FAKE_CLAUDE_MODE", "ok")
if os.environ.get("FAKE_CLAUDE_LOG"):
    with open(os.environ["FAKE_CLAUDE_LOG"], "a") as f:
        f.write(json.dumps(sys.argv[1:]) + "\n")
usage = {"input_tokens": 12, "cache_read_input_tokens": 300, "cache_creation_input_tokens": 0, "output_tokens": 20}

def out(d):
    sys.stdout.write(json.dumps(d) + "\n"); sys.stdout.flush()

if "stream-json" not in sys.argv:  # one-shot
    prompt = sys.stdin.read()
    if mode == "login":
        out({"type": "result", "is_error": True, "result": "Failed to authenticate: OAuth session expired"}); sys.exit(1)
    data = {"points": [{"point": "p", "met": True, "why": "present"}], "feedback": "Good."}
    if "learner profile" in prompt:
        data = {"summary": "- Going well: you study most days.\n- One change: check units before answering."}
    if "teaching card" in prompt:
        data = {"motivate": "Why.", "establish": "Idea $x^2$.", "connect": "Builds on A.", "note": "- n1\n- n2",
                "self_explain": "Explain it?"}
    if "--json-schema" in sys.argv and "speech" in json.loads(sys.argv[sys.argv.index("--json-schema") + 1]).get("properties", {}):
        data["speech"] = "Spoken feedback: x squared."
    out({"type": "result", "is_error": False, "result": "ok", "structured_output": data, "usage": usage}); sys.exit(0)

out({"type": "system", "subtype": "init", "tools": [], "model": "claude-haiku"})
turn = 0
for line in sys.stdin:
    msg = json.loads(line)
    turn += 1
    text = msg["message"]["content"]
    if mode == "login":
        out({"type": "result", "is_error": True, "result": "Failed to authenticate: OAuth session expired and could not be refreshed"}); continue
    if mode == "limit":
        out({"type": "result", "is_error": True, "result": "You've hit your session limit · resets 10:30pm (Asia/Hong_Kong)"}); continue
    reply = "The answer is B, obviously." if mode == "leak" else f"Reply {turn}: " + text.splitlines()[-1][:40]
    if mode == "speech":
        reply = f"Reply {turn}: use $x^2$ here.\n[[SPEECH]] Reply {turn}: use x squared here."
    elif mode == "speech_fence":
        reply = f"Reply {turn}: see below.\n```\n[[SPEECH]] Reply {turn}, said aloud.\n```"
    elif mode == "speech_empty":
        reply = f"Reply {turn}: nothing to say aloud.\n[[SPEECH]]"
    cut = reply.find("[[SPEECH]]")
    pieces = [reply[:cut + 5], reply[cut + 5:]] if cut >= 0 else [reply[i:i + 7] for i in range(0, len(reply), 7)]
    for piece in pieces:  # with a marker: split inside it, "[[SPE" / "ECH]] …", as a real stream can
        out({"type": "stream_event", "event": {"type": "content_block_delta", "index": 0,
                                               "delta": {"type": "text_delta", "text": piece}}})
    out({"type": "assistant", "message": {"content": [{"type": "text", "text": reply}]}})
    out({"type": "result", "subtype": "success", "is_error": False, "result": reply, "usage": usage})
