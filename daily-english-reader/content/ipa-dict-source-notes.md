# IPA Dictionary Source Notes

## Source

- Repository: https://github.com/open-dict-data/ipa-dict
- Source file: `data/en_US.txt` (English, General American)
- Source commit: `43c3570eb3553bdd19fccd2bd0091534889af023`
- Downloaded: 2026-06-30
- Source size: 3,180,267 bytes; 125,927 tab-delimited entries
- Source SHA-256: `2AF6F154A5C363275F052D1F85ACEDEF38ED185CA9745AA4314BE77F6B70DE67`

The upstream README says the US English data is based on a modified version of
`lingz/cmudict-ipa`, with stress markers added using `kylebgorman/syllabify`.
The repository and the credited US English source are MIT-licensed.

## Local Transformation

The audited source is vendored losslessly at `vendor/ipa-dict/en_US.txt.gz`.
Its uncompressed size and SHA-256 match the source values above. This path is
build-only: it is outside `static/`, is not copied into the generated site, and
is never fetched at browser runtime.

Every `render_site` call regenerates `ipa-dict-en-us-subset.json` from the exact
retained/generated article list passed to the normal daily build. The generated
JSON contains only exact words in that current corpus. If the source is missing
or unreadable, generation logs a warning and uses curated IPA only; the reading
build does not fail.

The generator excluded:

- entries with multiple comma-separated pronunciations;
- words without an exact upstream entry;
- numbers, punctuation-bearing tokens, one-letter tokens, and mixed-case forms;
- tokens seen only capitalized and all-caps acronyms;
- known unsafe names and places, including Pim, Toronto, London, NPR, and NASA;
- a conservative set of context-sensitive function words, including `the`, `a`, and `to`;
- words already present in the curated `ipa-lexicon.json`.

At runtime, `ipa-lexicon.json` has priority. Dictionary fallback is used only for
lowercase tokens. Exact inflected entries are allowed; no base-word or pronunciation
inference is performed. Missing or uncertain IPA remains hidden.

General American is a practical learner reference for the project's Canadian
audience, but it is not a Canadian-English transcription and may differ for some
vowels, lexical items, and regional pronunciations.

## License

The MIT License (MIT)

Copyright (c) 2016 dohliam

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
