# -*- coding: utf-8 -*-
"""Quality check for the translated book markdown."""
import io
import re

ZH = r"C:\Users\zhoun\personal-project\pdf-ebook-translator\out\book_zh.md"
EN = r"C:\Users\zhoun\personal-project\pdf-ebook-translator\out\book.md"

zh = io.open(ZH, encoding="utf-8").read()
en = io.open(EN, encoding="utf-8").read()

cjk = len(re.findall(r"[\u4e00-\u9fff]", zh))
latin_words = len(re.findall(r"[A-Za-z]{2,}", zh))
print("中文字符: %d" % cjk)
print("残留英文词: %d" % latin_words)
print("中文/英文比: %.1f%%" % (cjk / max(cjk + latin_words * 2, 1) * 100))

# 残留英文的块（可能是漏译）
lines = [l for l in zh.splitlines() if l.strip()]
leftover = [l for l in lines
            if len(re.findall(r"[A-Za-z]{2,}", l)) >= 4
            and not re.search(r"[\u4e00-\u9fff]", l)
            and not l.startswith("<!--")
            and not l.startswith("![")]
print("\n疑似未译行数: %d" % len(leftover))
for l in leftover[:12]:
    print("   ", l[:90])

print("\n=== 章节抽样 ===")
for kw in ["如何组织团队", "双渔人结", "保护站", "裂缝救援", "失温"]:
    idx = zh.find(kw)
    print("  %-8s %s" % (kw, "命中" if idx >= 0 else "未出现"))
