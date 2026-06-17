# Cloud TTS pilot for VocabTH

This generator creates pre-rendered MP3 lessons for the static app. It never stores API keys in frontend files.

## Google Cloud TTS

Set an API key in the current PowerShell session:

```powershell
$env:GOOGLE_TTS_API_KEY="your-google-api-key"
```

Generate only Job Interview Day 1:

```powershell
node .\scripts\generate-tts-batch.mjs --provider google --only-category job-interview-qanda --only-day 1
```

Generate one MP3 per vocabulary item:

```powershell
node .\scripts\generate-tts-batch.mjs --provider google --only-category job-interview-qanda --only-day 1 --split-items --spelling on
node .\scripts\generate-tts-batch.mjs --provider google --only-category job-interview-qanda --only-day 1 --split-items --spelling off
```

Split-item lessons include a 3-second recall pause and allow the app to start from any selected word.

Optional voice overrides:

```powershell
$env:GOOGLE_TTS_EN_VOICE="en-US-Neural2-F"
$env:GOOGLE_TTS_TH_VOICE="th-TH-Standard-A"
```

## Amazon Polly

Set temporary AWS credentials in the current PowerShell session:

```powershell
$env:AWS_ACCESS_KEY_ID="your-access-key"
$env:AWS_SECRET_ACCESS_KEY="your-secret-key"
$env:AWS_REGION="us-east-1"
```

Generate only Job Interview Day 1:

```powershell
node .\scripts\generate-tts-batch.mjs --provider amazon --only-category job-interview-qanda --only-day 1
```

Optional voice overrides:

```powershell
$env:AWS_POLLY_EN_VOICE="Joanna"
$env:AWS_POLLY_TH_VOICE="Niwat"
```

## Quota guard

The default monthly cap is 900,000 synthesized characters:

```powershell
node .\scripts\generate-tts-batch.mjs --provider google --month-cap 900000
```

Use `--dry-run` to estimate usage without generating audio:

```powershell
node .\scripts\generate-tts-batch.mjs --provider google --dry-run
```

When a lesson is generated, `audio/manifest.json` is updated to `status: "generated"`, and the app will play the MP3 before falling back to Web Speech.
