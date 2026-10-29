# -*- coding: utf-8 -*-
"""Sanity check for generated dict files."""
import io
import json

BASE = r"C:\Users\zhoun\personal-project\alpine-skills-zh\glossary"
pre = json.load(io.open(BASE + r"\dict_pre.json", encoding="utf-8"))
post = json.load(io.open(BASE + r"\dict_post.json", encoding="utf-8"))

print("pre entries :", len(pre))
print("post entries:", len(post))
print()

print("--- sample lookups ---")
for k in ["belay station", "belay", "crevasse rescue", "crevasse",
          "Munter hitch", "figure-eight knot", "glacier travel", "summit fever"]:
    print("  %-20s -> %s" % (k, pre.get(k, "MISSING")))
print()

danger = [k for k in ["col", "cam", "nut", "hex", "cord"] if k in pre]
print("dangerous short keys remaining:", danger if danger else "none")
print()

# prefix collision check (long must come before short)
keys = list(pre.keys())
issues = []
for lk in keys:
    for sk in keys:
        if lk != sk and lk.startswith(sk) and len(lk) > len(sk):
            if keys.index(sk) < keys.index(lk):
                issues.append((sk, lk))
print("ordering issues:", issues if issues else "none")
