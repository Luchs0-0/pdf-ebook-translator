# alpine-skills-summer

Chinese translation of **UIAA — Alpine Skills Summer** (a 357-page mountaineering handbook).

This is the reference implementation for the pipeline: a scanned, two-column, figure-heavy book.

---

## Source

| Property | Value |
|---|---|
| Pages | 357 |
| Text layer | **none** (0 characters on every sampled page) → pure scan |
| Embedded images | 1114×1580 px, **300 dpi**, one JPEG per page |
| Page box | 267×379 pt (small handbook format) |
| Producer | Adobe Acrobat "Image Conversion Plug-in" |
| Layout | two-column body, coloured section headings, diamond bullets, full-bleed photos, running footer with breadcrumbs |

The PDF is **not** in this repository. Put it at `workspace/source/` before running anything.

---

## Result

| Metric | Value |
|---|---|
| Translatable chunks | 3,099 |
| Translated / failed | **3,099 / 0** |
| Chinese characters | 84,516 |
| Chinese ratio (zh vs en tokens) | **88.3 %** |
| Residual untranslated lines | 4 (logo noise + `ED`/`ABO-` grade abbreviations) |
| Figures exported | 688 |
| Final PDF | 401 pages, 30.6 MB (reflowed from 357) |
| Final EPUB | 27.3 MB |

Outputs land in `workspace/output/`.

---

## Glossary

`glossary/glossary.md` is the source of truth — edit it, then:

```bash
python books/alpine-skills-summer/glossary/build_dicts.py
python tools/verify_dicts.py          # 94 pre / 35 post, 0 ordering issues
```

Current size: **94** pre-dict entries, **35** post-dict entries, **94** prompt-glossary lines.

Terminology decisions worth knowing (representative entries):

| English | Chinese | Note |
|---|---|---|
| belay / belayer / belay station | 保护 / 保护者 / 保护站 | |
| Munter hitch | 意大利半扣 | also seen as 芒特结 — normalised to 意大利半扣 |
| rappel / abseil | 绳降 | one term for both |
| crevasse / crevasse rescue | 冰裂缝 / 裂缝救援 | |
| self-arrest | 自我制动 | |
| hypothermia / frostbite | 失温 / 冻伤 | |
| acute mountain sickness | 急性高山症 | abbreviations AMS/HAPE/HACE kept |
| group dynamics | 团队动力学 | see the post-dict warning below |
| leading a group | 带队 | breadcrumb wording |

**Post-dict hazard, kept as a regression example:** the rule `团队动力 → 团队动力学` looked
harmless but its *value starts with its key*, so every already-correct `团队动力学` became
`团队动力学学`. The fix is a reverse rule (`团队动力学学 → 团队动力学`); `build_dicts.py`
now refuses to let this class of rule pass its self-check.

---

## Regenerating this book end to end

```bash
PDF=workspace/source/alpine-skills-summer.pdf
BOOK=alpine-skills-summer
PARSE=workspace/interim/parse-$BOOK

# 1. inspect (expect: 357 pages, no text layer, 300 dpi)
python tools/probe_pdf.py --pdf $PDF

# 2. parse with figures
.venv-mineru/Scripts/mineru-kit parse $PDF -o workspace/interim/parse.zip \
    --tier standard --format zip --pages all
mkdir -p $PARSE && tar -xf workspace/interim/parse.zip -C $PARSE

# 3. translate (needs HUNYUAN_API_KEY only if something is uncached)
python tools/translate_md.py \
    --md $PARSE/markdown.md \
    --out workspace/interim/book_zh.md \
    --book $BOOK \
    --cache workspace/interim/translate_cache.json

# 4. quality report
python tools/check_translation.py --zh workspace/interim/book_zh.md

# 5. EPUB
pandoc workspace/interim/book_zh.md -f markdown \
    -o workspace/output/alpine-skills-summer-zh.epub \
    --toc --resource-path=$PARSE \
    --metadata title="高山技能手册（夏季）" --metadata lang=zh-CN

# 6. PDF
python tools/build_pdf.py \
    --md workspace/interim/book_zh.md \
    --out workspace/output/alpine-skills-summer-zh.pdf \
    --resource-path $PARSE --title "高山技能手册（夏季）"
```

A full re-translation takes ~30 min (≈420 requests at batch 8). A rebuild from cache takes
seconds and needs no API key.

---

## Known issues

- **Text inside figures is still English** — isobar values, map labels, warning boxes.
  Those are part of the raster image; this project translates body text and captions only.
- **Pagination differs** from the original (357 → 401 pages) because Chinese reflows.
  Original page numbers survive as inline numbers where the parser kept them.
- **Some tables arrive as fenced blocks** — MinerU wraps a few tabular regions in ``` fences.
  The translator translates their inner text and keeps the fence, which reads acceptably but
  is not a semantic table.
- **4 residual English lines** are intentional: a logo artefact (`Baig - alsng - aliic g - lc snm`)
  and a grade-abbreviation row (`6a ED 6b ED+ ABO- VI`).
