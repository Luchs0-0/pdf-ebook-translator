# -*- coding: utf-8 -*-
"""由术语表生成三个字典文件（供 LLM 翻译层使用）。

- dict_pre.json       翻译前：把英文术语强制替换成定译（长词优先）
- dict_post.json      翻译后：把常见错译纠回定译
- glossary_sakura.txt 术语表注入格式：原词->译词（每行一条）

用法：
    python build_dicts.py
输出到本文件所在目录。
"""
import io
import json
import os

OUT = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------
# PRE：英文术语 -> 中文定译
# 顺序即替换顺序，务必"长词在前"，避免子串撞车
# （例如 "belay station" 必须在 "belay" 之前）
# ---------------------------------------------------------------
PRE = {
    # 组织 / 长专名
    "International Climbing and Mountaineering Federation": "国际登山联合会",
    "high altitude pulmonary edema": "高山肺水肿",
    "high altitude cerebral edema": "高山脑水肿",
    "acute mountain sickness": "急性高山症",
    "rethreaded figure-eight": "回穿八字结",
    "false sense of security": "虚假安全感",
    "setting the tone": "营造氛围",
    "ground rules": "基本准则",
    "eco-citizen": "生态公民",
    "situational awareness": "情境意识",
    "objective hazard": "客观危险",
    "subjective hazard": "主观危险",
    "crevasse rescue": "裂缝救援",
    "wilderness first aid": "野外急救",
    "glacier travel": "冰川行进",
    "risk assessment": "风险评估",
    "risk management": "风险管理",
    "decision making": "决策",
    "group dynamics": "团队动力学",
    "group pressure": "群体压力",
    "group management": "团队管理",
    "group leader": "领队",
    "trip leader": "活动领队",
    "delegation": "分工授权",
    "contingency plan": "应急预案",
    "turn-around time": "折返时间",
    "summit fever": "登顶执念",
    "belay station": "保护站",
    "belay anchor": "保护锚点",
    "belay device": "保护器",
    "belaying": "做保护",
    "belayer": "保护者",
    "belay": "保护",
    "Munter hitch": "意大利半扣",
    "HMS carabiner": "HMS 锁",
    "figure-eight knot": "八字结",
    "alpine butterfly": "蝴蝶结",
    "clove hitch": "双套结",
    "overhand knot": "单结",
    "friction hitch": "摩擦结",
    "locking carabiner": "主锁",
    "quickdraw": "快挂",
    "cordelette": "绳套",
    "simul-climbing": "同时攀登",
    "lead climbing": "先锋攀登",
    "lead climber": "先锋",
    "rope team": "结组",
    "rope drag": "绳阻",
    "coil the rope": "盘绳",
    "rappel": "绳降",
    "abseil": "绳降",
    "lowering": "放绳下放",
    "self-arrest": "自我制动",
    "snow bollard": "雪柱",
    "snow stake": "雪桩",
    "deadman": "雪地埋桩保护",
    "ice screw": "冰锥",
    "ice axe": "冰镐",
    "walking axe": "行走镐",
    "technical axe": "技术镐",
    "crampons": "冰爪",
    "crampon points": "冰爪齿",
    "harness": "安全带",
    "helmet": "头盔",
    "carabiner": "铁锁",
    "sling": "扁带",
    "protection": "保护点",
    "placement": "放置",
    "piton": "岩钉",
    "anchor": "锚点",
    "pitch": "绳距",
    "summit": "顶峰",
    "glacier": "冰川",
    "crevasse": "冰裂缝",
    "bergschrund": "冰川边缘裂缝",
    "serac": "冰塔",
    "moraine": "冰碛",
    "scree": "碎石坡",
    "talus": "岩屑堆",
    "snow line": "雪线",
    "saddle": "鞍部",
    "ridge": "山脊",
    "arête": "刃脊",
    "couloir": "雪槽",
    "slab": "板岩",
    "cornice": "雪檐",
    "avalanche": "雪崩",
    "whiteout": "白盲",
    "hypothermia": "失温",
    "frostbite": "冻伤",
    "evacuation": "撤离",
    "rescue": "救援",
    "briefing": "行前说明",
    "debriefing": "复盘",
}

# ---------------------------------------------------------------
# POST：常见错译 -> 定译（长词在前，避免把正确译文再改坏）
# ---------------------------------------------------------------
POST = {
    "设定基调": "营造氛围",
    "定调子": "营造氛围",
    "定调": "营造氛围",
    "生态公民意识": "生态公民",
    "意大利半扣结": "意大利半扣",
    "芒特结": "意大利半扣",
    "蒙特尔结": "意大利半扣",
    "保护点站": "保护站",
    "确保站": "保护站",
    "确保者": "保护者",
    "贝雷": "保护",
    "保护站台": "保护站",
    "安全带组": "安全带",
    "冰爪齿钉": "冰爪齿",
    "冰锥钉": "冰锥",
    "绳索队": "结组",
    "绳队": "结组",
    "绳段": "绳距",
    "岩钉钉": "岩钉",
    "机械塞具": "机械塞",
    "岩塞塞": "岩塞",
    "冰裂缝缝": "冰裂缝",
    "垭口口": "垭口",
    "雪檐檐": "雪檐",
    "白盲症": "白盲",
    "低体温症": "失温",
    "体温过低": "失温",
    "冻疮": "冻伤",
    "急性高山病": "急性高山症",
    "高山病": "高山症",
    # 注意：不要写 "团队动力" -> "团队动力学"。
    # 键是自身值的前缀，会把已正确的"团队动力学"改成"团队动力学学"（实测踩过）。
    "团队动力学学": "团队动力学",
    "群体动力": "团队动力学",
    "登顶热": "登顶执念",
    "折返时刻": "折返时间",
    "向导": "领队",
}

# ---------------------------------------------------------------
# 输出
# ---------------------------------------------------------------
GLOSSARY_LINES = [f"{k}->{v}" for k, v in PRE.items()]

with io.open(os.path.join(OUT, "dict_pre.json"), "w", encoding="utf-8") as f:
    json.dump(PRE, f, ensure_ascii=True, indent=1)
with io.open(os.path.join(OUT, "dict_post.json"), "w", encoding="utf-8") as f:
    json.dump(POST, f, ensure_ascii=True, indent=1)
with io.open(os.path.join(OUT, "glossary_sakura.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(GLOSSARY_LINES) + "\n")

if __name__ == "__main__":
    for name in ("dict_pre.json", "dict_post.json"):
        with io.open(os.path.join(OUT, name), encoding="utf-8") as f:
            data = json.load(f)
        print(f"{name}: {len(data)} entries OK")
    print(f"glossary_sakura.txt: {len(GLOSSARY_LINES)} lines OK")

    # 子串撞车自检：若"短词"排在"长词"之前，替换时会把长词拆坏
    # 正确顺序 = 长词在前（例 "belay station" 必须早于 "belay"）
    keys = list(PRE.keys())
    warnings = 0
    for long_k in keys:
        for short_k in keys:
            if long_k != short_k and long_k.startswith(short_k) and len(long_k) > len(short_k):
                if keys.index(short_k) < keys.index(long_k):
                    print(f"WARN 顺序风险: '{short_k}' 排在 '{long_k}' 之前，替换会拆坏长词")
                    warnings += 1
    print(f"顺序自检：{warnings} 处风险")

    # POST 自检：键若是自身值的前缀，会把正确译文改成"叠字"
    # 例："团队动力" -> "团队动力学" 会把"团队动力学"变成"团队动力学学"
    self_prefix = [k for k, v in POST.items() if v.startswith(k) and v != k]
    if self_prefix:
        for k in self_prefix:
            print(f"WARN POST 自噬风险: '{k}' -> '{POST[k]}'（值以键开头，会产生叠字）")
    else:
        print("POST 自检：无自噬风险")

    # POST 自检：单字/双字泛化规则容易误伤正常行文
    broad = [(k, v) for k, v in POST.items() if len(k) <= 2]
    if broad:
        print("WARN POST 泛化风险（键<=2字，易误伤正常表述）:", broad)
