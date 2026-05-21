import json
import math
from openai import OpenAI
from config import API_KEY, BASE_URL, PARSER_MODEL
from game_state import Character

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# ---------- point cost rules (server-authoritative) ----------

BUDGET_TIERS = {
    "waste":    {"label": "废灵根", "points": 10,   "desc": "资质平庸，逆天改命"},
    "normal":   {"label": "普通灵根", "points": 50,   "desc": "中规中矩，稳步修行"},
    "heaven":   {"label": "天灵根", "points": 100,  "desc": "天赋异禀，前途无量"},
    "immortal": {"label": "仙体", "points": None, "desc": "无限资质，自由创造"},
}

STAT_COST = {
    "hp":      lambda v: max(1, v // 10),
    "atk":     lambda v: v,
    "defense": lambda v: v,
}

ITEM_COST = {
    "healing_potion": 5,
}

KNOWN_TRAIT_COSTS = {
    "charged":    8,
    "focused":    6,
    "battle_cry": 5,
    "defending":  4,
}

STAT_BOUNDS = {
    "hp":      (10, 999),
    "atk":     (1, 99),
    "defense": (0, 50),
}

ITEM_BOUNDS = {
    "healing_potion": (0, 10),
}

# ---------- AI prompt ----------

CHARACTER_SYSTEM = """你是一个修仙世界的角色创建解析器。根据玩家的自由描述，生成结构化的角色属性。

## 世界观
这是一个修仙世界。玩家描述自己的角色——可以是剑修、体修、炼丹师、妖族、散修等任何设定。
你需要将描述转化为游戏属性。

## 属性说明
- hp（气血）：生命值，范围 10~999
- atk（攻击）：攻击力，范围 1~99
- defense（防御）：防御力，范围 0~50

## 物品
- healing_potion（回血丹）：恢复气血，每瓶 5 资质点，最多 10 瓶

## 战斗天赋（有实际效果）
- charged（蓄力）：8点 - 首次攻击伤害翻倍
- focused（心眼）：6点 - 首次攻击暴击率 50%
- battle_cry（气势）：5点 - 首次攻击 ATK+5
- defending（护体）：4点 - 首次受击伤害减半

## 描述性特质（不影响战斗数值，0点）
用来体现角色个性、背景、功法、灵根属性等。未来版本可能赋予实际效果。
例如：雷灵根、剑骨、炼丹天赋、妖族血脉 等

## 定价规则
- HP：每 10 点 = 1 资质点
- ATK：每 1 点 = 1 资质点
- DEF：每 1 点 = 1 资质点
- 物品和天赋：见上方固定价格

## 参考角色
名称：散修 | 气血 100(10点) 攻击 15(15点) 防御 8(8点) | 回血丹 x2(10点) | 总计 43 资质点

## 设计原则
- 剑修/刺客型：高 ATK，中 HP，低 DEF
- 体修/肉盾型：高 HP，高 DEF，低 ATK
- 均衡型：各属性均衡
- 从描述中提取或生成角色名称
- 总点数不超过预算

## 输出格式（只输出纯 JSON，无其他文字）
{
  "name": "角色名",
  "title": "一句话称号或描述",
  "stats": { "hp": 100, "atk": 15, "defense": 8 },
  "items": { "healing_potion": 2 },
  "traits": [
    { "id": "trait_id", "name": "显示名", "description": "简短描述", "mechanical": true },
    { "id": "custom_id", "name": "显示名", "description": "简短描述", "mechanical": false }
  ]
}

其中 mechanical 为 true 表示有战斗效果的天赋（id 必须是 charged/focused/battle_cry/defending 之一），
为 false 表示描述性特质。"""


def parse_character(description: str, budget: int | None) -> dict:
    budget_text = f"{budget} 资质点" if budget is not None else "无限制"
    user_msg = f"资质点预算：{budget_text}\n玩家描述：{description}"
    try:
        response = client.chat.completions.create(
            model=PARSER_MODEL,
            max_tokens=600,
            messages=[
                {"role": "system", "content": CHARACTER_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
        )
        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception as e:
        return {"error": str(e)}


# ---------- mock mode ----------

_MOCK_TEMPLATES = {
    "sword": {
        "keywords": ["剑", "剑修", "剑客", "剑仙", "御剑", "sword"],
        "name": "剑修",
        "title": "以剑入道",
        "stats": {"hp": 80, "atk": 20, "defense": 4},
        "items": {"healing_potion": 1},
        "traits": [
            {"id": "focused", "name": "剑心通明", "description": "首次出剑暴击率大增", "mechanical": True},
            {"id": "sword_bone", "name": "剑骨", "description": "天生剑修资质", "mechanical": False},
        ],
    },
    "body": {
        "keywords": ["体修", "肉身", "体", "力", "蛮", "铁", "金刚", "拳", "tank", "body"],
        "name": "体修",
        "title": "铁骨铜皮",
        "stats": {"hp": 180, "atk": 10, "defense": 12},
        "items": {"healing_potion": 1},
        "traits": [
            {"id": "defending", "name": "金刚体", "description": "首次受击伤害减半", "mechanical": True},
            {"id": "iron_body", "name": "铜皮铁骨", "description": "肉身坚韧超越常人", "mechanical": False},
        ],
    },
    "assassin": {
        "keywords": ["刺客", "暗杀", "影", "忍", "杀手", "隐", "assassin"],
        "name": "影杀者",
        "title": "暗影中的利刃",
        "stats": {"hp": 60, "atk": 22, "defense": 2},
        "items": {"healing_potion": 1},
        "traits": [
            {"id": "charged", "name": "暗杀蓄力", "description": "首次攻击伤害翻倍", "mechanical": True},
            {"id": "shadow_step", "name": "影步", "description": "身法诡异难以捉摸", "mechanical": False},
        ],
    },
    "alchemist": {
        "keywords": ["炼丹", "丹", "药", "医", "炼", "alchemist"],
        "name": "炼丹师",
        "title": "丹道通神",
        "stats": {"hp": 90, "atk": 12, "defense": 6},
        "items": {"healing_potion": 4},
        "traits": [
            {"id": "alchemy_talent", "name": "丹道天赋", "description": "炼丹悟性超群", "mechanical": False},
        ],
    },
    "demon": {
        "keywords": ["妖", "魔", "鬼", "兽", "龙", "凤", "demon", "monster"],
        "name": "妖修",
        "title": "妖族血脉觉醒",
        "stats": {"hp": 120, "atk": 18, "defense": 6},
        "items": {"healing_potion": 0},
        "traits": [
            {"id": "battle_cry", "name": "妖气爆发", "description": "首次攻击气势加成", "mechanical": True},
            {"id": "demon_blood", "name": "妖族血脉", "description": "体内流淌着妖族之血", "mechanical": False},
        ],
    },
    "berserker": {
        "keywords": ["狂", "怒", "暴", "嗜血", "野蛮", "berserker"],
        "name": "狂修",
        "title": "以怒入道",
        "stats": {"hp": 130, "atk": 20, "defense": 3},
        "items": {"healing_potion": 0},
        "traits": [
            {"id": "battle_cry", "name": "暴怒", "description": "首次攻击气势加成", "mechanical": True},
            {"id": "berserker_blood", "name": "嗜血本能", "description": "越战越狂", "mechanical": False},
        ],
    },
}

_DEFAULT_TEMPLATE = {
    "name": "散修",
    "title": "无门无派",
    "stats": {"hp": 100, "atk": 15, "defense": 8},
    "items": {"healing_potion": 2},
    "traits": [],
}


def mock_parse_character(description: str, budget: int | None) -> dict:
    t = description.lower()
    template = None
    for tmpl in _MOCK_TEMPLATES.values():
        if any(w in t for w in tmpl["keywords"]):
            template = tmpl
            break
    if template is None:
        template = _DEFAULT_TEMPLATE

    result = {
        "name": template["name"],
        "title": template["title"],
        "stats": dict(template["stats"]),
        "items": dict(template["items"]),
        "traits": list(template["traits"]),
    }

    if budget is not None:
        result = _scale_to_budget(result, budget)

    return result


def _scale_to_budget(parsed: dict, budget: int) -> dict:
    _, cost = _calc_cost(parsed)
    if cost <= budget:
        return parsed

    while cost > budget and parsed["traits"]:
        trait = parsed["traits"][-1]
        if trait.get("mechanical") and trait["id"] in KNOWN_TRAIT_COSTS:
            parsed["traits"].pop()
            _, cost = _calc_cost(parsed)
        else:
            parsed["traits"].pop()

    _, cost = _calc_cost(parsed)

    while cost > budget and parsed["items"].get("healing_potion", 0) > 0:
        parsed["items"]["healing_potion"] -= 1
        _, cost = _calc_cost(parsed)

    if cost > budget:
        stats = parsed["stats"]
        ratio = budget / max(cost, 1)
        stats["hp"] = max(STAT_BOUNDS["hp"][0], int(stats["hp"] * ratio))
        stats["atk"] = max(STAT_BOUNDS["atk"][0], int(stats["atk"] * ratio))
        stats["defense"] = max(STAT_BOUNDS["defense"][0], int(stats["defense"] * ratio))

    return parsed


# ---------- validation (server-authoritative) ----------

def _calc_cost(parsed: dict) -> tuple[dict, int]:
    breakdown = {}
    stats = parsed.get("stats", {})

    for key, fn in STAT_COST.items():
        val = stats.get(key, 0)
        breakdown[key] = fn(val)

    item_total = 0
    for item_id, count in parsed.get("items", {}).items():
        if item_id in ITEM_COST:
            item_total += ITEM_COST[item_id] * count
    breakdown["items"] = item_total

    trait_total = 0
    for trait in parsed.get("traits", []):
        if trait.get("mechanical") and trait["id"] in KNOWN_TRAIT_COSTS:
            trait_total += KNOWN_TRAIT_COSTS[trait["id"]]
    breakdown["traits"] = trait_total

    breakdown["total"] = sum(breakdown.values())
    return breakdown, breakdown["total"]


def validate_and_recalculate(parsed: dict, budget: int | None) -> tuple[dict, dict, bool, str]:
    if "error" in parsed:
        return parsed, {}, False, f"AI 解析失败：{parsed['error']}"

    stats = parsed.get("stats", {})
    for key, (lo, hi) in STAT_BOUNDS.items():
        val = stats.get(key, lo)
        stats[key] = max(lo, min(hi, int(val)))
    parsed["stats"] = stats

    clean_items = {}
    for item_id, count in parsed.get("items", {}).items():
        if item_id in ITEM_COST:
            lo, hi = ITEM_BOUNDS.get(item_id, (0, 99))
            clean_items[item_id] = max(lo, min(hi, int(count)))
    parsed["items"] = clean_items

    clean_traits = []
    for trait in parsed.get("traits", []):
        if not isinstance(trait, dict) or "id" not in trait:
            continue
        if trait.get("mechanical") and trait["id"] not in KNOWN_TRAIT_COSTS:
            trait["mechanical"] = False
        clean_traits.append(trait)
    parsed["traits"] = clean_traits

    breakdown, total = _calc_cost(parsed)

    if budget is not None and total > budget:
        return parsed, breakdown, False, f"总计 {total} 资质点，超出预算 {budget} 点"

    return parsed, breakdown, True, ""


# ---------- build Character ----------

def build_character(parsed: dict) -> Character:
    stats = parsed["stats"]
    hp = stats["hp"]

    potion_count = parsed.get("items", {}).get("healing_potion", 0)
    items = {"healing_potion": potion_count} if potion_count > 0 else {}

    mechanical_status = [
        t["id"] for t in parsed.get("traits", [])
        if t.get("mechanical") and t["id"] in KNOWN_TRAIT_COSTS
    ]

    all_traits = [
        {"id": t["id"], "name": t.get("name", t["id"]), "description": t.get("description", "")}
        for t in parsed.get("traits", [])
    ]

    extras = {}
    if parsed.get("title"):
        extras["title"] = parsed["title"]

    return Character(
        name=parsed.get("name", "无名修士"),
        hp=hp,
        max_hp=hp,
        atk=stats["atk"],
        defense=stats["defense"],
        items=items,
        status=list(mechanical_status),
        traits=all_traits,
        extras=extras,
    )
