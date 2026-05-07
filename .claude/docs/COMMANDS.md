# Slash Commands — Reading Guide

Slash commands turn multi-step CLI workflows into **single-line invocations**. Each command file lives in `../commands/<name>.md` and follows the Claude Code slash command convention (frontmatter + body).

## Available commands

| Command | Purpose | Argument |
|---|---|---|
| `/audit` | End-to-end pipeline (ingest → scan → analyze → top-3 plans → executive readout) | optional billing file path |
| `/ingest` | Ingest a single billing file | required: file path |
| `/scan` | Run detection rules against current data | none |
| `/remediate` | Generate plan in all 3 formats for one finding | required: finding_id |
| `/status` | Session telemetry: elapsed, prompts, findings, ports | none |
| `/deploy-mcp` | Start the MCP server (stdio default; --http optional) | optional flag |

## Why these and not more

Each command corresponds to a high-frequency or high-value invocation. Commands that map 1:1 to a single CLI subcommand (`uv run finops X`) without orchestration logic don't earn their keep — just type the CLI directly.

`/audit` is the headline command. It chains every other operation. A demo of this project should open with `/audit samples/aws_cur_sample.csv` — that single command is the entire MVP narrative.

## Command vs skill — what's the difference?

- **Skill** = methodology the AI applies when reasoning about a class of tasks.
- **Command** = a deterministic shortcut to a specific runbook.

A skill is "how to think about FinOps audits"; a command is "run the audit now". The audit *runbook* lives in the `/audit` command body; the *methodology* lives in `finops-architect/SKILL.md`.
