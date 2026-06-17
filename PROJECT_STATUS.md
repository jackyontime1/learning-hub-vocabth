# VocabTH / Podcast Voice - Project Status

Updated: June 17, 2026

## Workspace

- Working directory: `D:\podcast voice`
- Production source: `D:\podcast voice\deploy-rollback-original`
- Production URL: https://fabulous-tanuki-b7a44d.netlify.app
- Netlify site ID: `a3efdc09-9ec8-4e20-a27e-1f69f554d54b`
- Netlify CLI and direct API can access the site, but Netlify currently blocks new deploys because the account credit usage has been exceeded.
- Exact API response on June 12, 2026:
  `Account credit usage exceeded - new deploys are blocked until credits are added`
- Local Oxford translation changes are ready but not yet live.
- Prepared deploy package:
  `D:\podcast voice\outputs\vocabth-oxford-natural-thai-deploy-20260612-continue.zip`

## Current Scope

- Static audio-first vocabulary web app.
- Around 4,083 vocabulary entries.
- Oxford entries now use generated category metadata and no longer rely on the `Full Oxford Base` UI bucket.
- Job Interview Q&A contains 71 words across 8 days.
- Construction and Oxford categories still use Web Speech unless an MP3 manifest entry exists.
- Daily English Reader now has a local Flashcards page for podcast vocabulary:
  `D:\podcast voice\daily-english-reader\site\flashcards.html`
- Flashcards data is generated from Podcast categories into:
  `D:\podcast voice\daily-english-reader\site\data\podcast-flashcards.json`
- Current Flashcards payload: 4,130 cards across 11 Podcast categories.
- Flashcards progress is stored in browser localStorage key:
  `learnhub.flashcards.v1`
- Learning Hub now has a Cloudflare Pages-ready local build that combines Reading, Podcast, Vocabulary, Flashcards, and Saved under one static site:
  `D:\podcast voice\daily-english-reader\site`
- Podcast is available inside the same site at:
  `D:\podcast voice\daily-english-reader\site\podcast\index.html`
- Podcast audio paths for Flashcards now use same-site paths such as:
  `podcast/audio/words/...`
- Cloudflare Pages headers are generated at:
  `D:\podcast voice\daily-english-reader\site\_headers`
- Learning Hub CSS/JS assets are versioned with `?v=20260617-learning-hub` to avoid stale browser cache on iPhone after moving from the old Netlify Podcast URL.
- No Cloudflare deploy has been performed yet because Cloudflare Pages/R2 credentials and bucket config are not set in this workspace.
- Cloudflare Pages deploy was performed on June 17, 2026.
- Cloudflare Pages project:
  `learning-hub-vocabth`
- Cloudflare Pages production URL:
  `https://learning-hub-vocabth.pages.dev/`
- First deployment URL:
  `https://0e97e168.learning-hub-vocabth.pages.dev`
- R2 is not enabled yet on the Cloudflare account. Wrangler returned:
  `Please enable R2 through the Cloudflare Dashboard. [code: 10042]`
- Daily Reading automation has been configured for GitHub Actions -> Cloudflare Pages.
- Automation schedule:
  `05:00 America/Toronto`
- GitHub Actions uses UTC cron entries `09:00` and `10:00` with an `America/Toronto` time guard because GitHub schedule cron itself is UTC-based.
- Automation deploy target:
  `https://learning-hub-vocabth.pages.dev/`
- Automation uses free Reading audio generation (`pyttsx3` / `espeak-ng` + `ffmpeg`) and does not consume the Podcast Google Cloud TTS monthly safety cap.
- Automation uses the existing free image chain: source media, Unsplash, Openverse, Wikimedia Commons, fallback.
- GitHub repository:
  `https://github.com/jackyontime1/learning-hub-vocabth`
- GitHub Actions repository secrets are configured:
  `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`
- The workflow now runs a no-audio preflight build before the real Reading audio build and Cloudflare Pages deploy.

## Oxford Category Distribution

- Oxford source file contains 3,837 unique entries after cleanup.
- `Full Oxford Base` has been removed from the active category selector.
- Oxford entries are now distributed across 8 general categories and sorted by frequency rank within each category.
- The `translated only` filter now applies only to the 3 protected categories, so Oxford general categories show the full frequency-ranked lists on the website.
- Oxford Thai translation payload now covers all 3,837 entries in:
  `D:\podcast voice\deploy-rollback-original\oxford-translations.json`
- Translation coverage breakdown:
  - Preserved curated Thai entries from `thaiPack`: 185
  - Generated Thai meanings for missing Oxford entries: 3,652
  - Unresolved entries: 0
- For Oxford entries without curated examples, the UI now shows the word and Thai meaning only, and playback skips fake placeholder sentences so the lesson sounds less robotic.
- Current Oxford category counts:
  - `Starter Everyday`: 2,458
  - `Work & Study`: 441
  - `People & Feelings`: 235
  - `Travel & Places`: 107
  - `Home & Food`: 88
  - `Nature & Health`: 104
  - `Actions & Thinking`: 316
  - `Society & Media`: 88
- Category metadata file:
  `D:\podcast voice\deploy-rollback-original\oxford-metadata.json`
- Metadata generator:
  `D:\podcast voice\deploy-rollback-original\scripts\generate-oxford-metadata.py`
- Translation generator:
  `D:\podcast voice\deploy-rollback-original\scripts\generate-oxford-translations.py`

## Job Interview Audio

- Days 1-8 use pre-generated Google Cloud Text-to-Speech MP3 files.
- Voice: Google Chirp 3 HD Puck.
- English: `en-US-Chirp3-HD-Puck`.
- Thai: `th-TH-Chirp3-HD-Puck`.
- Audio is split into one file per queue item.
- Users can start from any word in the queue.
- Users can enable or disable spelling for current-day words.
- Playback speed control: `0.75x` to `1.25x`.
- Recall pause: 3 seconds.
- Previous-day words use short review audio.
- Current-day words use full audio with examples.
- Queue is capped at 50 words:
  - Day 2: 20
  - Day 3: 30
  - Day 4: 40
  - Days 5-8: 50

## Day 2 Audio Trial

Job Interview Day 2 currently uses profile `english-balanced-v2`:

- All English speech volume: `+5 dB`.
- English vocabulary speed: `0.98`.
- English example sentence speed: `0.88`.
- Thai speed remains `1.08`.
- Both spelling and no-spelling variants were generated.
- The new files were deployed to production on June 12, 2026.
- This profile is isolated to Day 2 and does not change Days 1 or 3-8.

The user should test Day 2 on an iPhone again before this profile is copied to other days.

## Headset Pause / Resume

- The web app now registers Media Session play, pause, stop, previous, and next handlers in `app.js`.
- This was added because the old web player only handled the on-page buttons and did not expose proper headset / lock-screen controls like YouTube or native audio apps.
- MP3 playback now uses one persistent hidden `<audio>` element instead of creating new audio objects for each play action.
- Job Interview lessons should now pause and resume from Bluetooth headset controls more consistently when using the MP3 lesson flow.
- Categories that still fall back to Web Speech may not behave as reliably as MP3-backed lessons on iPhone.

## TTS Quota

- Monthly safety cap: 900,000 characters.
- June 2026 usage recorded in manifest: 131,946 characters.
- Remaining safety allowance: 768,054 characters.
- Daily Oxford MP3 automation is active:
  - Automation ID: `oxford-mp3-daily-batch`
  - Schedule: daily at 09:00 Asia/Bangkok.
  - Maximum: 25 new words and 25,000 TTS characters per run.
  - It must resume from the next unfinished Oxford word in frequency order.
  - It must run a dry-run and create a backup before generation.
  - It must not deploy Netlify automatically.
- Never exceed the manifest cap.
- Always run `--dry-run` before generation.
- API key is local only:
  `D:\podcast voice\.secrets\google-tts-api-key.txt`
- Never upload or expose the API key in frontend files.

## Important Files

- App UI/data: `deploy-rollback-original\app.js`
- HTML: `deploy-rollback-original\index.html`
- Styles: `deploy-rollback-original\styles.css`
- Audio manifest: `deploy-rollback-original\audio\manifest.json`
- Job Interview jobs:
  `deploy-rollback-original\audio\jobs\job-interview-qanda-days-002-008.json`
- Job builder:
  `deploy-rollback-original\scripts\build-job-interview-audio-jobs.mjs`
- TTS generator:
  `deploy-rollback-original\scripts\generate-tts-batch.mjs`
- Audio files:
  `deploy-rollback-original\audio\words\job-interview-qanda`

## Useful Commands

Run from `D:\podcast voice\deploy-rollback-original`.

Rebuild Job Interview jobs:

```powershell
node scripts\build-job-interview-audio-jobs.mjs
```

Estimate one day:

```powershell
node scripts\generate-tts-batch.mjs --provider google --jobs audio\jobs\job-interview-qanda-days-002-008.json --split-items --spelling on --only-day 2 --dry-run
```

Generate one day:

```powershell
node scripts\generate-tts-batch.mjs --provider google --api-key-file ..\.secrets\google-tts-api-key.txt --jobs audio\jobs\job-interview-qanda-days-002-008.json --split-items --spelling on --only-day 2 --ffmpeg "C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
```

Generate the no-spelling variant by changing `--spelling on` to `--spelling off`.

Deploy:

```powershell
& 'C:\Users\admin\AppData\Roaming\npm\netlify.cmd' deploy --prod --dir 'D:\podcast voice\deploy-rollback-original' --site a3efdc09-9ec8-4e20-a27e-1f69f554d54b --json
```

Rebuild Reading flashcards data from Podcast:

```powershell
node "D:\podcast voice\daily-english-reader\scripts\build-podcast-flashcards.mjs"
```

Build the combined Learning Hub site for Cloudflare Pages preview/deploy:

```powershell
node "D:\podcast voice\daily-english-reader\scripts\build-learning-hub.mjs"
```

## Verification Completed

- All original 212 Job Interview MP3 files decoded successfully with ffmpeg.
- All 30 Day 2 `english-balanced-v2` files decoded successfully.
- Netlify serves MP3 files with HTTP Range `206`, suitable for iPhone playback.
- Production manifest and Day 2 profile files return HTTP `200`.
- No Google API key was found in deployed frontend files.
- Production `app.js` includes Media Session headset pause and resume handlers.
- Local code now routes MP3 playback through a persistent audio element and does not require new TTS generation.
- Oxford metadata generation completes locally without touching TTS quota.
- Oxford translation generation completed locally into JSON only and did not create any new audio files or consume TTS quota.
- Reading Flashcards local page loads successfully from `http://127.0.0.1:8092/flashcards.html`.
- `podcast-flashcards.json` returns HTTP `200` locally and contains 4,130 cards / 11 categories.
- Combined Learning Hub build completed locally on June 17, 2026.
- Local route checks returned HTTP `200` for:
  `index.html`, `podcast/index.html`, `flashcards.html`, `data/podcast-flashcards.json`, and `podcast/audio/manifest.json`.
- Browser mobile-width sanity check passed for Home, Podcast, and Flashcards. Flashcards loaded 4,130 cards and 12 category filter options including `All podcast categories`.
- JS syntax checks passed for Reading app JS, generated site app JS, Podcast app JS, and both Learning Hub build scripts.
- Daily English Reader unit tests passed: 11/11.
- Local `python -m http.server` returned `200` for an MP3 Range request because it does not emulate Cloudflare/R2 byte-range behavior; verify HTTP `206` again after audio is served from Cloudflare/R2.
- Cloudflare Pages deployment uploaded 316 files and `_headers` successfully.
- Cloudflare Pages route checks returned HTTP `200` for:
  `https://learning-hub-vocabth.pages.dev/`,
  `data/podcast-flashcards.json`, and
  `podcast/audio/manifest.json`.
- Cloudflare Pages MP3 Range check returned `200 OK` with `Accept-Ranges: bytes`, not `206 Partial Content`; move MP3 files to R2 after R2 is enabled, then re-test iPhone playback and headset pause/play.
- Daily Reading automation workflow YAML parsed successfully for both possible repo layouts:
  `D:\podcast voice\.github\workflows\daily-update.yml`
  and
  `D:\podcast voice\daily-english-reader\.github\workflows\daily-update.yml`
- Daily Reading automation verification passed locally:
  JS syntax checks passed and unit tests passed 11/11.

## Backups

- Full Job Interview Days 1-8:
  `D:\podcast voice\backups\vocabth-job-interview-days1-8-20260611-220500.zip`
- Before Day 2 English balance change:
  `D:\podcast voice\backups\before-day2-english-balance-20260612-105136.zip`
- Before Day 2 `english-balanced-v2` generation:
  `D:\podcast voice\backups\before-day2-english-balanced-v2-20260612-111758.zip`
- Before Day 2 `english-balanced-v2` deploy:
  `D:\podcast voice\backups\before-deploy-day2-english-balanced-v2-20260612-112218.zip`
- Before Oxford redistribution:
  `D:\podcast voice\backups\before-oxford-redistribute-20260612-124030.zip`
- Before Oxford natural-Thai translation deploy attempt:
  `D:\podcast voice\backups\before-oxford-natural-thai-deploy-20260612-145952.zip`
- Before Learning Hub Pages/R2 combined build:
  `D:\podcast voice\backups\before-learning-hub-pages-r2-20260617-112609.zip`
- Before Cloudflare Pages deploy:
  `D:\podcast voice\backups\before-cloudflare-pages-deploy-20260617-114149.zip`
- Before Daily Reader Cloudflare automation changes:
  `D:\podcast voice\backups\before-daily-reader-cloudflare-auto-20260617-120401.zip`

## Next Action

Set up Cloudflare Pages + R2 when credentials are available:

1. Publish `D:\podcast voice\daily-english-reader\site` as the Cloudflare Pages output.
2. Put or mirror Podcast MP3 files under the same public path convention:
   `/podcast/audio/words/...`.
3. Configure R2 CORS to allow `GET`, `HEAD`, `OPTIONS` and the `Range` header.
4. Test on iPhone Chrome/Safari:
   Reading, Podcast, Flashcards, MP3 play/pause, headset pause/play, and MP3 HTTP Range `206`.

Keep responses and progress updates concise to reduce token use.
