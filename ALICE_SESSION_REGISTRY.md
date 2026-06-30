# Alice Session Registry

This registry separates project conversations and scheduled automations. It is a
coordination index, not proof that a chat, run, or production task completed.
Update it only from owner-provided context or verified project evidence.

## Reading BBC / Learning Hub

- Repo/path: `D:\codex-clean-round2a-20260628`
- Purpose: Daily English Reader and English learning website
- Current control session: `Reading BBC - Alice Control Center`
- Source of truth: `PROJECT_STATUS.md`
- Control policy: `ALICE_CONTROL_CENTER.md`
- Suggested future session: `Reading BBC - UI Redesign Research`

## Podcast Voice / Oxford MP3

- Path: `D:\podcast voice`
- Purpose: podcast-style MP3 and Oxford audio batches
- Suggested audit name: `Podcast Voice - Oxford MP3 Audit - YYYY-MM-DD`
- Suggested batch name: `Podcast Voice - Oxford MP3 Batch - YYYY-MM-DD`

### Scheduled Automation

- Name: Oxford MP3 Daily Batch
- ID: `oxford-mp3-daily-batch`
- Memory: `$CODEX_HOME/automations/oxford-mp3-daily-batch/memory.md`
- Related path: `D:\podcast voice`
- Schedule: daily at 09:00 Asia/Bangkok, subject to owner confirmation
- Status from owner screenshot: Partially Verified
- Production verified in screenshot: No
- Next allowed mode without owner approval: inspect-only
- Risks: Git availability, ffmpeg path, Google TTS network/quota, monthly safety
  cap, and duplicate visible run/session names

## Alice Organization / Alice Money Engine

- Purpose: business/income engine and AI organization work
- Approved path: owner to confirm before file changes
- Suggested session: `Alice Money Engine - Platform Opportunity Scan`
- Keep separate from Reading and Podcast repositories.

## Codex / Tooling / Headroom

- Purpose: Codex tooling, setup, and usage optimization
- Approved path: task-specific; owner must identify it
- Do not install system compilers or global toolchains without approval.
- Do not let tooling experiments modify product repositories.

## Archived or Unclear Chats Needing Owner Review

Record unclear sidebar entries here only after the owner provides a title,
screenshot, summary, or export.

| Visible title | Suspected project | Evidence available | Owner decision needed |
| --- | --- | --- | --- |
| None recorded | Unknown | None | No |

Duplicate titles must be treated as potentially separate sessions or automation
runs until evidence shows otherwise.
