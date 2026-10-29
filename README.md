# pdf-ebook-translator

Turn **scanned PDF ebooks** into a translated edition (EPUB + PDF), with layout-aware parsing,
glossary-constrained LLM translation, and resumable, cache-backed runs.

Built for real books — two-column text, figures, tables, running headers — not for chat bubbles.

```
PDF (scanned, no text layer)
   │  MinerU (layout-aware parse, exports figures)
   ▼
Markdown + images/
   │  chunked translation: glossary injection + pre/post dictionaries + hash cache
   ▼
translated Markdown
   │  pandoc                     │  pandoc → HTML → headless Chrome
   ▼                             ▼
EPUB (with figures)          PDF (A4, CJK fonts)
```

---

## Why not just use a manga translator?

Most comic pipelines do: detect speech bubbles → OCR → translate → **erase text pixels and re-typeset**.
That works for short lines on white bubbles. On a two-column technical book it fails in three ways:

| Problem | What happens |
|---|---|
| Detector is trained on bubbles | Dense two-column body text gets split into fragments, and the two columns interleave |
| Erase-and-redraw | Re-typesetting Chinese into a 357-page colour layout is far more work than the result is worth |
| Bubble-level semantics | Books need paragraph-level reading order, not bubble order |

Measured on the sample book: **10 out of 10 pages interleaved the two columns** when sorted by `y` only.
A layout-aware parser is not an optimisation here — it is a requirement.
See [`docs/pipeline.md`](docs/pipeline.md).

---

## Repository layout

```
pdf-ebook-translator/
├─ tools/                     # all scripts (CLI, argparse, no hard-coded paths)
│   ├─ common.py              # shared path helpers (repo root, workspace, book dirs)
│   ├─ probe_pdf.py           # what is this PDF? pages / text layer / image dpi / layout
│   ├─ extract_pages.py       # pull a page range into a standalone PDF
│   ├─ render_pages.py        # render pages to PNG at a given dpi
│   ├─ ocr_probe.py           # OCR + two-column reading-order check (optional path)
│   ├─ translate_md.py        # chunked translation, glossary + dict + cache
│   ├─ patch_cache.py         # translate only the few blocks still missing
│   ├─ build_pdf.py           # Markdown → PDF (pandoc + headless Chrome/Edge)
│   ├─ verify_dicts.py        # dictionary sanity checks
│   └─ check_*.py             # quality reports for markdown / translation / pdf
├─ books/
│   └─ alpine-skills-summer/  # one directory per book
│       ├─ README.md
│       └─ glossary/          # glossary.md is the source of truth
│           ├─ glossary.md
│           ├─ build_dicts.py # glossary.md → dict_pre / dict_post / sakura glossary
│           ├─ dict_pre.json
│           ├─ dict_post.json
│           └─ glossary_sakura.txt
├─ docs/
│   ├─ pipeline.md            # design rationale + tool comparison
│   └─ troubleshooting.md     # every environment trap we actually hit
├─ workspace/                 # ALL runtime I/O lives here (nothing is committed)
│   ├─ source/                # put the original PDF here
│   ├─ interim/               # parse output, translated markdown, caches
│   └─ output/                # final EPUB / PDF
└─ requirements.txt
```

`workspace/` is intentionally git-ignored except for its `.gitkeep` files: it only ever holds
regenerable artefacts, so a fresh clone starts clean.

---

## Requirements

| Component | Why | Notes |
|---|---|---|
| Python 3.10+ | pipeline | `pip install -r requirements.txt` |
| [MinerU](https://github.com/opendatalab/MinerU) `4.x` | layout-aware parsing **and figure export** | `pip install "mineru[core]"`. Heaviest dependency — keep it in its **own** venv |
| [pandoc](https://pandoc.org/installing.html) `3.x` | Markdown → EPUB / HTML | On Windows it may install to `%LOCALAPPDATA%\Pandoc` and stay off `PATH` |
| Chrome or Edge | Markdown → PDF | used headless; no LaTeX install needed |
| Translation endpoint | any OpenAI-compatible API | this repo defaults to Tencent MaaS (`hy-mt2-plus`) |

No LaTeX and no LibreOffice are required.

---

## Quick start

```bash
git clone <this repo>
cd pdf-ebook-translator

python -m venv .venv
.venv/Scripts/activate          # Windows;  source .venv/bin/activate elsewhere
pip install -r requirements.txt

# MinerU in a separate env — it pulls a lot and pins its own versions
python -m venv .venv-mineru
.venv-mineru/Scripts/python -m pip install "mineru[core]"
```

### 1. Inspect the source PDF

```bash
python tools/probe_pdf.py --pdf workspace/source/book.pdf
```
Tells you: page count, whether there is a text layer, embedded image DPI, and whether the layout
is multi-column. If a text layer exists you can skip OCR entirely.

### 2. Parse it (layout-aware, with figures)

```bash
# one-time: fetch the "standard" tier models (needed for figure export)
.venv-mineru/Scripts/mineru-kit models download --tier standard --source modelscope

# parse the whole book; --format zip keeps markdown + images/ together
.venv-mineru/Scripts/mineru-kit parse workspace/source/book.pdf \
    -o workspace/interim/parse.zip --tier standard --format zip --pages all

# unzip next to it
mkdir workspace/interim/parse && tar -xf workspace/interim/parse.zip -C workspace/interim/parse
```

> **Tier matters.** `--tier flash` is instant and needs no model download, but it **does not export
> images** — figures become `doc:...` placeholders. `standard` exports `images/page_N_image_M.jpg`.
> `mineru parse` (the server-backed CLI) refuses to run locally with `parse-server is disabled`;
> `mineru-kit parse` is the direct entry point that works.

### 3. Translate

```bash
export HUNYUAN_API_KEY=<your key>
export HUNYUAN_BASE_URL=https://tokenhub-intl.tencentmaas.com/v1   # default
export HUNYUAN_MODEL=hy-mt2-plus                                   # default

python tools/translate_md.py \
    --md  workspace/interim/parse/markdown.md \
    --out workspace/interim/book_zh.md \
    --book alpine-skills-summer \
    --cache workspace/interim/translate_cache.json
```

Useful flags:

| Flag | Effect |
|---|---|
| `--dry-run` | count chunks and estimated requests, no API calls |
| `--limit 20` | translate only the first 20 chunks (smoke test) |
| `--batch 6` | chunks per request (lower it if responses get truncated) |
| `--book <name>` | resolves glossary/dict paths under `books/<name>/glossary/` |

Re-running is cheap: every translated chunk is cached by a hash of its source text, so an
interrupted run resumes, and a glossary fix only re-translates affected chunks.

### 4. Build the EPUB

```bash
pandoc workspace/interim/book_zh.md -f markdown \
    -o workspace/output/book-zh.epub \
    --toc --resource-path=workspace/interim/parse \
    --metadata title="…" --metadata lang=zh-CN
```

### 5. Build the PDF

```bash
python tools/build_pdf.py \
    --md  workspace/interim/book_zh.md \
    --out workspace/output/book-zh.pdf \
    --resource-path workspace/interim/parse \
    --title "…"
```
Uses `--embed-resources` (images inlined as base64) plus `@page` CSS for A4 and CJK fonts,
then prints with headless Chrome/Edge and the browser's own header/footer disabled.

---

## Books in this repo

| Book | Pages | Figures | Output | Notes |
|---|---|---|---|---|
| `alpine-skills-summer` (UIAA) | 401 (reflowed) | 688 | EPUB 27 MB · PDF 31 MB | scanned, 300 dpi, two-column |

Each book directory holds its own glossary; the pipeline itself is language- and book-agnostic.
See [`books/alpine-skills-summer/README.md`](books/alpine-skills-summer/README.md).

---

## Design notes

**Glossary is the single source of truth.** Edit `books/<book>/glossary/glossary.md`, run
`build_dicts.py`, and it regenerates three artefacts:

- `dict_pre.json` — source-side substitutions applied *before* translation (locks terminology in)
- `dict_post.json` — output-side corrections applied *after* translation (repairs known mistranslations)
- `glossary_sakura.txt` — `source->target` lines injected into the LLM system prompt, filtered to
  only the terms that actually occur in the current batch

Two dictionary hazards are checked automatically, because both bit us in practice:

1. **Prefix collisions** — a short key must never sit before a longer key that starts with it,
   or `belay station` becomes `保护站` plus leftovers.
2. **Self-consuming post rules** — if a post-dict *value* starts with its own *key*
   (`团队动力 → 团队动力学`), every already-correct `团队动力学` becomes `团队动力学学`.

**Post-dictionaries are re-applied at rebuild time**, so fixing a term does not require
re-translating anything.

---

## Limitations

- **Figure internals stay in the source language.** Charts, map labels and warning boxes are
  part of the raster image; this pipeline translates body text and captions, it does not redraw figures.
  Re-typesetting text inside images is a separate (and much larger) problem.
- **Reflow changes pagination.** A 357-page source becomes ~401 A4 pages; original page numbers
  survive only as inline numbers where the parser kept them.
- **OCR/VLM noise is filtered heuristically** (vowel-ratio test for logo garbage, single-token
  paragraph filter). A few odd tokens may survive; they are cheap to fix via `dict_post.json`.
- **Tables become fenced blocks.** MinerU wraps some tabular regions in code fences; the translator
  translates their inner text and preserves the fence, which renders acceptably but is not a real table.

---

## More documentation

- [`docs/pipeline.md`](docs/pipeline.md) — why layout-aware parsing, tool comparison, tier trade-offs
- [`docs/troubleshooting.md`](docs/troubleshooting.md) — the environment traps we hit (DLLs, oneDNN,
  proxy DNS, encoding, gitignore)
- [`README.zh-CN.md`](README.zh-CN.md) — 中文说明

---

## License

[MIT](LICENSE) © 2026 Luchs0-0

## Legal note

The pipeline is tooling; the **books are not included**. Translated editions of a copyrighted work
are derivative works — check the source licence and your local rules before publishing outputs.
Keep source PDFs out of the repository (`workspace/source/` is git-ignored).
