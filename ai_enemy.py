import json
import random
from openai import OpenAI
from config import API_KEY, BASE_URL, PARSER_MODEL
from game_state import Character

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# ---------- AI prompt ----------

ENEMY_SYSTEM = """你是一个修仙世界的随机敌人生成器。根据玩家角色的实力，生成一个合适的对手。

## 世界观
这是一个修仙世界。敌人可以是：
- 妖兽：野外的灵智妖兽（赤焰狼、玄冰蟒、金翅大鹏、九尾妖狐等）
- 邪修：走入歧途的修士（血煞道人、夺舍邪修、炼尸者等）
- 魔物：魔气侵蚀的产物（噬魂魔蛛、堕落傀儡、魔化树妖等）
- 灵兽：具有灵性但领地意识强的兽类（护巢灵鹤、守山石猿等）
- 鬼修：阴魂不散的怨灵（厉鬼、怨婴、冥将等）
- 散修：与玩家为敌的修炼者（劫道散修、赏金猎人等）

## 属性范围指导
根据提供的玩家属性，敌人应有挑战性但不压倒性：
- HP（气血）：玩家HP的 40%~80%
- ATK（攻击）：玩家ATK的 60%~90%
- DEF（防御）：玩家DEF的 50%~80%
- 最低值：HP≥10, ATK≥1, DEF≥0

## 输出格式（只输出纯 JSON，无其他文字）
{
  "name": "敌人名称（2-4字）",
  "title": "一句话称号",
  "category": "妖兽|邪修|魔物|灵兽|鬼修|散修",
  "stats": { "hp": 50, "atk": 12, "defense": 5 },
  "description": "2-3句话的遭遇场景描述，第二人称（你看到...你感觉到...），有画面感，营造紧张氛围",
  "traits": [
    { "id": "trait_id", "name": "显示名", "description": "简短描述", "mechanical": false }
  ]
}

## 设计原则
- 名称要有修仙感（不要西方奇幻风格如哥布林/骷髅/巨龙）
- description 是开场叙述，不超过3句话
- 每次生成不同种类的敌人
- traits 仅叙事描述，不影响战斗数值
- 低实力玩家对应低阶妖兽/散修，高实力玩家对应高阶邪修/远古魔物"""


# ---------- mock templates ----------

_MOCK_ENEMY_TEMPLATES = [
    {
        "name": "赤焰妖狐",
        "title": "化形百年的火灵妖兽",
        "category": "妖兽",
        "description": "灌木丛中窜出一只通体赤红的妖狐，三条尾巴燃着幽蓝鬼火。它朝你龇牙低吼，灼热的妖气扑面而来。",
        "stats_ratio": {"hp": 0.6, "atk": 0.8, "defense": 0.5},
        "traits": [{"id": "fire_spirit", "name": "火灵之体", "description": "通体燃烧着妖火", "mechanical": False}],
    },
    {
        "name": "血煞道人",
        "title": "以血入道的邪修",
        "category": "邪修",
        "description": "一个面色苍白的修士挡住了你的去路。他周身缠绕着血色灵气，手中的法器滴着暗红色的液体，嘴角挂着阴森的笑意。",
        "stats_ratio": {"hp": 0.5, "atk": 0.9, "defense": 0.4},
        "traits": [{"id": "blood_arts", "name": "血煞功", "description": "以鲜血为引的邪门功法", "mechanical": False}],
    },
    {
        "name": "噬魂魔蛛",
        "title": "深渊魔气孕育的异种",
        "category": "魔物",
        "description": "巨大的蛛网覆盖了前方的通道。一只漆黑如墨的巨蛛从暗处爬出，八只眼睛泛着诡异的紫光，毒液从獠牙间滴落。",
        "stats_ratio": {"hp": 0.7, "atk": 0.7, "defense": 0.6},
        "traits": [{"id": "venom_fang", "name": "剧毒獠牙", "description": "沾满致命毒液的尖牙", "mechanical": False}],
    },
    {
        "name": "玄冰蟒",
        "title": "千年寒潭中的守护者",
        "category": "灵兽",
        "description": "寒气从地底涌出，一条周身覆盖冰蓝鳞片的巨蟒从深潭中浮现。它的双瞳如同两颗寒星，冰冷的气息让你不由得打了个寒颤。",
        "stats_ratio": {"hp": 0.8, "atk": 0.6, "defense": 0.7},
        "traits": [{"id": "frost_scales", "name": "玄冰鳞甲", "description": "寒气凝结的天然护甲", "mechanical": False}],
    },
    {
        "name": "怨婴",
        "title": "怨气凝聚的厉鬼",
        "category": "鬼修",
        "description": "阴风阵阵中，一个半透明的幼小身影浮现在你面前。它的哭声刺耳却又遥远，空洞的双眼中没有瞳孔，只有无尽的怨恨。",
        "stats_ratio": {"hp": 0.4, "atk": 0.85, "defense": 0.3},
        "traits": [{"id": "ghost_form", "name": "鬼体", "description": "半虚半实的怨灵之体", "mechanical": False}],
    },
    {
        "name": "落魄散修",
        "title": "走投无路的劫道者",
        "category": "散修",
        "description": "一个衣衫褴褛的修士从路旁闪出，手持一把灵气暗淡的飞剑指向你。他眼中满是疯狂与绝望，嘶声道：'留下你的储物袋！'",
        "stats_ratio": {"hp": 0.55, "atk": 0.75, "defense": 0.5},
        "traits": [{"id": "desperate", "name": "穷途末路", "description": "被逼入绝境的修士", "mechanical": False}],
    },
    {
        "name": "石甲傀儡",
        "title": "远古阵法遗留的守卫",
        "category": "魔物",
        "description": "脚下的石板突然震动，一尊布满符文的石像从墙壁中剥离而出。它缓缓转动生锈的关节，空洞的眼眶中亮起暗红色的光芒。",
        "stats_ratio": {"hp": 0.75, "atk": 0.65, "defense": 0.8},
        "traits": [{"id": "stone_body", "name": "岩石之躯", "description": "坚硬的石质身体", "mechanical": False}],
    },
    {
        "name": "碧眼狼王",
        "title": "统率狼群的妖兽首领",
        "category": "妖兽",
        "description": "一声悠长的狼嚎划破夜空。一头体型远超常狼的巨兽从月色中走出，碧绿的双瞳闪烁着灵智的光芒，身后隐约可见数十双绿色的眼睛。",
        "stats_ratio": {"hp": 0.65, "atk": 0.85, "defense": 0.55},
        "traits": [{"id": "pack_leader", "name": "狼王威压", "description": "统率群狼的霸气", "mechanical": False}],
    },
]


# ---------- generation ----------

def generate_enemy(player: Character, mock_mode: bool = False) -> dict:
    if mock_mode:
        return mock_generate_enemy(player)

    player_context = (
        f"玩家角色：{player.name}，气血{player.max_hp}，攻击{player.atk}，防御{player.defense}"
    )
    try:
        response = client.chat.completions.create(
            model=PARSER_MODEL,
            max_tokens=500,
            messages=[
                {"role": "system", "content": ENEMY_SYSTEM},
                {"role": "user", "content": player_context},
            ],
        )
        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        parsed = json.loads(text)
        return _validate_enemy(parsed, player)
    except Exception as e:
        return mock_generate_enemy(player)


def mock_generate_enemy(player: Character) -> dict:
    template = random.choice(_MOCK_ENEMY_TEMPLATES)

    def scaled(ratio):
        return ratio * random.uniform(0.85, 1.15)

    hp = max(10, int(player.max_hp * scaled(template["stats_ratio"]["hp"])))
    atk = max(1, int(player.atk * scaled(template["stats_ratio"]["atk"])))
    defense = max(0, int(player.defense * scaled(template["stats_ratio"]["defense"])))

    return {
        "name": template["name"],
        "title": template["title"],
        "category": template["category"],
        "description": template["description"],
        "stats": {"hp": hp, "atk": atk, "defense": defense},
        "items": {},
        "traits": list(template["traits"]),
    }


def _validate_enemy(parsed: dict, player: Character) -> dict:
    if not isinstance(parsed, dict) or "stats" not in parsed:
        return mock_generate_enemy(player)

    stats = parsed["stats"]
    stats["hp"] = max(10, min(int(player.max_hp * 1.2), int(stats.get("hp", 30))))
    stats["atk"] = max(1, min(int(player.atk * 1.0), int(stats.get("atk", 10))))
    stats["defense"] = max(0, min(int(player.defense * 1.0), int(stats.get("defense", 5))))
    parsed["stats"] = stats

    if not parsed.get("name"):
        parsed["name"] = "无名妖物"
    if not parsed.get("description"):
        parsed["description"] = f"一股危险的气息迎面而来——{parsed['name']}出现在你的面前！"

    parsed.setdefault("title", "")
    parsed.setdefault("category", "妖兽")
    parsed.setdefault("items", {})
    parsed.setdefault("traits", [])

    for t in parsed["traits"]:
        t["mechanical"] = False

    return parsed


def build_enemy(parsed: dict) -> tuple[Character, str]:
    stats = parsed["stats"]
    hp = stats["hp"]

    traits = [
        {"id": t.get("id", "unknown"), "name": t.get("name", ""), "description": t.get("description", "")}
        for t in parsed.get("traits", [])
    ]

    extras = {}
    if parsed.get("title"):
        extras["title"] = parsed["title"]
    if parsed.get("category"):
        extras["category"] = parsed["category"]

    enemy = Character(
        name=parsed.get("name", "无名妖物"),
        hp=hp,
        max_hp=hp,
        atk=stats["atk"],
        defense=stats["defense"],
        items={},
        status=[],
        traits=traits,
        extras=extras,
    )

    description = parsed.get("description", f"{enemy.name}出现在你面前！")
    return enemy, description
