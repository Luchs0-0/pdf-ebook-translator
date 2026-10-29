# -*- coding: utf-8 -*-
"""OCR 抽检 + 双栏阅读顺序校验。

这是整本项目是否可行的**关键闸门**：
    双栏正文能否被正确分离、左右栏顺序是否正确、段落是否被切碎。

用法：
    python ocr_probe.py --dir out/png
    python ocr_probe.py --dir out/png --dump out/ocr_probe.json

依赖（本项目未预装，需自行安装）：
    pip install paddleocr paddlepaddle
    # 首次运行会自动下载模型（约 100-300 MB）
    # GPU 版：pip install paddlepaddle-gpu （需匹配 CUDA）

若装不动 paddle，可换 rapidocr-onnxruntime（更轻，纯 onnx，无需 paddle）：
    pip install rapidocr-onnxruntime
然后用 --engine rapidocr 运行。
"""
import argparse
import json
import os
import sys


# ---------------------------------------------------------------
# 引擎适配层
# ---------------------------------------------------------------
def load_engine(name):
    if name == "paddle":
        try:
            from paddleocr import PaddleOCR
        except ImportError:
            sys.exit(
                "缺少 paddleocr。安装：\n"
                "    pip install paddleocr paddlepaddle\n"
                "或改用轻量引擎：\n"
                "    pip install rapidocr-onnxruntime\n"
                "    python ocr_probe.py --dir <dir> --engine rapidocr"
            )
        ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        return ("paddle", ocr)

    if name == "rapidocr":
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError:
            sys.exit("缺少 rapidocr-onnxruntime：pip install rapidocr-onnxruntime")
        return ("rapidocr", RapidOCR())

    sys.exit(f"未知引擎: {name}")


def run_ocr(engine, path):
    """统一输出 [(x0, y0, x1, y1, text), ...]"""
    kind, model = engine
    out = []

    if kind == "paddle":
        # PaddleOCR 2.x / 3.x 接口差异兼容
        try:
            res = model.ocr(path, cls=True)
        except TypeError:
            res = model.ocr(path)
        if not res:
            return out
        # 3.x 可能返回 dict 列表；2.x 返回 [[box, (text, score)]]
        first = res[0] if isinstance(res, list) else res
        if isinstance(first, dict):  # 3.x
            for item in res:
                for box, text in zip(item.get("rec_boxes", []), item.get("rec_texts", [])):
                    xs = [p[0] for p in box] if hasattr(box[0], "__len__") else [box[0], box[2]]
                    ys = [p[1] for p in box] if hasattr(box[0], "__len__") else [box[1], box[3]]
                    out.append((min(xs), min(ys), max(xs), max(ys), text))
        else:  # 2.x
            for line in res:
                if not line:
                    continue
                for box, (text, _score) in line:
                    xs = [p[0] for p in box]
                    ys = [p[1] for p in box]
                    out.append((min(xs), min(ys), max(xs), max(ys), text))
        return out

    if kind == "rapidocr":
        res, _elapse = model(path)
        if not res:
            return out
        for box, text, _score in res:
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            out.append((min(xs), min(ys), max(xs), max(ys), text))
        return out

    return out


# ---------------------------------------------------------------
# 阅读顺序
# ---------------------------------------------------------------
def naive_order(blocks):
    """朴素顺序：先上后下，再左后右。双栏书这样排会把左右栏交错。"""
    return sorted(blocks, key=lambda b: (round(b["cy"] / 20), b["x0"]))


def column_order(blocks, page_w, span_ratio=0.55):
    """栏感知顺序：跨栏元素（标题/图）切分成横带，每带内先左栏后右栏。"""
    mid = page_w / 2
    spans, left, right = [], [], []
    for b in blocks:
        if b["w"] >= page_w * span_ratio:
            spans.append(b)
        elif b["cx"] < mid:
            left.append(b)
        else:
            right.append(b)

    spans.sort(key=lambda b: b["y0"])
    if not spans:
        # 没有跨栏元素：整页当作一个带
        return (sorted(left, key=lambda b: (b["y0"], b["x0"])) +
                sorted(right, key=lambda b: (b["y0"], b["x0"])))

    bands = [{"top": s["y0"], "bottom": s["y1"], "span": s} for s in spans]
    banded = {i: {"left": [], "right": []} for i in range(len(bands))}

    for b in left + right:
        idx = 0
        for i, band in enumerate(bands):
            if b["cy"] >= band["top"]:
                idx = i
        target = "left" if b["cx"] < mid else "right"
        banded[idx][target].append(b)

    ordered = []
    for i, band in enumerate(bands):
        ordered.append(band["span"])
        ordered += sorted(banded[i]["left"], key=lambda b: (b["y0"], b["x0"]))
        ordered += sorted(banded[i]["right"], key=lambda b: (b["y0"], b["x0"]))
    return ordered


def main():
    ap = argparse.ArgumentParser(description="OCR probe with column-order check")
    ap.add_argument("--dir", required=True, help="PNG 目录")
    ap.add_argument("--engine", default="paddle", choices=["paddle", "rapidocr"])
    ap.add_argument("--dump", default="", help="把结果写成 JSON")
    args = ap.parse_args()

    try:
        from PIL import Image
    except ImportError:
        sys.exit("缺少依赖：pip install pillow")

    engine = load_engine(args.engine)
    files = sorted(f for f in os.listdir(args.dir) if f.lower().endswith((".png", ".jpg", ".jpeg")))
    if not files:
        sys.exit(f"目录里没有图片: {args.dir}")

    report = []
    diff_pages = 0

    for fname in files:
        path = os.path.join(args.dir, fname)
        with Image.open(path) as im:
            page_w = im.width

        raw = run_ocr(engine, path)
        blocks = [{"x0": r[0], "y0": r[1], "x1": r[2], "y1": r[3], "text": r[4],
                   "cx": (r[0] + r[2]) / 2, "cy": (r[1] + r[3]) / 2,
                   "w": r[2] - r[0], "h": r[3] - r[1]} for r in raw]

        n = naive_order(blocks)
        c = column_order(blocks, page_w)

        # 顺序差异：能说明"朴素排序会交错左右栏"
        naive_seq = [b["text"] for b in n]
        col_seq = [b["text"] for b in c]
        differs = naive_seq != col_seq
        if differs:
            diff_pages += 1

        print(f"\n=== {fname}  块数={len(blocks)}  顺序差异={'是' if differs else '否'} ===")
        print("--- 栏感知顺序（前 8 块）---")
        for b in c[:8]:
            side = "跨栏" if b["w"] >= page_w * 0.55 else ("左" if b["cx"] < page_w / 2 else "右")
            print(f"  [{side}] y={b['y0']:>5.0f} x={b['x0']:>5.0f}  {b['text'][:60]}")
        if differs:
            print("--- 朴素顺序（前 8 块，注意是否左右交错）---")
            for b in n[:8]:
                print(f"  y={b['y0']:>5.0f} x={b['x0']:>5.0f}  {b['text'][:60]}")

        report.append({"page": fname, "page_w": page_w, "block_count": len(blocks),
                       "order_differs": differs, "blocks": blocks,
                       "column_order": [b["text"] for b in c]})

    print(f"\n=== 汇总 ===")
    print(f"处理 {len(files)} 页；栏序与朴素序不一致的页数：{diff_pages}/{len(files)}")
    if diff_pages == 0:
        print("→ 双栏分离良好，可直接沿用段落级流程")
    else:
        print("→ 存在栏序问题：必须使用栏感知排序（或用版面感知工具如 pdf2zh）")

    if args.dump:
        os.makedirs(os.path.dirname(os.path.abspath(args.dump)), exist_ok=True)
        with open(args.dump, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=1)
        print(f"结果已写入: {os.path.abspath(args.dump)}")


if __name__ == "__main__":
    main()
