# -*- coding: utf-8 -*-
"""Markdown → 中文 PDF（pandoc 出 HTML + Chrome/Edge headless 打印）。

为什么不用 LaTeX：本机无 xelatex，且安装 TeX 发行版体积巨大。
为什么不用 LibreOffice：本机未安装。

用法：
    python make_pdf.py --md out/book_std_zh.md --out out/book.pdf \
        --resource-path out/book_std --title "高山技能手册（夏季）"

依赖：pandoc（%LOCALAPPDATA%\\Pandoc\\pandoc.exe）、Chrome 或 Edge

要点：
- 图片用 --embed-resources 内嵌为 base64，避免相对路径在 file:// 下失效
- @page 设 A4 与页边距；字体优先微软雅黑，保证 CJK 正确渲染
- Chrome 打印时关闭自带页眉页脚（否则会带 URL 与日期）
"""
import argparse
import base64
import os
import shutil
import subprocess
import sys
import tempfile

PANDOC_CANDIDATES = [
    os.path.expandvars(r"%LOCALAPPDATA%\Pandoc\pandoc.exe"),
    r"C:\Program Files\Pandoc\pandoc.exe",
    "pandoc",
]

BROWSER_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

CSS = """
@page { size: A4; margin: 16mm 14mm 18mm 14mm; }
html { -webkit-print-color-adjust: exact; }
body {
  font-family: "Microsoft YaHei", "微软雅黑", "Source Han Sans SC", "PingFang SC", sans-serif;
  font-size: 10.8pt; line-height: 1.7; color: #111;
  max-width: none; margin: 0;
}
h1, h2, h3, h4 { line-height: 1.35; page-break-after: avoid; margin: 1.1em 0 .5em; }
h2 { font-size: 1.28em; border-bottom: 1px solid #ddd; padding-bottom: .18em; }
h3 { font-size: 1.12em; }
p { margin: .45em 0; text-align: justify; }
ul, ol { margin: .45em 0 .45em 1.3em; }
li { margin: .18em 0; }
img { max-width: 100%; height: auto; page-break-inside: avoid; display: block; margin: .6em auto; }
pre { white-space: pre-wrap; word-break: break-word; background: #f6f6f6;
      border: 1px solid #e2e2e2; border-radius: 4px; padding: .6em .7em; font-size: 9.2pt; }
code { font-family: Consolas, "Courier New", monospace; font-size: 9.4pt; }
table { border-collapse: collapse; width: 100%; margin: .6em 0; font-size: 9.6pt; }
th, td { border: 1px solid #ccc; padding: .3em .45em; }
blockquote { border-left: 3px solid #ccc; margin: .6em 0; padding: .2em .8em; color: #444; }
a { color: #0b62c4; text-decoration: none; word-break: break-all; }
"""


def find_first(paths):
    for p in paths:
        if os.path.sep not in p and shutil.which(p):
            return shutil.which(p)
        if os.path.isfile(p):
            return p
    return None


def main():
    ap = argparse.ArgumentParser(description="Markdown -> Chinese PDF via headless browser")
    ap.add_argument("--md", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--resource-path", default="", help="图片等资源的搜索目录")
    ap.add_argument("--title", default="")
    ap.add_argument("--keep-html", action="store_true", help="保留中间 HTML 便于排查")
    args = ap.parse_args()

    pandoc = find_first(PANDOC_CANDIDATES)
    browser = find_first(BROWSER_CANDIDATES)
    if not pandoc:
        sys.exit("找不到 pandoc")
    if not browser:
        sys.exit("找不到 Chrome / Edge")

    print("pandoc :", pandoc)
    print("browser:", browser)

    out_pdf = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_pdf), exist_ok=True)
    html_path = os.path.splitext(out_pdf)[0] + ".html"

    # 1) markdown -> HTML（内嵌图片 + CSS）
    cmd = [pandoc, args.md, "-f", "markdown", "-t", "html5",
           "--standalone", "--embed-resources",
           "--metadata", "title=" + (args.title or os.path.basename(args.md)),
           "-o", html_path]
    if args.resource_path:
        cmd.insert(2, "--resource-path=" + args.resource_path)
    # 把 CSS 写入临时文件后交给 pandoc
    css_dir = tempfile.mkdtemp(prefix="pdfcss_")
    css_file = os.path.join(css_dir, "print.css")
    with open(css_file, "w", encoding="utf-8") as f:
        f.write(CSS)
    cmd.insert(-2, "--css=" + css_file)

    print("\n[1/2] pandoc -> html ...")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(r.stderr[-2000:])
        sys.exit("pandoc 失败")
    size_mb = os.path.getsize(html_path) / 1024 / 1024
    print("   html: %s (%.1f MB)" % (html_path, size_mb))

    # 2) headless 浏览器打印 PDF
    print("\n[2/2] headless 打印 PDF ...")
    url = "file:///" + html_path.replace("\\", "/")
    profile = tempfile.mkdtemp(prefix="cr_profile_")
    bcmd = [browser, "--headless=new", "--disable-gpu", "--no-sandbox",
            "--no-pdf-header-footer",
            "--user-data-dir=" + profile,
            "--print-to-pdf=" + out_pdf,
            "--virtual-time-budget=20000",
            url]
    r2 = subprocess.run(bcmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if not os.path.exists(out_pdf):
        print((r2.stderr or "")[-2000:])
        sys.exit("PDF 生成失败")

    print("   PDF: %s (%.2f MB)" % (out_pdf, os.path.getsize(out_pdf) / 1024 / 1024))
    if not args.keep_html:
        os.remove(html_path)
    shutil.rmtree(css_dir, ignore_errors=True)
    shutil.rmtree(profile, ignore_errors=True)


if __name__ == "__main__":
    main()
