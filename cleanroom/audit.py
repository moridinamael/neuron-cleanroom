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


def _strings(x):
    """Every string inside a tool input, decoded (so an escaped \\n in a heredoc is a newline, not a path)."""
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from _strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from _strings(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    a = ap.parse_args()
    run = Path(a.run)
    man = json.loads((run / "manifest.json").read_text(encoding="utf-8")) if (run / "manifest.json").exists() else {}
    room = Path(man.get("room", ".")).resolve().as_posix().lower()
    room_name = Path(room).name
    # a drive path needs a real first segment (C:/Users), so code like "if a:\n" in a test sentence is not a path
    outside = re.compile(r"(?i)(?<![\w.])(?:[a-z]:/[\w.-]{2,}|/c/|/home/|/users/|~/|\.\./)[^\s\"'`]*")
    # repo and folder names only count as part of a path, so the word "monosemanticity" in a report is not a hit
    named = re.compile(r"(?i)[/\\](?:bonsai-interp|monosemanticity)\b|\b(?:bonsai-interp|monosemanticity)[/\\]|\.claude[/\\]projects|FINDINGS\.md|graph[/\\]neurons")
    calls, results, denied = {}, {}, set()
    for line in (run / "transcript.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "item.completed" and isinstance(ev.get("item"), dict):  # Codex `exec --json` events
            it = ev["item"]
            kind = it.get("type", "?")
            if kind in ("command_execution", "file_change", "mcp_tool_call", "web_search"):
                payload = {k: it.get(k) for k in ("command", "changes", "server", "tool", "arguments", "query") if it.get(k) is not None}
                calls[it.get("id", str(len(calls)))] = {"tool": {"web_search": "WebSearch"}.get(kind, kind), "input": json.dumps(payload, ensure_ascii=False),
                                                         "text": " ".join(_strings(payload)), "sub_agent": False}
                out_txt = str(it.get("aggregated_output") or "")
                if re.search(r"(?i)permission.{0,40}(denied|blocked)|access is denied|sandbox", out_txt) and it.get("exit_code"):
                    denied.add(it.get("id", ""))
            continue
        content = (ev.get("message") or {}).get("content")
        for c in content if isinstance(content, list) else []:
            if c.get("type") == "tool_use":
                calls[c["id"]] = {"tool": c["name"], "input": json.dumps(c["input"], ensure_ascii=False),
                                  "text": " ".join(_strings(c["input"])), "sub_agent": ev.get("parent_tool_use_id") is not None}
            elif c.get("type") == "tool_result":
                txt = c.get("content")
                txt = txt if isinstance(txt, str) else json.dumps(txt, ensure_ascii=False)
                results[c["tool_use_id"]] = txt
                if re.search(r"(?i)permission.{0,40}(denied|blocked)|denied by|not allowed", txt):
                    denied.add(c["tool_use_id"])
    # Claude Code gives each session its own scratchpad under .../claude/<project key>/; the key is the room path with
    # every non-alphanumeric character turned into '-'. Using it is not a leak, so it is listed separately.
    key = re.sub(r"[^a-z0-9]", "-", room)
    flagged, scratch = [], []
    for i, c in calls.items():
        raw = c["text"].replace("\\", "/")  # the real argument text (decoded), with Windows separators normalised
        paths = [p for p in outside.findall(raw) if room_name not in p.lower() and room not in p.lower()]
        own = [p for p in paths if f"/claude/{key}/" in p.lower()]
        if own:
            scratch.append({"tool": c["tool"], "paths": own[:3], "input": c["input"][:300]})
            paths = [p for p in paths if p not in own]
        why = ([f"path outside the room: {paths[:3]}"] if paths else []) + \
              ([f"names {named.findall(raw)[:3]}"] if named.search(raw) else []) + (["web tool"] if c["tool"] in WEB else [])
        if why:
            flagged.append({"tool": c["tool"], "sub_agent": c["sub_agent"], "why": why, "denied": i in denied,
                            "input": c["input"][:400], "result_head": results.get(i, "")[:300]})
    out = {"tool_calls": len(calls), "by_tool": dict(Counter(c["tool"] for c in calls.values())),
           "sub_agent_calls": sum(c["sub_agent"] for c in calls.values()), "denied_calls": len(denied),
           "flagged": flagged, "own_scratchpad_uses": scratch,
           "denied": [{"tool": calls[i]["tool"], "input": calls[i]["input"][:300]} for i in denied if i in calls]}
    (run / "audit.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{out['tool_calls']} tool calls {out['by_tool']}; sub-agent calls {out['sub_agent_calls']}; "
          f"denied {out['denied_calls']}; own scratchpad uses {len(scratch)}; flagged {len(flagged)}")
    for f in flagged:
        print(f"  FLAG {f['tool']} denied={f['denied']} {f['why']}: {f['input'][:160]}")
    sys.exit(1 if flagged else 0)


if __name__ == "__main__":
    main()
