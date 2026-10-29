# -*- coding: utf-8 -*-
"""Markdown 分块翻译：腾讯混元（OpenAI 兼容端点）+ 术语表注入 + 前后置字典。

设计要点
--------
1. **结构保真**：按 Markdown 块切分（标题/段落/列表项/表格行），逐块替换，
   代码块、图片、水平线原样保留。
2. **批量请求**：一次请求送多条片段（带编号标记），减少往返与费用。
3. **术语表注入**：读取 glossary_sakura.txt（`英->中` 每行一条），
   只把本批片段里实际出现的词条塞进 system prompt，避免污染。
4. **前后置字典**：dict_pre.json 先做英文->定译替换，dict_post.json 做译文兜底纠错。
5. **断点续跑**：每个片段的译文按源文本 hash 缓存到 --cache，
   重跑时命中缓存直接跳过（省钱、可中断）。

用法
----
    set HUNYUAN_API_KEY=<key>
    python translate_md.py --md out/mineru/book.md --out out/book_zh.md
    python translate_md.py --md ... --limit 5          # 只翻前 5 个片段（试跑）
    python translate_md.py --md ... --dry-run          # 只统计片段，不请求

环境变量
--------
    HUNYUAN_API_KEY   必填
    HUNYUAN_BASE_URL  默认 https://api.hunyuan.cloud.tencent.com/v1
    HUNYUAN_MODEL     默认 hy-mt2-plus
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time

try:
    import requests
except ImportError:
    sys.exit("缺少依赖：pip install requests")

DEFAULT_BASE = os.environ.get("HUNYUAN_BASE_URL", "https://api.hunyuan.cloud.tencent.com/v1")
DEFAULT_MODEL = os.environ.get("HUNYUAN_MODEL", "hy-mt2-plus")

SYSTEM_TEMPLATE = """你是专业的英译中技术翻译，正在翻译一本登山技术手册（UIAA Alpine Skills）。
严格遵守以下规则：

1. 只输出译文，不解释、不加注、不复述原文。
2. 术语必须使用下方术语表的规定译名；表中没有的专名，按行业通行译法。
3. 保持祈使句的祈使语气（原文 "Keep the rope taut." → "保持绳索绷紧。"），
   不要改写成"应该/需要…"。
4. 不扩写、不省略、不合并句子。数字与单位原样保留（不换算）。
5. 图注、标题、项目符号照译，保留其层级语义。
6. 输入是带编号的片段数组，输出必须是**同样编号、同样数量**的 JSON 数组，
   每项形如 {{"id": 1, "zh": "译文"}}。不要输出任何其他内容。

{glossary}
"""

USER_TEMPLATE = """请翻译以下 {n} 条片段，输出 JSON 数组（id 与输入一致）：

{payload}
"""


# ---------------------------------------------------------------
# 术语表
# ---------------------------------------------------------------
def load_glossary(path):
    """读取 `英文->中文` 每行一条的术语表，返回 dict。"""
    table = {}
    if not path or not os.path.exists(path):
        return table
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "->" not in line:
                continue
            src, dst = line.split("->", 1)
            src, dst = src.strip(), dst.strip()
            if src:
                table[src] = dst
    return table


def relevant_glossary(batch_text, table, limit=60):
    """只挑本批实际出现的词条，拼成提示词段落。"""
    hits = []
    low = batch_text.lower()
    for src, dst in table.items():
        if src.lower() in low:
            hits.append((src, dst))
    hits = hits[:limit]
    if not hits:
        return "（本批无预置术语，按行业通行译法处理）"
    lines = ["术语表（必须遵守）："]
    lines += ["- %s → %s" % (s, d) for s, d in hits]
    return "\n".join(lines)


def apply_dict(text, table):
    """长词优先的字符串替换。"""
    if not table:
        return text
    for k in sorted(table, key=len, reverse=True):
        if k in text:
            text = text.replace(k, table[k])
    return text


# ---------------------------------------------------------------
# Markdown 切块
# ---------------------------------------------------------------
CODE_FENCE = re.compile(r"^\s*(```|~~~)")
HEADING = re.compile(r"^\s{0,3}#{1,6}\s+")
LIST_ITEM = re.compile(r"^\s*([-*+]|\d+[.)])\s+")
IMAGE_ONLY = re.compile(r"^\s*!\[[^\]]*\]\([^)]*\)\s*$")
HR = re.compile(r"^\s*([-*_]\s*){3,}$")
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
PAGE_NO = re.compile(r"^\s*[-—\s]*\d{1,4}[-—\s]*$")
HTML_COMMENT = re.compile(r"^\s*<!--.*-->\s*$")


def has_letters(s):
    return bool(re.search(r"[A-Za-z]{2,}", s))


def split_blocks(md_text):
    """返回 blocks: [{'kind','start','end','text'}]（行索引，end 不含）。

    translatable=True 的块后续会被翻译并替换。
    """
    lines = md_text.splitlines()
    blocks = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]

        if not line.strip():
            i += 1
            continue

        # 代码块：整体跳过
        if CODE_FENCE.match(line):
            fence = line.strip()[:3]
            j = i + 1
            while j < n and not lines[j].strip().startswith(fence):
                j += 1
            blocks.append({"kind": "code", "start": i, "end": min(j + 1, n),
                           "text": "\n".join(lines[i:min(j + 1, n)]), "translatable": False})
            i = min(j + 1, n)
            continue

        # 图片单独一行 / 水平线 / 纯页码 / HTML 注释
        if IMAGE_ONLY.match(line) or HR.match(line) or PAGE_NO.match(line) or HTML_COMMENT.match(line):
            blocks.append({"kind": "atom", "start": i, "end": i + 1,
                           "text": line, "translatable": False})
            i += 1
            continue

        # 标题
        if HEADING.match(line):
            blocks.append({"kind": "heading", "start": i, "end": i + 1,
                           "text": line, "translatable": has_letters(line)})
            i += 1
            continue

        # 表格：逐行（保留管道，翻单元格文本）
        if TABLE_ROW.match(line):
            blocks.append({"kind": "table", "start": i, "end": i + 1,
                           "text": line, "translatable": has_letters(line) and "---" not in line})
            i += 1
            continue

        # 列表项：单行一条
        if LIST_ITEM.match(line):
            blocks.append({"kind": "list", "start": i, "end": i + 1,
                           "text": line, "translatable": has_letters(line)})
            i += 1
            continue

        # 段落：连续非空行合并
        j = i
        while (j < n and lines[j].strip() and not HEADING.match(lines[j])
               and not LIST_ITEM.match(lines[j]) and not TABLE_ROW.match(lines[j])
               and not CODE_FENCE.match(lines[j]) and not HR.match(lines[j])
               and not IMAGE_ONLY.match(lines[j])):
            j += 1
        para = " ".join(l.strip() for l in lines[i:j])
        blocks.append({"kind": "para", "start": i, "end": j,
                       "text": para, "translatable": has_letters(para)})
        i = j

    return blocks


# ---------------------------------------------------------------
# LLM 调用
# ---------------------------------------------------------------
def call_llm(session, base, model, key, system, user, timeout=180, retries=3):
    url = base.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "max_tokens": 8192,
    }
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}

    last = None
    for attempt in range(retries):
        try:
            r = session.post(url, json=payload, headers=headers, timeout=timeout)
            if r.status_code != 200:
                last = "HTTP %s: %s" % (r.status_code, r.text[:300])
                time.sleep(2 * (attempt + 1))
                continue
            data = r.json()
            return data["choices"][0]["message"]["content"]
        except Exception as exc:  # noqa: BLE001
            last = str(exc)
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("LLM 调用失败: %s" % last)


def parse_json_array(raw):
    """从模型输出里抠出 JSON 数组（容忍 ```json 包裹与前后噪声）。"""
    if not raw:
        return None
    text = raw.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1).strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------
def key_of(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser(description="Markdown chunked translation via Hunyuan")
    ap.add_argument("--md", required=True, help="输入 Markdown")
    ap.add_argument("--out", required=True, help="输出 Markdown")
    ap.add_argument("--glossary", default="glossary/glossary_sakura.txt")
    ap.add_argument("--pre-dict", default="glossary/dict_pre.json")
    ap.add_argument("--post-dict", default="glossary/dict_post.json")
    ap.add_argument("--cache", default="out/translate_cache.json")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--batch", type=int, default=8, help="每请求片段数")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 个片段（0=全部）")
    ap.add_argument("--dry-run", action="store_true", help="只统计，不请求")
    args = ap.parse_args()

    with open(args.md, encoding="utf-8") as f:
        md = f.read()

    blocks = split_blocks(md)
    targets = [b for b in blocks if b["translatable"]]
    print("总块数 %d，可翻译块 %d" % (len(blocks), len(targets)))

    if args.limit:
        targets = targets[:args.limit]
        print("限制为前 %d 块" % len(targets))

    if args.dry_run:
        for b in targets[:10]:
            print("  [%s] %s" % (b["kind"], b["text"][:80]))
        print("...")
        return

    key = os.environ.get("HUNYUAN_API_KEY", "").strip()
    if not key:
        sys.exit("请先设置环境变量 HUNYUAN_API_KEY")

    glossary = load_glossary(args.glossary)
    print("术语表条数:", len(glossary))

    pre = json.load(open(args.pre_dict, encoding="utf-8")) if os.path.exists(args.pre_dict) else {}
    post = json.load(open(args.post_dict, encoding="utf-8")) if os.path.exists(args.post_dict) else {}

    cache = json.load(open(args.cache, encoding="utf-8")) if os.path.exists(args.cache) else {}
    os.makedirs(os.path.dirname(os.path.abspath(args.cache)), exist_ok=True)

    session = requests.Session()
    done = 0
    failed = 0

    for start in range(0, len(targets), args.batch):
        group = targets[start:start + args.batch]
        todo = [b for b in group if key_of(b["text"]) not in cache]

        if not todo:
            done += len(group)
            continue

        prepared = [apply_dict(b["text"], pre) for b in todo]
        batch_text = "\n".join(prepared)
        system = SYSTEM_TEMPLATE.format(glossary=relevant_glossary(batch_text, glossary))
        payload = json.dumps([{"id": i + 1, "en": t} for i, t in enumerate(prepared)],
                             ensure_ascii=False, indent=1)
        user = USER_TEMPLATE.format(n=len(prepared), payload=payload)

        try:
            raw = call_llm(session, args.base, args.model, key, system, user)
            arr = parse_json_array(raw)
            if not arr or len(arr) != len(prepared):
                print("  WARN 返回格式异常，跳过该批（%d 条）。原始片段：%s"
                      % (len(prepared), (raw or "")[:200]))
                failed += len(prepared)
                continue
            by_id = {int(item["id"]): item["zh"] for item in arr if "id" in item and "zh" in item}
            for i, b in enumerate(todo):
                zh = by_id.get(i + 1)
                if not zh:
                    failed += 1
                    continue
                cache[key_of(b["text"])] = apply_dict(zh, post)
            done += len(todo)
            print("  [%d/%d] 本批 %d 条已缓存" % (min(start + args.batch, len(targets)),
                                                len(targets), len(todo)))
        except Exception as exc:  # noqa: BLE001
            print("  ERROR 批次失败:", exc)
            failed += len(todo)

        # 每批落盘，支持中断续跑
        with open(args.cache, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=0)

    # 回填
    out_lines = []
    replaced = 0
    for b in blocks:
        zh = cache.get(key_of(b["text"])) if b["translatable"] else None
        if zh:
            prefix = ""
            if b["kind"] == "heading":
                m = re.match(r"^(\s{0,3}#{1,6}\s+)", b["text"])
                prefix = m.group(1) if m else ""
            elif b["kind"] == "list":
                m = re.match(r"^(\s*(?:[-*+]|\d+[.)])\s+)", b["text"])
                prefix = m.group(1) if m else ""
            out_lines.append(prefix + zh if prefix and not zh.startswith(prefix) else zh)
            replaced += 1
        else:
            out_lines.append(b["text"])

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n\n".join(out_lines) + "\n")

    print("\n完成：已替换 %d 块，失败 %d 块，输出 %s" % (replaced, failed, args.out))
    if failed:
        print("提示：失败块未替换，重跑同一命令会命中缓存、只补失败部分。")


if __name__ == "__main__":
    main()
