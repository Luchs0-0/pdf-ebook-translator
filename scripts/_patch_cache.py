# -*- coding: utf-8 -*-
"""找出仍在缓存缺失的块，并用单条直译补进缓存。

用法：
    python _patch_cache.py --md out/book.md --cache out/book_cache.json [--apply]
"""
import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import translate_md as T  # noqa: E402

import requests  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", required=True)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--glossary", default="glossary/glossary_sakura.txt")
    ap.add_argument("--post-dict", default="glossary/dict_post.json")
    ap.add_argument("--apply", action="store_true", help="实际调用并写入缓存")
    args = ap.parse_args()

    md = io.open(args.md, encoding="utf-8").read()
    blocks = T.split_blocks(md)
    for b in blocks:
        if not b["translatable"]:
            continue
        if b["kind"] == "para" and len(b["text"].strip()) <= 30:
            import re
            if re.fullmatch(r"[A-Z][a-z]{2,6}", b["text"].strip()):
                b["translatable"] = False
                continue
        if T.looks_like_garbage(b["text"]):
            b["translatable"] = False

    cache = json.load(io.open(args.cache, encoding="utf-8"))
    missing = [b for b in blocks
               if b["translatable"] and T.cache_lookup(cache, b["text"]) is None]

    print("缺失块数:", len(missing))
    for b in missing:
        print("\n--- [%s] (%d chars) ---" % (b["kind"], len(b["text"])))
        print(b["text"][:600])

    if not missing or not args.apply:
        return

    key = os.environ.get("HUNYUAN_API_KEY", "").strip()
    if not key:
        sys.exit("未设置 HUNYUAN_API_KEY")

    glossary = T.load_glossary(args.glossary)
    post = json.load(io.open(args.post_dict, encoding="utf-8"))

    for b in missing:
        # 逐条直译：不分批、只要求纯译文，规避 JSON 截断
        system = ("你是专业英译中技术翻译。只输出译文，不要解释、不要 JSON、不要编号。"
                  "保持祈使句语气，数字与单位原样保留。\n" +
                  T.relevant_glossary(b["text"], glossary))
        try:
            r = requests.post(
                os.environ.get("HUNYUAN_BASE_URL", T.DEFAULT_BASE) + "/chat/completions",
                headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                json={"model": os.environ.get("HUNYUAN_MODEL", T.DEFAULT_MODEL),
                      "messages": [{"role": "system", "content": system},
                                   {"role": "user", "content": b["text"]}],
                      "temperature": 0.2, "max_tokens": 8192},
                timeout=180,
            )
            if r.status_code != 200:
                print("  FAIL HTTP", r.status_code, r.text[:200])
                continue
            zh = r.json()["choices"][0]["message"]["content"].strip()
            cache[T.key_of(b["text"])] = T.apply_dict(zh, post)
            print("  OK ->", zh[:120].replace("\n", " "))
        except Exception as exc:  # noqa: BLE001
            print("  ERR", exc)

    json.dump(cache, io.open(args.cache, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("\n缓存已更新，共", len(cache), "条")


if __name__ == "__main__":
    main()
