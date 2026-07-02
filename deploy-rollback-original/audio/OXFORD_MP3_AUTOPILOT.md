# Oxford MP3 Autopilot v1

Purpose: prepare the Oxford MP3 daily batch runner for a future owner-approved scheduled mode while keeping TTS quota, repo state, and production audio safe.

## Current State

- The recurring `oxford-mp3-daily-batch` automation must remain `PAUSED` until the owner explicitly approves unpausing.
- Autopilot v1 is readiness hardening only. It does not approve the next batch by itself.
- The runner must be used from a clean worktree or clean clone, not from a dirty original repository.
- `daily-english-reader/data/cache/translations.json` must never be resolved or modified by Oxford audio work.

## Daily Caps

Default runner caps:

- Selected lessons per run: `2`
- New words per run: `20`
- MP3 files per run: `70`
- Estimated TTS characters per run: `16,000`
- Monthly local safety cap: `900,000`

The runner stops before TTS if the selected batch exceeds any cap.

In live TTS mode, the runner also checks the local automation memory file when it is available. The memory must record the same month usage as the manifest, or the run stops before spending quota.

## Required Safe Flow

1. Keep automation paused until owner approval.
2. Create or use a clean worktree from latest `origin/main`.
3. Run a no-TTS dry-run first:
   `node scripts/run-oxford-audio-batch.mjs --dry-run`
4. Confirm:
   - selected lessons are expected;
   - duplicate output paths are `0`;
   - overwrite/rename/delete risk is `0`;
   - missing manifest MP3 references are `0`;
   - estimated characters and MP3 count are under caps.
5. Run live TTS only after owner approval or after the owner explicitly unpauses scheduled mode.
6. Rebuild Learning Hub data after generation.
7. Validate MP3 files, manifest references, and generated flashcards.
8. Commit from the clean worktree with explicit file paths only.
9. Push and monitor GitHub Actions.
10. Verify production manifest and MP3 URLs.
11. Update status/memory after successful production verification.

## Automatic Fixes Allowed

The runner may safely:

- skip/reuse existing valid MP3 files;
- create a pre-run backup before live generation;
- verify newly generated MP3s with ffmpeg;
- update the audio manifest after each generated variant;
- refresh the dry-run jobs report.

## Fail-Closed Conditions

The runner stops before TTS when it detects:

- dirty worktree usage outside the generated Oxford jobs file;
- the protected `translations.json` conflict;
- stale Oxford manifest status for physically complete lessons;
- stale automation memory quota/status when the memory file is available;
- missing manifest MP3 references;
- duplicate output paths;
- selected lessons, new words, MP3 files, or estimated characters above caps;
- monthly local quota overflow;
- missing ffmpeg for live generation.

If a hard error happens during scheduled mode, leave the automation paused and report before retrying. Do not continue spending quota.

## Owner Five-Day Check

Every five days, check:

- automation status is still intentional (`PAUSED` or owner-approved active);
- total July usage and remaining local cap;
- last completed category/day and last commit;
- latest GitHub Actions result;
- production manifest is reachable;
- production MP3 URLs for recent batches return `audio/mpeg`;
- next dry-run estimate stays under caps;
- no untracked or conflicted protected files are involved.

## Safe Unpause Procedure

Before unpausing:

1. Confirm `PROJECT_STATUS.md` and automation memory agree with production.
2. Confirm the original dirty repo is not used for live TTS.
3. Confirm dry-run output is under Autopilot v1 caps.
4. Confirm provider-side quota uncertainty is acceptable.
5. Owner explicitly approves unpausing.

Pause again immediately if any safety check fails, production verification fails, or quota usage is unclear.

## Do Not Touch

- `daily-english-reader/data/cache/translations.json`
- unrelated dirty files
- old audio artifacts except the approved generated MP3 set
- category order
- production app behavior
- recurring automation status without owner approval
