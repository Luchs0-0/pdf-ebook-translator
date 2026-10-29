# -*- coding: utf-8 -*-
"""验证生成的 PDF：页数/文字/图片，并导出样页 PNG 供目视检查。

用法：
    python tools/check_pdf.py --pdf workspace/output/book-zh.pdf [--pages 1,200]
"""
import argparse
import os
import re

import pymupdf


def main():
    ap = argparse.ArgumentParser(description="Verify a generated PDF")
    ap.add_argument("--pdf", required=True, help="PDF 路径")
    ap.add_argument("--out-dir", default="workspace/interim/pdf-check", help="样页导出目录")
    ap.add_argument("--pages", default="", help='要导出的页码，如 "1,200"；默认首末各一页')
    args = ap.parse_args()

    doc = pymupdf.open(args.pdf)
    print("页数:", doc.page_count)
    print("大小: %.2f MB" % (os.path.getsize(args.pdf) / 1024 / 1024))
    print("元数据:", {k: v for k, v in doc.metadata.items() if v})

    cjk = latin = 0
    img_pages = 0
    for page in doc:
        t = page.get_text("text")
        cjk += len(re.findall(r"[\u4e00-\u9fff]", t))
        latin += len(re.findall(r"[A-Za-z]{2,}", t))
        if page.get_images(full=True):
            img_pages += 1

    print("\n中文字符: %d" % cjk)
    print("英文词: %d" % latin)
    print("中文占比: %.1f%%" % (cjk / max(cjk + latin * 2, 1) * 100))
    print("含图片页数: %d / %d" % (img_pages, doc.page_count))

    print("\n--- 第 1 页文字（前 200 字）---")
    print(doc[0].get_text("text").strip()[:200])

    if args.pages:
        targets = [int(x) - 1 for x in args.pages.split(",") if x.strip().isdigit()]
    else:
        targets = [0, doc.page_count // 2, doc.page_count - 1]
    os.makedirs(args.out_dir, exist_ok=True)
    for i in targets:
        if 0 <= i < doc.page_count:
            pix = doc[i].get_pixmap(dpi=110)
            path = os.path.join(args.out_dir, "page_%03d.png" % (i + 1))
            pix.save(path)
            print("\n导出:", path, "(%dx%d)" % (pix.width, pix.height))


if __name__ == "__main__":
    main()
