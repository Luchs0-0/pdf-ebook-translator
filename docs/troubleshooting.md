# Troubleshooting

Every trap below was hit while building this repo, on Windows 11 + Python 3.12.
Symptoms are quoted verbatim so they are greppable.

---

## MinerU / parsing

### `错误: 本地 mineru 服务未运行。请先运行 'mineru server start'`

MinerU 4.x split into a service + client. `mineru parse` needs a running server.
Two options:

```bash
mineru server start        # then mineru parse … works
```

…or skip the server entirely and use the direct entry point:

```bash
mineru-kit parse <pdf> -o out.zip --tier standard --format zip --pages all
```

### `错误: Local parse-server is disabled. Use --tier flash or --remote.`

`parse_server.local.mode` defaults to `disabled`:

```bash
mineru config show | grep parse_server
# parse_server.local.mode = disabled [default]
```

`mineru config set parse_server.local.mode managed` did **not** take effect in our environment.
The working path is `mineru-kit parse` (see above), which does not depend on this switch.

### Figures missing / `![Image block](doc:...)` in the output

You are on `--tier flash`. Flash does not export images — figures become internal `doc:` URIs
that no downstream tool can resolve. For images:

```bash
mineru-kit models download --tier standard --source modelscope   # GBs, one-time
mineru-kit parse <pdf> -o out.zip --tier standard --format zip --pages all
```

`--format zip` bundles `markdown.md` + `images/` together; extract them side by side.

### `--pages` silently only parsed the first 10 pages

`mineru parse` defaults to the first 10 pages. Always pass `--pages all` for a full book.

### Missing models: `MinerU2.5-Pro-… missing: .mineru_complete`

Standard/advanced tiers need the model download step above. `--source modelscope` is usually
faster than HuggingFace inside China; set `MINERU_MODEL_SOURCE=modelscope` to make it sticky.

---

## Python dependency traps

### `ImportError: DLL load failed while importing utf1632` (chardet)

chardet 7.x ships a binary that fails on some Windows setups.

```bash
pip install "chardet==5.2.0"
```

### `ImportError: DLL load failed while importing nattype / timezones / offsets` (pandas)

pandas **3.1.0** crashes at import on this machine; 3.0.x and 2.2.3 are fine.

```bash
pip install "pandas==2.2.3"
```

Installing the VC++ 2015-2022 redistributable helps a whole class of `DLL load failed` errors:

```bash
winget install Microsoft.VCRedist.2015+.x64
```

### `NotImplementedError: (Unimplemented) ConvertPirAttribute2RuntimeAttribute …` (Paddle)

Paddle 3.x on CPU trips a oneDNN bug. Disable MKLDNN:

```python
import os
os.environ["FLAGS_use_mkldnn"] = "0"
PaddleOCR(..., enable_mkldnn=False)
```

`tools/ocr_probe.py` already does this.

### PaddleOCR 3.x constructor arguments changed

`show_log` was removed and `use_angle_cls` became `use_textline_orientation`.
`tools/ocr_probe.py` tries several argument sets and falls back gracefully.

### Installing `mineru` breaks the main venv

`mineru[core]` pulls its own pandas / numpy / onnxruntime and will happily downgrade or upgrade
yours. **Use a separate environment** (`.venv-mineru`). The repo's main `requirements.txt`
stays minimal for exactly this reason.

---

## Translation endpoint

### `401 invalid_api_key`

The key exists but is not valid for the endpoint you called. Two different products look similar:

| Endpoint | Path |
|---|---|
| Tencent **MaaS** (used here) | `https://tokenhub-intl.tencentmaas.com/v1` |
| Hunyuan official | `https://api.hunyuan.cloud.tencent.com/v1` |

A key issued for one will 401 on the other. Create keys at
<https://console.cloud.tencent.com/hunyuan/start>.

### `400 … The model or service ID … does not exist`

Model IDs are per-platform. Measured on the MaaS endpoint:

| Model ID | Result |
|---|---|
| `hy-mt2-plus` | ✅ works |
| `hy4-preview` | ⚠️ timed out at 60 s |
| `hunyuan-translation-plus` | ❌ 400, service ID does not exist |
| `hy-mt2` | ❌ 400 |

### `WARN 返回格式异常，跳过该批`

The model returned malformed/truncated JSON, usually because the batch was too large.
Re-run with a smaller `--batch`, or:

```bash
python tools/patch_cache.py --md … --cache … --apply
```

`patch_cache.py` translates one string at a time and asks for plain text, not JSON.
Any remaining stragglers can be re-run repeatedly; cached blocks are skipped.

---

## Output generation

### `pandoc: 无法将"pandoc"项识别为 cmdlet…`

The Windows MSI installs into `%LOCALAPPDATA%\Pandoc` and does not always update `PATH`:

```powershell
& "$env:LOCALAPPDATA\Pandoc\pandoc.exe" --version
```

`tools/build_pdf.py` probes several locations automatically.

### `Could not fetch resource doc:…\: InvalidUrlException "Invalid scheme"`

You are converting a `flash`-tier Markdown that contains `doc:` placeholders.
Re-parse with `--tier standard` to obtain real images.

### PDF has no page numbers

Deliberate: headless Chrome's built-in header/footer carries the URL and date, so it is disabled
(`--no-pdf-header-footer`). Add numbering via a pandoc/LaTeX template if you need it.

### Chinese renders as boxes / tofu

The PDF CSS asks for `"Microsoft YaHei"`. On a machine without it, edit `CSS` in
`tools/build_pdf.py` to name an installed CJK family (e.g. "Source Han Sans SC", "PingFang SC").

---

## Environment quirks (Windows, this setup)

### Proxy DNS rewrites break direct CDN access

A Clash-style proxy resolved some hosts to fake IPs (`198.18.0.x`), which made
`*.mangadex.network` return 404 for every image while the API still worked.
If a host works via API but every asset 404s, check:

```powershell
Resolve-DnsName <host> | Select-Object Name, IPAddress
```

A fake-IP range means "the proxy intercepted it", not "the file is gone".

### PowerShell mangles Chinese literals

Chinese passed as a command-line literal (especially in here-strings) can land on disk as
mojibake. Write Chinese content through a file instead:

```python
io.open("x.md", "w", encoding="utf-8").write(text)
```

and generate JSON with `ensure_ascii=True` so the output is pure ASCII escapes.
For readable console output: `chcp 65001` and `$env:PYTHONIOENCODING = "utf-8"`.

### `git add -A` swallowed an entire virtualenv

`.gitignore` originally listed only `.venv/`, so `.venv-mineru/` was staged (thousands of files).
Use a glob:

```gitignore
.venv*/
```

If it already happened and was not pushed yet: `git rm -r --cached .venv-mineru`, then
`git commit --amend --no-edit`.

### Merging two folders and breaking every absolute path

If the repo moves, path constants die silently. All `tools/*.py` here derive paths from
`tools/common.py` (`REPO_ROOT = Path(__file__).resolve().parent.parent`) — keep it that way.
