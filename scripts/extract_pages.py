# -*- coding: utf-8 -*-
"""Extract a page range into a standalone PDF (for per-page experiments).

用法：
    python extract_pages.py --pdf "<PDF>" --pages "100" --out out/page100.pdf
"""
import argparse
import os
import sys

try:
    import pymupdf
except ImportError:
    sys.exit("缺少依赖：pip install pymupdf")

DEFAULT_PDF = r"C:\Users\zhoun\Downloads\dokumen.pub_alpine-skills-summer.pdf"


def parse_pages(spec, count):
    out = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return sorted({p - 1 for p in out if 1 <= p <= count})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default=DEFAULT_PDF)
    ap.add_argument("--pages", required=True, help='1 基页码，例 "100" 或 "100-102"')
    ap.add_argument("--out", required=True, help="输出 PDF 路径")
    args = ap.parse_args()

    src = pymupdf.open(args.pdf)
    idxs = parse_pages(args.pages, src.page_count)
    out = pymupdf.open()
    for i in idxs:
        out.insert_pdf(src, from_page=i, to_page=i)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    out.save(args.out)
    print("pages %s -> %s (%d page(s))" % ([i + 1 for i in idxs], args.out, len(idxs)))


if __name__ == "__main__":
    main()
