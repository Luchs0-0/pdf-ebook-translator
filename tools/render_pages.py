# -*- coding: utf-8 -*-
"""按页码把 PDF 页面渲染成 PNG（默认 300dpi），供 OCR / 人工抽检。

用法：
    python tools/render_pages.py --pdf workspace/source/book.pdf --pages "6,20,100-102" --out workspace/interim/png

依赖：pymupdf
"""
import argparse
import os
import sys

try:
    import pymupdf
except ImportError:
    sys.exit("缺少依赖：pip install pymupdf")


def parse_pages(spec, page_count):
    """'1,3,5-7' -> [0,2,4,5,6]（转 0 基索引，并做边界裁剪）"""
    out = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            start, end = int(a), int(b)
            for p in range(start, end + 1):
                out.append(p - 1)
        else:
            out.append(int(part) - 1)
    return sorted({p for p in out if 0 <= p < page_count})


def main():
    ap = argparse.ArgumentParser(description="Render PDF pages to PNG")
    ap.add_argument("--pdf", required=True, help="PDF 路径")
    ap.add_argument("--pages", required=True, help='页码，1 基，例："6,20,100-102"')
    ap.add_argument("--out", default="workspace/interim/png", help="输出目录")
    ap.add_argument("--dpi", type=int, default=300)
    args = ap.parse_args()

    doc = pymupdf.open(args.pdf)
    idxs = parse_pages(args.pages, doc.page_count)
    os.makedirs(args.out, exist_ok=True)

    for i in idxs:
        page = doc[i]
        pix = page.get_pixmap(dpi=args.dpi)
        path = os.path.join(args.out, f"p{i + 1:04d}.png")
        pix.save(path)
        print(f"p{i + 1:>4} -> {path}  ({pix.width}x{pix.height})")

    print(f"\n完成：{len(idxs)} 页 -> {os.path.abspath(args.out)}")


if __name__ == "__main__":
    main()
