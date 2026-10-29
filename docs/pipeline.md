# Pipeline design notes

Why this pipeline looks the way it does, and what we rejected.

---

## The core decision: layout-aware parsing, not bubble OCR

The obvious approach for images-with-text is the manga route:

```
detect text regions → OCR → translate → erase pixels → re-typeset
```

We measured it on the sample book (a 357-page, two-column UIAA handbook) and rejected it.

### Measurement

Rendering 10 pages at 300 dpi, running PaddleOCR, then ordering the detected blocks two ways:

| Ordering rule | Result |
|---|---|
| Sort by `y`, then `x` (naive) | **10 / 10 pages interleaved the two columns** |
| Column-aware (left column top→bottom, then right) | correct reading order |

Concrete example, page 20 (`Most common types of rocks`):

```
naive:   A.1.3 → title → Limestone (L, y=110) → Granite (R, y=99) → Limestone body (L, y=171) → …
column:  A.1.3 → title → Limestone → its body … → then Granite → its body …
```

So text-order handling is mandatory, not cosmetic. Once you need column-aware ordering *plus*
figure extraction, a layout-aware document parser is cheaper than hand-rolling column
heuristics on top of a bubble detector.

### The same page through MinerU

```
## Qualities of a leader
Constantly aware of safety concerns.
Strong team spirit; enthusiastic and generous.
Eco-citizen: …
Technical skills, …
Attentive to the group.
Knows how to get the group's attention…
## Leader's code of conduct
Evaluates participants' abilities.
Investigates the route then informs participants…
```

Left column complete, then right column. Headings promoted to `##`. No custom logic.

---

## Tool comparison

| Tool | Approach | Scanned PDFs | Preserves layout | Figures exported | Used here |
|---|---|---|---|---|---|
| **MinerU** (`mineru-kit`) | VLM + OCR document parser → Markdown | ✅ | — (reflows) | ✅ with `standard` tier | **yes** |
| `pdf2zh` / PDFMathTranslate | layout-preserving bilingual PDF | ✅ with OCR | ✅ | n/a | rejected (see below) |
| marker | PDF → Markdown | ⚠️ uneven | — | partial | not used |
| docling | document structure | ⚠️ tables-first | — | partial | not used |
| manga-image-translator | bubble detect + inpaint | ✅ | erase / re-typeset | no | rejected |

### Why `pdf2zh` was not chosen

It is the right tool if the deliverable must be a **bilingual PDF with the original layout**.
It is the wrong tool here because:

- the reading target is a phone/tablet e-reader, where reflow beats fidelity;
- two-column re-layout inside a fixed page is exactly where column-ordering bugs hurt most;
- re-typesetting Chinese into coloured layout blocks has a poor quality/effort ratio.

It remains a valid alternative if an "archival, original layout" edition is ever wanted.

### Why not erase-and-re-typeset

357 pages, two columns, coloured section blocks, diamond bullets, full-bleed photos, running footers.
Redrawing all of that in Chinese costs far more than it returns, and CJK line-breaking inside
fixed boxes degrades quickly. We translate text; we do not repaint the book.

---

## MinerU tier trade-offs (MinerU 4.x)

| Tier | Cost | Figures | Verdict |
|---|---|---|---|
| `flash` | instant, no model download | ❌ becomes `doc:...` placeholder | fine for text-only reading |
| `standard` | needs `mineru-kit models download --tier standard` (GBs) | ✅ `images/page_N_image_M.jpg` | required for an illustrated edition |
| `advanced` | heaviest | ✅ | not needed for this book |

Measured on the sample: `standard` processed **357 pages in ~11.5 min** (0.515 page/s, CPU).

Entry point matters: `mineru parse` (server-backed) refuses local runs with
`parse-server is disabled`; **`mineru-kit parse` works directly**.

---

## Translation design

### Chunking by Markdown structure

Blocks are classified as heading / paragraph / list item / table row / fenced block / atom
(image, page number, HTML comment). Facts that forced this design:

- **Fenced blocks are not code in this book.** MinerU wraps tabular/figure text in ``` fences.
  Skipping fences left **217 untranslated English lines**; translating their inner text while
  keeping the fence cut that to **4**.
- **Bullet markers differ per tier** (`•` in flash, `▶` / `\-` in standard). Cache lookups
  normalise leading bullet characters, so both tiers share cached translations.
- **Large batches get truncated.** The model occasionally returns invalid JSON for big batches;
  retry with `--batch 1`, or use `patch_cache.py`, which translates single strings and accepts
  plain text instead of JSON.

### Glossary and dictionaries

Three artefacts, one source of truth:

| Artefact | Applied | Effect |
|---|---|---|
| `dict_pre.json` | before translation | locks source terminology |
| `dict_post.json` | after translation, **and again at rebuild** | repairs known mistranslations |
| `glossary_sakura.txt` | inside the LLM prompt, filtered per batch | keeps terminology consistent |

Two failure modes are checked by `build_dicts.py`, because both were observed in practice:

1. **Prefix collision** — a short key ordered before a longer key that starts with it
   (`belay` before `belay station`) corrupts the longer term.
2. **Self-consuming rule** — a post-dict value that starts with its own key
   (`团队动力 → 团队动力学`) rewrites correct output into `团队动力学学`.

Re-applying post-dicts during rebuild means terminology fixes never require re-translating.

### Cache

Every chunk is cached under `sha1(source_text)[:16]`. Consequences:

- an interrupted run resumes for free;
- a re-run with no outstanding chunks needs **no API key at all**;
- glossary changes only re-translate chunks whose source text changed.

Reported at startup, e.g. `缓存命中 3099 / 3099（100.0%），待翻译 0`.

---

## Output

| Target | Tool | Notes |
|---|---|---|
| EPUB | `pandoc` | `--resource-path` points at the parse directory so `images/…` resolves |
| PDF | `pandoc` → HTML → **headless Chrome/Edge** | no LaTeX needed; `--embed-resources` inlines images; `@page` CSS handles A4 + CJK fonts |

Headless-browser printing was chosen because this environment had neither `xelatex` nor
LibreOffice, and because it respects CSS `@page` sizing and system CJK fonts.
Trade-off: no automatic page numbers (the browser header/footer is disabled deliberately).
