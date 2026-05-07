---
description: Report current session status — elapsed time, prompts logged, findings count, agent runs, recent commits.
---

Print a status block:

```
FINOPS VIBE CODING SESSION STATUS
=================================
Elapsed:     <Hh Mm Ss>
Prompts:     <count> in prompts.md
Decisions:   <count> in BITACORA.md
Findings:    <count> active in DB
Agent runs:  <count> total (<count> Opus, <count> Haiku)
Commits:     <count> on current branch
Last commit: <hash short> · <message>
Open ports:  API <up|down> :8000 · Dashboard <up|down> :8501 · MCP <up|down> :8765
```

Use `make elapsed`, `wc -l prompts.md`, `git rev-list --count HEAD`, `git log -1 --oneline`, and the `lsof -i :PORT` for open-port checks.

End with: "Ready to continue. Next directive?"
