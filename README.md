# Alpine Skills Summer —— 中文翻译工程

UIAA《Alpine Skills Summer》登山技术手册（357 页）的简体中文翻译项目。

本仓库是从 `../aoz/`（高达 A.O.Z 漫画汉化项目）**拆出来的独立工程**：
复用其中的 LLM 翻译层与术语表机制，但**不复用**漫画的图像处理管线（原因见 `docs/管线选型.md`）。

---

## 一、源文件

| 项 | 说明 |
|---|---|
| 原件 | `C:\Users\zhoun\Downloads\dokumen.pub_alpine-skills-summer.pdf` |
| 大小 | 56.8 MB |
| 页数 | 357 页 |
| 性质 | **纯扫描件**，无文本层（PyMuPDF 抽样 60 页字符数均为 0） |
| 内嵌图 | 1114×1580 px，**300 dpi**，每页 1 张 JPEG |
| 版面 | 双栏正文 + 彩色章节标题 + 菱形项目符号 + 全幅照片 + 页脚面包屑/页码 |
| 版权 | **原件不入库**（`.gitignore` 已排除 `*.pdf`）。入库前请自行确认授权范围 |

> ⚠️ 这本书的难点**不在翻译，而在双栏阅读顺序与版面还原**。

---

## 二、项目结构

```
alpine-skills-zh/
├─ README.md                  ← 本文档
├─ .gitignore
├─ source/                    ← 放原始 PDF（不入库）
├─ glossary/
│   ├─ alpine_glossary.md     ← 术语表（唯一真源，人工维护）
│   ├─ build_dicts.py         ← 由术语表生成三个字典文件
│   ├─ dict_pre.json          ← 翻译前替换
│   ├─ dict_post.json         ← 翻译后纠错
│   └─ glossary_sakura.txt    ← LLM 术语表注入格式（原词->译词）
├─ scripts/
│   ├─ probe_pdf.py           ← PDF 结构探针（页数/文本层/分辨率/版面）
│   ├─ render_pages.py        ← 按页码渲染 300dpi PNG
│   ├─ ocr_probe.py           ← OCR 抽检 + 双栏阅读顺序校验
│   └─ verify_dicts.py        ← 校验字典条数/样本/顺序风险
├─ docs/
│   └─ 管线选型.md            ← 为什么换工具、候选方案对比
└─ out/                       ← 输出（不入库）
```

---

## 三、统一约束（所有脚本共用）

Python 解释器用 A.O.Z 项目那套 venv（已装 torch / PyMuPDF / pymupdf）：

```
C:\Users\zhoun\personal-project\aoz\mit-venv\Scripts\python.exe
```

本仓库暂不建独立 venv。若后续要装 PaddleOCR（约 500 MB+），
建议在仓库内单独建 `.venv` 并纳入 `.gitignore`。

**中文落盘规则**（从 A.O.Z 项目继承的坑）：
不要在 PowerShell 命令里直接写中文字面量（会被转成乱码），
中文一律写进 `.py` / `.md` 文件，由 Python 以 `encoding="utf-8"` 读写；
生成 JSON 时用 `ensure_ascii=True`。

**控制台看中文**：PowerShell 默认代码页会让 Python 输出的中文变乱码，
运行前先执行这两行（仅影响显示，不影响文件内容）：
```powershell
chcp 65001 > $null
$env:PYTHONIOENCODING = "utf-8"
```

---

## 四、工作流（建议顺序）

### 步骤 0：结构探针（已完成，可复跑）
```powershell
$py = "C:\Users\zhoun\personal-project\aoz\mit-venv\Scripts\python.exe"
& $py scripts\probe_pdf.py --pdf "C:\Users\zhoun\Downloads\dokumen.pub_alpine-skills-summer.pdf"
```

### 步骤 1：OCR 抽检 + 栏序验证（✅ 已完成，见下方结论）
```powershell
# 渲染 10 页样张
& $py scripts\render_pages.py --pages "6,20,60,100,140,200,240,280,320,350" --out out\png
# 跑 OCR 并检查"先左栏后右栏"的阅读顺序
& $py scripts\ocr_probe.py --dir out\png --dump out\ocr_probe.json
```

**实测结论（10 页样本）**：
- OCR 识别质量良好：每页 6-66 个文本块，英文印刷体基本全中
- **10/10 页在"朴素顺序"（先上后下、再左后右）下左右栏严重交错**
  典型例子（第 20 页）：`Limestone`（左栏 y=110）→ `Granite`（右栏 y=99）→ 又跳回左栏
- 即：**必须**用栏感知排序或版面感知工具，不能靠 y 坐标排序
- 已实现栏感知排序（跨栏判定 = 宽度≥70% 且横跨中线；页脚区 y>80% 单独处理），
  在抽样页上能把左栏正文排成连续段落

> 这说明路线 B（MinerU 版面解析）是必需项而非可选项。

### 步骤 2：版面解析 → Markdown（**路线 B 已选定**）
用 **MinerU** 把扫描页解析成结构化 Markdown（含标题层级、段落、图注、表格）：
```powershell
# 待安装：pip install "magic-pdf[full]"
& $py -c "import magic_pdf" # 装完先验
magic-pdf -p "<PDF路径>" -o out\mineru
```
- 产出 `out\mineru\*.md`，是后续翻译的**唯一输入**（不再动原图）
- 重点检查：双栏是否被正确合并成连续段落、彩色标题是否被识别为 `##` 级标题

### 步骤 3：分块翻译（LLM + 术语表）
- 按 Markdown 段落切块（建议 1 段 1 请求或 3-5 段合并，控制上下文）
- 系统提示注入：`glossary/glossary_sakura.txt` + `aoz` 项目验证过的
  「保留专名 / 不扩写 / 祈使句保持祈使」规则
- 用 `dict_pre.json` 做前置锁定、`dict_post.json` 做后置纠错

### 步骤 4：合成 EPUB
```powershell
# pandoc 由 md 生成 epub（需装 pandoc）
pandoc out\mineru\book.md -o out\alpine-skills-zh.epub --toc --metadata title="高山技能（夏季）"
```
- 图片随 md 引用保留（MinerU 会把图切出来存 `images/`）
- 生成后人工过一遍：目录层级、图注位置、代码/列表格式

### 步骤 5：校对
术语一致性、页码/面包屑是否误译（EPUB 中可保留为小字注）、图注是否漏翻、祈使句语气。

---

## 五、当前状态

| 步骤 | 状态 |
|---|---|
| PDF 结构探针 | ✅ 完成（357 页 / 无文本层 / 300dpi / 双栏） |
| 术语表初稿 | ✅ 已建（md 约 100 条；生成 pre-dict **91** / post-dict **32** / sakura **91** 行） |
| 字典生成脚本 | ✅ 可运行，顺序自检 0 风险 |
| 脚本骨架 | ✅ 已就位（probe / render / ocr_probe / verify_dicts） |
| git | ✅ 已 `git init`（分支 main），已首次 commit |
| **OCR 抽检** | ✅ **已完成**（10 页，10/10 存在栏序问题，已实现栏感知排序） |
| 版面解析 / 试翻 / 整本 / 校对 | ❌ 未开始 |

**已定决策**：
- **翻译路线 = B（EPUB 重排）**：MinerU 解析 → Markdown → LLM 分块翻译 → pandoc 生成 EPUB。
  理由：技术手册的价值在内容可检索/可重排，原版彩色设计的还原成本不值。
- **OCR 引擎 = PaddleOCR**：与 A.O.Z 漫画项目保持一致，精度已验证。
- **仓库名 = `alpine-skills-zh`**：描述性命名，不直接顶书名、不与官方产生关联暗示。

### 已知待办

- [x] 装 OCR 引擎（paddleocr 3.7.0 + paddlepaddle 3.3.1）并跑完 OCR 抽检
- [ ] 装 MinerU（`magic-pdf[full]`），试解析第 100 页验证双栏合并
- [ ] 装 pandoc
- [ ] 配置远程仓库（gh 2.103.3 已装，**尚未登录**：需 `gh auth login`）

---

## 五之二、环境坑位（本机实测）

### 1. Paddle 3.x CPU 的 oneDNN 缺陷（必须关 MKLDNN）
```
NotImplementedError: (Unimplemented) ConvertPirAttribute2RuntimeAttribute not support
  [pir::ArrayAttribute<pir::DoubleAttribute>]
```
解法（脚本已内置）：
```python
os.environ["FLAGS_use_mkldnn"] = "0"
PaddleOCR(..., enable_mkldnn=False)
```

### 2. chardet 7.7.0 的 DLL 报错
```
ImportError: DLL load failed while importing utf1632
```
解法：`pip install "chardet==5.2.0"`

### 3. 装 paddle 把 numpy 降级了（2.5.4 → 2.3.5）
本仓库借用了 `aoz/mit-venv`（共享环境）。装 paddleocr 时 numpy 被降到 2.3.5，
cv2 也换成了 4.10.0。**已验证 A.O.Z 的 manga_translator 仍能正常启动**（help 输出正常），
但这是**版本漂移风险**：

> 若本项目再装更多依赖（MinerU 等），建议**在仓库内单独建 `.venv`**，
> 不要再往 `aoz/mit-venv` 里装，以免两边互相破坏。`.gitignore` 已排除 `.venv/`。

### 4. PaddleOCR 首次运行会下载模型
模型落在 `C:\Users\zhoun\.paddlex\official_models\`（约 200 MB），
首次运行慢属正常；后续会命中缓存。

---

## 六、与 A.O.Z 项目的复用关系

| 资产 | 复用？ | 说明 |
|---|---|---|
| LLM 翻译层（OpenAI 兼容端点） | ✅ 全部 | 换 target lang 与 prompt 即可 |
| 术语表 / 字典机制 | ✅ 机制 | 内容按登山术语重建 |
| venv / PyMuPDF / torch | ✅ 全部 | 直接指向 A.O.Z 的 venv |
| 代理绕行、编码规避经验 | ✅ 全部 | 见 A.O.Z README 第四节 |
| **漫画检测器（气泡）** | ❌ | 双栏正文会被切碎 |
| **抹字 + 回填（inpaint）** | ❌ | 彩色排版书重排代价过高 |
| **气泡分组逻辑** | ❌ | 书需段落级阅读顺序 |

详见 `docs/管线选型.md`。
