# -*- coding: utf-8 -*-
"""按页统计解析出来的 Markdown：字符量、标题、图片引用、近空页。

用法：
    python tools/check_book_md.py --md workspace/interim/parse-alpine-skills-summer/markdown.md
"""
import argparse
import io
import re


def main():
    ap = argparse.ArgumentParser(description="Analyze a parsed book markdown")
    ap.add_argument("--md", required=True, help="Markdown 路径")
    ap.add_argument("--show-page", type=int, default=0, help="打印指定页全文（1 基）")
    args = ap.parse_args()

    md = io.open(args.md, encoding="utf-8").read()

    parts = re.split(r"<!-- page (\d+) of (\d+) -->", md)
    pages = {}
    for i in range(1, len(parts), 3):
        pages[int(parts[i])] = parts[i + 2] if i + 2 < len(parts) else ""

    print("文件字符数: %d" % len(md))
    if pages:
        print("页面块数: %d" % len(pages))
        print("平均每页字符: %.0f" % (sum(len(b) for b in pages.values()) / len(pages)))
        short = sorted(((len(b), n) for n, b in pages.items()))[:8]
        print("最短 8 页:", ", ".join("p%d(%d)" % (n, L) for L, n in short))
        empty = [n for n, b in pages.items() if len(b.strip()) < 40]
        print("近空页(<40字符): %d %s" % (len(empty), empty[:15]))
    else:
        print("页面块数: 0（standard 档不输出 <!-- page --> 注释，属正常）")

    print("标题数: %d" % len(re.findall(r"^#{1,6}\s+", md, re.M)))
    print("图片引用: %d" % len(re.findall(r"!\[[^\]]*\]\([^)]*\)", md)))

    if args.show_page and pages:
        print("\n--- page %d ---" % args.show_page)
        print(pages.get(args.show_page, "(该页不存在)")[:1500])


if __name__ == "__main__":
    main()
