# Run 2026-10-17: bonsai1/L9/N3688

| File | What it is |
|---|---|
| `predictions.json` | Our expectations, committed in bonsai-interp `2dae2f0` before launch |
| `BRIEF.md`, `room_README.md`, `room_settings.json` | Exactly what the agent saw: the brief, the tool README (with the methods hints) and the permission seal |
| `transcript.jsonl` | The full headless session (stream-json), including the sub-agent |
| `audit.json` | Leak audit: 51 tool calls, 0 denied, 0 flagged |
| `room.bundle`, `room_git_log.txt` | The room's full git history, with the agent's pre-registration commits `9f80ff5`, `0b5703a`, `6f430e5`, `9c224a0`. To check it: `git clone room.bundle room` |
| `REPORT.md`, `summary.json` | The agent's report |
| `scored.json` | Our predictions scored: 6 held, 1 partial, 1 failed; plus a disclosure of what was not blind |
| `manifest.json` | How the room was built. This run predates `build_room.py`, and its toolchain was the interp package before it was renamed from `mono` |
