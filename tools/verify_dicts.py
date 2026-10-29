# -*- coding: utf-8 -*-
"""Sanity check for a book's generated dictionary files.

用法：
    python tools/verify_dicts.py                                  # 默认 alpine-skills-summer
    python tools/verify_dicts.py --glossary-dir books/my-book/glossary
"""
import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import glossary_dir  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Verify dict_pre / dict_post")
    ap.add_argument("--glossary-dir", default=str(glossary_dir()),
                    help="字典所在目录（默认 books/<book>/glossary）")
    ap.add_argument("--sample", nargs="*", default=[],
                    help="额外要抽查的英文术语")
    args = ap.parse_args()

    base = args.glossary_dir
    pre_path = os.path.join(base, "dict_pre.json")
    post_path = os.path.join(base, "dict_post.json")
    for p in (pre_path, post_path):
        if not os.path.exists(p):
            sys.exit("找不到 %s（先跑 build_dicts.py）" % p)

    pre = json.load(io.open(pre_path, encoding="utf-8"))
    post = json.load(io.open(post_path, encoding="utf-8"))

    print("pre entries :", len(pre))
    print("post entries:", len(post))

    print("\n--- sample lookups ---")
    samples = args.sample or list(pre.keys())[:8]
    for k in samples:
        print("  %-24s -> %s" % (k, pre.get(k, "MISSING")))

    danger = [k for k in pre if len(k) <= 3]
    print("\n短键(<=3字符，易误伤):", danger if danger else "none")

    keys = list(pre.keys())
    issues = []
    for lk in keys:
        for sk in keys:
            if lk != sk and lk.startswith(sk) and len(lk) > len(sk):
                if keys.index(sk) < keys.index(lk):
                    issues.append((sk, lk))
    print("ordering issues:", issues if issues else "none")

    self_prefix = [(k, v) for k, v in post.items() if v.startswith(k) and v != k]
    print("post self-prefix issues:", self_prefix if self_prefix else "none")


if __name__ == "__main__":
    main()
