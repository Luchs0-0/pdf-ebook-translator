# -*- coding: utf-8 -*-
"""验证生成的 PDF：页数/文字/图片，并导出样页 PNG。"""
import io
import os
import re
import sys

import pymupdf

PDF = r"C:\Users\zhoun\personal-project\pdf-ebook-translator\out\alpine-skills-summer-zh.pdf"

doc = pymupdf.open(PDF)
print("页数:", doc.page_count)
print("大小: %.2f MB" % (os.path.getsize(PDF) / 1024 / 1024))
print("元数据:", {k: v for k, v in doc.metadata.items() if v})

# 文字统计
total_cjk = 0
total_latin = 0
img_pages = 0
for page in doc:
    t = page.get_text("text")
    total_cjk += len(re.findall(r"[\u4e00-\u9fff]", t))
    total_latin += len(re.findall(r"[A-Za-z]{2,}", t))
    if page.get_images(full=True):
        img_pages += 1

print("\n中文字符: %d" % total_cjk)
print("英文词: %d" % total_latin)
print("中文占比: %.1f%%" % (total_cjk / max(total_cjk + total_latin * 2, 1) * 100))
print("含图片页数: %d / %d" % (img_pages, doc.page_count))

print("\n--- 第 1 页文字（前 300 字）---")
print(doc[0].get_text("text").strip()[:300])

print("\n--- 抽 3 页看中文 ---")
targets = [doc.page_count // 4, doc.page_count // 2, doc.page_count - 5]
for i in targets:
    if 0 <= i < doc.page_count:
        t = doc[i].get_text("text").strip().replace("\n", " ")
        print("p%-4d %s" % (i + 1, t[:150]))

# 导出样页供目视检查
out_dir = r"C:\Users\zhoun\personal-project\pdf-ebook-translator\out\pdf_check"
os.makedirs(out_dir, exist_ok=True)
for i in [0, doc.page_count // 2]:
    pix = doc[i].get_pixmap(dpi=110)
    path = os.path.join(out_dir, "page_%03d.png" % (i + 1))
    pix.save(path)
    print("\n导出:", path, "(%dx%d)" % (pix.width, pix.height))
