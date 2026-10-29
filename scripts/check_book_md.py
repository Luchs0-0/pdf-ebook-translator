# -*- coding: utf-8 -*-
"""Sanity-check MinerU full-book markdown: per-page text volume + spot compare."""
import re
import sys
import io

PATH = r"C:\Users\zhoun\personal-project\pdf-ebook-translator\out\book.md"

with io.open(PATH, encoding="utf-8") as f:
    md = f.read()

# split by page markers
parts = re.split(r"<!-- page (\d+) of (\d+) -->", md)
# parts: [pre, "1", "357", body1, "2", "357", body2, ...]
pages = {}
for i in range(1, len(parts), 3):
    num = int(parts[i])
    body = parts[i + 2] if i + 2 < len(parts) else ""
    pages[num] = body

print("pages parsed:", len(pages))
total_chars = sum(len(b) for b in pages.values())
print("total chars: %d (avg %.0f/page)" % (total_chars, total_chars / max(len(pages), 1)))

# distribution
lens = sorted(((len(b), n) for n, b in pages.items()))
print("\n--- 最短 8 页 ---")
for L, n in lens[:8]:
    print("  p%-4d %5d chars" % (n, L))
print("--- 最长 5 页 ---")
for L, n in lens[-5:]:
    print("  p%-4d %5d chars" % (n, L))

empty = [n for n, b in pages.items() if len(b.strip()) < 40]
print("\n近空页(<40字符): %d %s" % (len(empty), empty[:20]))

# heading stats
heads = re.findall(r"^#{1,6}\s+(.+)$", md, re.M)
print("\nheadings: %d" % len(heads))
print("前 12 个标题:")
for h in heads[:12]:
    print("   ", h[:70])

print("\n--- page 100 全文 ---")
print(pages.get(100, "(缺)")[:1200])
