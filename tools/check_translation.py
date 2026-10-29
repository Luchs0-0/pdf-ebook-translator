# -*- coding: utf-8 -*-
"""译文质量体检：中英比例、疑似未译行、章节关键词命中。

用法：
    python tools/check_translation.py --zh workspace/interim/book_zh.md [--en .../markdown.md]
"""
import argparse
import io
import re


def main():
    ap = argparse.ArgumentParser(description="Quality check for a translated markdown")
    ap.add_argument("--zh", required=True, help="中文稿路径")
    ap.add_argument("--en", default="", help="英文原稿路径（可选，用于对照）")
    ap.add_argument("--keywords", nargs="*", default=[],
                    help="要检查是否出现的中文关键词（可选）")
    args = ap.parse_args()

    zh = io.open(args.zh, encoding="utf-8").read()

    cjk = len(re.findall(r"[\u4e00-\u9fff]", zh))
    latin = len(re.findall(r"[A-Za-z]{2,}", zh))
    total = cjk + latin * 2
    print("中文字符: %d" % cjk)
    print("残留英文词: %d" % latin)
    print("中文占比: %.1f%%" % (cjk / max(total, 1) * 100))

    lines = [l for l in zh.splitlines() if l.strip()]
    leftover = [l for l in lines
                if len(re.findall(r"[A-Za-z]{2,}", l)) >= 4
                and not re.search(r"[\u4e00-\u9fff]", l)
                and not l.startswith("<!--")
                and not l.startswith("![")]
    print("\n疑似未译行数: %d" % len(leftover))
    for l in leftover[:15]:
        print("   ", l[:100])

    if args.en:
        en = io.open(args.en, encoding="utf-8").read()
        print("\n英文字符数: %d" % len(en))
        print("图片引用: %d" % len(re.findall(r"!\[[^\]]*\]\([^)]*\)", zh)))

    if args.keywords:
        print("\n=== 关键词命中 ===")
        for kw in args.keywords:
            print("  %-12s %s" % (kw, "命中" if kw in zh else "未出现"))


if __name__ == "__main__":
    main()
