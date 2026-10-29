# pdf-ebook-translator

把**扫描版 PDF 电子书**翻译成中文（或任意目标语言），输出 **带图 EPUB + PDF**。
特点是：版面感知解析、术语表约束翻译、带缓存的断点续跑。

为真实书稿设计——双栏正文、插图、表格、页眉页脚，不是为对话气泡设计的。

```
PDF（扫描件，无文本层）
   │  MinerU（版面感知解析，并导出插图）
   ▼
Markdown + images/
   │  分块翻译：术语表注入 + 前后置字典 + hash 缓存
   ▼
中文 Markdown
   │  pandoc                      │  pandoc → HTML → headless Chrome
   ▼                              ▼
EPUB（含插图）                 PDF（A4，含中文字体）
```

---

## 为什么不能直接套漫画翻译管线

漫画管线通常是：检测气泡 → OCR → 翻译 → **抹掉原文字像素再重排**。
短句 + 白底气泡没问题，但放在双栏技术书上会崩三点：

| 问题 | 后果 |
|---|---|
| 检测器是按气泡训练的 | 密排双栏正文被切碎，左右栏交错 |
| 抹字重排 | 357 页彩色版面里重排中文，投入产出比极差 |
| 气泡级语义 | 书需要段落级阅读顺序，不是气泡顺序 |

实测：仅按 `y` 排序时，**10 页样本全部出现左右栏交错**。
所以版面感知解析不是"优化项"，而是**必需项**。详见 [`docs/pipeline.md`](docs/pipeline.md)。

---

## 目录结构

```
pdf-ebook-translator/
├─ tools/                     # 全部脚本（argparse，无硬编码路径）
│   ├─ common.py              # 共享路径推导（仓库根、workspace、书目目录）
│   ├─ probe_pdf.py           # PDF 体检：页数/文本层/图片 dpi/版面
│   ├─ extract_pages.py       # 抽取指定页码为独立 PDF
│   ├─ render_pages.py        # 按 dpi 渲染页面为 PNG
│   ├─ ocr_probe.py           # OCR + 双栏阅读顺序校验（备选路线）
│   ├─ translate_md.py        # 分块翻译（术语表 + 前后置字典 + 缓存）
│   ├─ patch_cache.py         # 只补翻缓存里仍缺失的少量块
│   ├─ build_pdf.py           # Markdown → PDF（pandoc + headless Chrome/Edge）
│   ├─ verify_dicts.py        # 字典自检
│   └─ check_*.py             # markdown / 译文 / PDF 质量报告
├─ books/
│   └─ alpine-skills-summer/  # 一本书一个目录
│       ├─ README.md
│       └─ glossary/          # glossary.md 是唯一真源
│           ├─ glossary.md
│           ├─ build_dicts.py # 由 glossary.md 生成下面三个字典
│           ├─ dict_pre.json
│           ├─ dict_post.json
│           └─ glossary_sakura.txt
├─ docs/
│   ├─ pipeline.md            # 设计取舍 + 工具对比
│   └─ troubleshooting.md     # 实际踩过的环境坑
├─ workspace/                 # 所有运行期 I/O 都在这里（不入库）
│   ├─ source/                # 放原始 PDF
│   ├─ interim/               # 解析产物、中文稿、缓存
│   └─ output/                # 最终 EPUB / PDF
└─ requirements.txt
```

`workspace/` 除 `.gitkeep` 外全部 gitignore：里面只有可再生的中间物，新克隆就是干净的。

---

## 依赖

| 组件 | 用途 | 说明 |
|---|---|---|
| Python 3.10+ | 管线本体 | `pip install -r requirements.txt` |
| [MinerU](https://github.com/opendatalab/MinerU) `4.x` | 版面解析 **并导出插图** | `pip install "mineru[core]"`，最重，**单独 venv** |
| [pandoc](https://pandoc.org/installing.html) `3.x` | Markdown → EPUB / HTML | Windows 可能装在 `%LOCALAPPDATA%\Pandoc` 且不在 PATH |
| Chrome 或 Edge | Markdown → PDF | headless 打印，**不需要装 LaTeX** |
| 翻译端点 | 任意 OpenAI 兼容 API | 本仓库默认腾讯 MaaS（`hy-mt2-plus`） |

不需要 LaTeX，也不需要 LibreOffice。

---

## 快速开始

```bash
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt

# MinerU 单独一个环境，它会钉住自己的一批版本
python -m venv .venv-mineru
.venv-mineru/Scripts/python -m pip install "mineru[core]"
```

### 1. 体检源 PDF
```bash
python tools/probe_pdf.py --pdf workspace/source/book.pdf
```
看：页数、有无文本层、内嵌图 dpi、是否多栏。**有文本层就可以跳过 OCR**。

### 2. 解析（带插图）
```bash
# 一次性：下 standard 档模型（导出插图需要）
.venv-mineru/Scripts/mineru-kit models download --tier standard --source modelscope

.venv-mineru/Scripts/mineru-kit parse workspace/source/book.pdf \
    -o workspace/interim/parse.zip --tier standard --format zip --pages all

mkdir workspace/interim/parse && tar -xf workspace/interim/parse.zip -C workspace/interim/parse
```

> **档位很关键**：`--tier flash` 秒出、不用下模型，但**不导出图片**（图片变成 `doc:...` 占位）。
> `standard` 才会导出 `images/page_N_image_M.jpg`。
> 另外 `mineru parse`（服务端 CLI）本地会报 `parse-server is disabled`，
> **`mineru-kit parse` 才是能直接用的入口**。

### 3. 翻译
```bash
export HUNYUAN_API_KEY=<你的 key>
export HUNYUAN_BASE_URL=https://tokenhub-intl.tencentmaas.com/v1   # 默认值
export HUNYUAN_MODEL=hy-mt2-plus                                   # 默认值

python tools/translate_md.py \
    --md  workspace/interim/parse/markdown.md \
    --out workspace/interim/book_zh.md \
    --book alpine-skills-summer \
    --cache workspace/interim/translate_cache.json
```

常用参数：

| 参数 | 作用 |
|---|---|
| `--dry-run` | 只统计块数与预估请求数，不发请求 |
| `--limit 20` | 只翻前 20 块（冒烟测试） |
| `--batch 6` | 每次请求的块数（返回被截断就调小） |
| `--book <name>` | 自动定位 `books/<name>/glossary/` |

**重跑很便宜**：每块译文按源文本 hash 缓存，中断可续；改术语表只影响相关块。

### 4. 出 EPUB
```bash
pandoc workspace/interim/book_zh.md -f markdown \
    -o workspace/output/book-zh.epub \
    --toc --resource-path=workspace/interim/parse \
    --metadata title="……" --metadata lang=zh-CN
```

### 5. 出 PDF
```bash
python tools/build_pdf.py \
    --md  workspace/interim/book_zh.md \
    --out workspace/output/book-zh.pdf \
    --resource-path workspace/interim/parse \
    --title "……"
```
用 `--embed-resources` 把图片内嵌成 base64，配 `@page` CSS 控 A4 与中文字体，
再用 headless Chrome/Edge 打印，并关掉浏览器自带页眉页脚。

---

## 本仓库中的书

| 书目 | 页数 | 插图 | 产物 | 说明 |
|---|---|---|---|---|
| `alpine-skills-summer`（UIAA） | 401（重排后） | 688 | EPUB 27 MB · PDF 31 MB | 扫描件，300 dpi，双栏 |

每本书一个目录、一套术语表；管线本身与具体书目、语种无关。

---

## 设计要点

**术语表是唯一真源。** 改 `books/<book>/glossary/glossary.md`，跑 `build_dicts.py`，生成三个文件：

- `dict_pre.json` —— 翻译**前**替换原文术语（锁定用词）
- `dict_post.json` —— 翻译**后**纠正已知错译
- `glossary_sakura.txt` —— `原词->译词`，注入 LLM system prompt，且只挑当前批次里实际出现的词条

两类字典事故已做成自动检查，因为都真实踩过：

1. **前缀撞车** —— 短词排在长词前面，`belay station` 会被拆坏
2. **后置字典自噬** —— 若某条规则的**值以键开头**（`团队动力 → 团队动力学`），
   所有本来就正确的"团队动力学"会变成"团队动力学**学**"

**后置字典在回填阶段会再跑一遍**，所以改术语不需要重翻。

---

## 已知局限

- **插图内部仍是原文**。图表、地图标注、警示框是像素的一部分；本管线只翻正文与图注，
  不重绘图片。图内文字汉化是另一个量级的问题。
- **重排会改变页码**。357 页原文重排成约 401 页 A4；原页码只在解析保留处作为行内数字存在。
- **OCR/VLM 噪声靠启发式过滤**（元音比例测 logo 垃圾、单 token 段落过滤）。
  偶有漏网，用 `dict_post.json` 修最省事。
- **表格会变成围栏块**。MinerU 把部分表格区域包进 code fence；翻译其内部文字并保留围栏，
  渲染可接受，但不是真正的表格。

---

## 更多文档

- [`docs/pipeline.md`](docs/pipeline.md) —— 为何必须版面感知、工具对比、档位取舍
- [`docs/troubleshooting.md`](docs/troubleshooting.md) —— 踩过的环境坑（DLL / oneDNN / 代理 DNS / 编码 / gitignore）
- [`README.md`](README.md) —— English

---

## 许可

[MIT](LICENSE) © 2026 Luchs0-0

## 版权说明

本仓库只含**工具**，不含书籍本体。对受版权保护作品做翻译并发布属于演绎作品，
请先确认来源许可与当地法规。原始 PDF 请勿入库（`workspace/source/` 已 gitignore）。
