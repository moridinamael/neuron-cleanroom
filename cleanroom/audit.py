"""Leak audit of a blind run: every tool call, any that reach outside the room, and every denied call.

  python -m cleanroom.audit --run runs/<run>      ->  <run>/audit.json  (exit 1 if anything is flagged)

A call is flagged when its input names a path outside the room (an absolute path, ~, or a parent
directory), the interp repo, Claude's memory or transcripts, or when it is a web tool. Sub-agent
calls are included (stream-json carries them with a parent_tool_use_id).
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

WEB = {"WebFetch", "WebSearch"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    a = ap.parse_args()
    run = Path(a.run)
    man = json.loads((run / "manifest.json").read_text(encoding="utf-8")) if (run / "manifest.json").exists() else {}
    room = Path(man.get("room", ".")).resolve().as_posix().lower()
    room_name = Path(room).name
    outside = re.compile(r"(?i)(?<![\w.])(?:[a-z]:[/\\]|/c/|/home/|/users/|~[/\\]|\.\.[/\\])[^\s\"'`]*")
    named = re.compile(r"(?i)bonsai-interp|monosemanticity|\.claude[/\\]projects|FINDINGS\.md|graph[/\\]neurons")
    calls, results, denied = {}, {}, set()
    for line in (run / "transcript.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        content = (ev.get("message") or {}).get("content")
        for c in content if isinstance(content, list) else []:
            if c.get("type") == "tool_use":
                calls[c["id"]] = {"tool": c["name"], "input": json.dumps(c["input"], ensure_ascii=False),
                                  "sub_agent": ev.get("parent_tool_use_id") is not None}
            elif c.get("type") == "tool_result":
                txt = c.get("content")
                txt = txt if isinstance(txt, str) else json.dumps(txt, ensure_ascii=False)
                results[c["tool_use_id"]] = txt
                if re.search(r"(?i)permission.{0,40}(denied|blocked)|denied by|not allowed", txt):
                    denied.add(c["tool_use_id"])
    flagged = []
    for i, c in calls.items():
        raw = c["input"].replace("\\\\", "/").replace("\\n", " ")
        paths = [p for p in outside.findall(raw) if room_name not in p.lower() and room not in p.lower()]
        why = ([f"path outside the room: {paths[:3]}"] if paths else []) + \
              ([f"names {named.findall(raw)[:3]}"] if named.search(raw) else []) + (["web tool"] if c["tool"] in WEB else [])
        if why:
            flagged.append({"tool": c["tool"], "sub_agent": c["sub_agent"], "why": why, "denied": i in denied,
                            "input": c["input"][:400], "result_head": results.get(i, "")[:300]})
    out = {"tool_calls": len(calls), "by_tool": dict(Counter(c["tool"] for c in calls.values())),
           "sub_agent_calls": sum(c["sub_agent"] for c in calls.values()), "denied_calls": len(denied),
           "flagged": flagged,
           "denied": [{"tool": calls[i]["tool"], "input": calls[i]["input"][:300]} for i in denied if i in calls]}
    (run / "audit.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{out['tool_calls']} tool calls {out['by_tool']}; sub-agent calls {out['sub_agent_calls']}; "
          f"denied {out['denied_calls']}; flagged {len(flagged)}")
    for f in flagged:
        print(f"  FLAG {f['tool']} denied={f['denied']} {f['why']}: {f['input'][:160]}")
    sys.exit(1 if flagged else 0)


if __name__ == "__main__":
    main()
