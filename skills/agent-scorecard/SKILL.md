---
name: agent-scorecard
description: Test and compare AI coding agents (Claude Code, Codex, Hermes, OpenCode, local models and others) on 5 real tasks with agent-scorecard, where every check is done by code. Use when the user wants to benchmark an agent or model on their own computer, compare two setups, or explain a scorecard result.
---

# Agent Scorecard

agent-scorecard gives an agent 5 everyday tasks (fix a bug, build a web page, summarize a PDF,
add up a CSV, refactor code) and scores the results with code. Hidden tests and integrity
checks mean an agent can't pass by gaming the visible tests.

## 1. Find or get the repo

Look for a folder that contains `scorecard/` and `tasks/`. If there isn't one, clone it:

```bash
git clone https://github.com/YOUR-USERNAME/agent-scorecard
cd agent-scorecard
```

It needs only Python 3.9 or newer. There is nothing to install.
Then confirm the checkers work on this machine:

```bash
python -m scorecard selftest
```

On Windows use `py` if `python` is not on PATH.

## 2. Pick the mode

Ask the user which agent and model they want to test, unless they already said.

**Auto mode** works when the agent has a one-shot command line. Each prompt is passed as one
argument with `{prompt}`. Commands that work today (flags change between versions, so check
`--help` if one fails):

| Agent | --cmd |
|---|---|
| Claude Code | `claude -p --permission-mode bypassPermissions {prompt}` |
| Hermes Agent | `hermes chat --quiet --yolo -q {prompt}` |
| Codex CLI | `codex exec --full-auto {prompt}` |

```bash
python -m scorecard run --agent "Hermes Agent" --model "MODEL NAME" --cmd "hermes chat --quiet --yolo -q {prompt}"
```

Add `--repeat 3` to run everything 3 times in fresh folders. Agents are not consistent, so
"passed every run" tells you more than one lucky run.

**Manual mode** is for chat apps, IDE agents, or recording a video. The user runs this in
their own terminal, because it waits for them to press Enter:

```bash
python -m scorecard run --agent "Cursor" --model "MODEL NAME"
```

It creates a fresh run folder, shows each prompt, copies it to the clipboard, and times the
task between two Enter presses. Tell the user to open their agent inside the run folder it prints.

## 3. Read the result

Each run folder gets `scorecard.json` and `report.html`. When explaining a result:

- Read `scorecard.json`. Lead with tasks passed, then time and peak RAM.
- For each failed task, name the failed check and quote its `detail`. Say what the agent most
  likely did wrong. Don't guess beyond what the files show. Look inside the run folder
  (`1-fix-bug/cart.py`, `3-pdf-summary/summary.txt` and so on) when it helps.
- A task where the user had to help counts as a fail. Say so plainly.
- To compare setups, put the runs side by side: passed, passed every run, minutes, peak RAM.

To add a run to the public results table: `python -m scorecard save "<run folder>"`.

## Rules

- Never edit files in `tasks/` or `scorecard/` to change a result, and never edit a run folder
  and then report the new score as the agent's score.
- If you are the agent being tested, don't score yourself in this session. Use auto mode, which
  runs a fresh session with no access to this conversation.
- Don't copy anything from `tasks/*/solution/` into a run folder.
- Report results as they are, including failures. Don't round a 3/5 up.
