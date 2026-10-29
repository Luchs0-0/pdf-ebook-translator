# -*- coding: utf-8 -*-
"""PDF 结构探针：页数 / 文本层 / 内嵌图分辨率 / 版面提示。

用法：
    python tools/probe_pdf.py --pdf workspace/source/book.pdf

依赖：pymupdf
"""
import argparse
import sys

try:
    import pymupdf
except ImportError:
    sys.exit("缺少依赖：pip install pymupdf")


def main():
    ap = argparse.ArgumentParser(description="Probe a scanned PDF's structure")
    ap.add_argument("--pdf", required=True, help="PDF 路径")
    ap.add_argument("--scan-pages", type=int, default=60,
                    help="全文扫描前 N 页用于统计文本层覆盖率")
    args = ap.parse_args()

    doc = pymupdf.open(args.pdf)

    print("=== 基本信息 ===")
    print("页数:", doc.page_count)
    print("元数据:", {k: v for k, v in doc.metadata.items() if v})
    print("已修复标记:", doc.is_repaired)

    print("\n=== 抽样页面 ===")
    print("页码   页面pt        内嵌图px     有效dpi   图片大小   格式")
    idxs = sorted({0, 1, 2, 5, 10, doc.page_count // 4, doc.page_count // 2,
                   (doc.page_count * 3) // 4, doc.page_count - 2, doc.page_count - 1})
    for i in idxs:
        if not (0 <= i < doc.page_count):
            continue
        page = doc[i]
        pw, ph = page.rect.width, page.rect.height
        imgs = page.get_images(full=True)
        if not imgs:
            print(f"p{i:<5} {pw:.0f}x{ph:.0f}    (无图)")
            continue
        for img in imgs[:1]:
            info = doc.extract_image(img[0])
            dpi = (info["width"] / pw) * 72 if pw else 0
            print(f"p{i:<5} {pw:.0f}x{ph:.0f}   {info['width']}x{info['height']}   "
                  f"{dpi:.0f}      {len(info['image'])//1024} KB   {info['ext']}")

    print(f"\n=== 文本层覆盖率（前 {args.scan_pages} 页）===")
    limit = min(args.scan_pages, doc.page_count)
    empty = 0
    total_chars = 0
    for i in range(limit):
        t = doc[i].get_text("text").strip()
        if len(t) < 20:
            empty += 1
        total_chars += len(t)
    print(f"扫描 {limit} 页：近乎无文字 {empty} 页，总字符数 {total_chars}")
    if total_chars == 0:
        print("→ 结论：纯扫描件，必须走 OCR 路线")
    elif empty > limit * 0.5:
        print("→ 结论：大部分页面无文本层，按扫描件处理")
    else:
        print("→ 结论：有可用文本层，可直接抽文本翻译（不需要 OCR）")

    print("\n=== 目录 ===")
    toc = doc.get_toc()
    print("条目数:", len(toc))
    for entry in toc[:10]:
        print("  ", entry)
    if toc and all(str(e[1]).startswith(("uiaa_", "page", "img")) for e in toc[:5]):
        print("→ 目录为自动生成的无意义名称，无法用于章节切分")


if __name__ == "__main__":
    main()
