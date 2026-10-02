#!/usr/bin/env python3
"""Stands in for both the `codex` and the `claude` command in the foundry tests: no AI is ever started.

FAKE_FAIL=<text>   print the text and exit 1
FAKE_COPY=<file>   copy it to the file the job is expected to write ($FOUNDRY_EXPECTS); a checker writes no findings
FAKE_REPORT=<json> the worker's final report
FAKE_ARGV=<file>   save the command line there
FAKE_UTILIZATION   the fraction of the week a Claude worker reports as used
"""
import json
import os
import shutil
import sys

args = sys.argv[1:]
if "app-server" in args:
    sys.exit(0)
if os.environ.get("FAKE_ARGV"):
    open(os.environ["FAKE_ARGV"], "w").write(json.dumps(args))
if os.environ.get("FAKE_FAIL"):
    print(os.environ["FAKE_FAIL"])
    sys.exit(1)
expects = os.environ.get("FOUNDRY_EXPECTS")
if expects and expects.endswith("check.json"):
    os.makedirs(os.path.dirname(expects), exist_ok=True)
    open(expects, "w").write('{"findings": []}')
elif expects and os.environ.get("FAKE_COPY"):
    os.makedirs(os.path.dirname(expects), exist_ok=True)
    shutil.copy(os.environ["FAKE_COPY"], expects)
report = json.loads(os.environ.get("FAKE_REPORT", '{"done": true}'))
if "exec" in args:  # codex: the report goes into the file named after -o
    open(args[args.index("-o") + 1], "w").write(json.dumps(report))
else:  # claude: a stream of JSON events on stdout
    print(json.dumps({"type": "rate_limit_event", "rate_limit_info": {
        "status": "allowed_warning", "rateLimitType": "seven_day",
        "utilization": float(os.environ.get("FAKE_UTILIZATION", "0.5")), "resetsAt": 4102444800}}))
    print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "total_cost_usd": 0.5,
                      "structured_output": report, "result": json.dumps(report)}))
