# Repository Agent Instructions

## Required Read Order

Before inspecting code or running project commands, read:

1. `AGENTS.md`
2. `PROJECT_STATUS.md`
3. `ALICE_CONTROL_CENTER.md`
4. Any owner-referenced checkpoint or status note

Treat `PROJECT_STATUS.md` as the current project-state handoff and
`ALICE_CONTROL_CENTER.md` as the management, approval, risk, and usage policy.
The owner's latest explicit instruction controls when it resolves a conflict.

## Operating Rules

- Follow the Alice research-first gate before data, pronunciation, translation,
  audio, image, automation, API, dataset, licensing, or design-system work.
- Follow the Alice model-selection policy and recommend the lowest sufficient
  model before each task.
- Follow the usage guard and checkpoint rules; stop safely when usage is low.
- Respect all approval gates, especially commit, push, production, external API,
  paid-tool, schema, infrastructure, deletion, protected-file, and audio-quota
  gates.
- Keep Reading BBC / Learning Hub, Podcast Voice / Oxford MP3, Alice Organization,
  and Codex / Tooling / Headroom work in their approved paths.
- Identify scheduled automations by project, name, ID, memory path, and action mode
  before asking Codex to operate on them.
- Never use `git add .` or `git add -A`; stage only explicit approved files.
- Do not touch unrelated dirty files, and stop on conflicts.
- Make the smallest safe change and verify it before reporting completion.

## Repository Scope

- Repository: `D:\codex-clean-round2a-20260628`
- Product: Daily English Reader / Learning Hub for Thai learners
- Protected unless explicitly approved: `PROJECT_STATUS.md`, translation caches,
  production content logic, workflows, schemas, and unrelated project files.
