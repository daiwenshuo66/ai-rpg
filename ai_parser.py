import json
from openai import OpenAI
from config import API_KEY, BASE_URL, PARSER_MODEL

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

PARSER_SYSTEM = """你是一个游戏指令解析器。将玩家的自然语言输入解析为JSON动作。

可用动作：
1. attack - 攻击敌人
2. defend - 防御（下次受伤减半）
3. use_item - 使用物品（需指定item字段）
4. flee - 逃跑
5. rest - 休息/睡觉/打盹/歇一会（恢复少量HP）
6. taunt - 嘲讽/挑衅/激怒/辱骂敌人
7. examine - 观察/审视/打量/查看敌人
8. invalid - 玩家输入确实与任何战斗行动无关时使用

输出格式（只输出纯JSON，无其他文字）：
- 攻击：{"action": "attack"}
- 防御：{"action": "defend"}
- 使用物品：{"action": "use_item", "item": "healing_potion"}
- 逃跑：{"action": "flee"}
- 休息：{"action": "rest"}
- 嘲讽：{"action": "taunt"}
- 观察：{"action": "examine"}
- 无效：{"action": "invalid", "original": "玩家的原话"}

物品ID：治疗药水 = "healing_potion"

规则：
- 只输出纯JSON
- 优先匹配最合理的战斗行动
- 只有当输入确实无法映射到以上任何战斗行动时，才使用invalid
- invalid时必须在original字段保留玩家原话"""


def parse_input(user_input: str, context: dict) -> dict:
    try:
        response = client.chat.completions.create(
            model=PARSER_MODEL,
            max_tokens=150,
            messages=[
                {"role": "system", "content": PARSER_SYSTEM},
                {
                    "role": "user",
                    "content": f"游戏状态：{json.dumps(context, ensure_ascii=False)}\n\n玩家输入：{user_input}",
                },
            ],
        )
        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception as e:
        print(f"  [解析异常: {e}，标记为无效动作]")
        return {"action": "invalid", "original": user_input}


def mock_parse(user_input: str) -> dict:
    t = user_input.lower()
    if any(w in t for w in ["攻击", "打", "砍", "砸", "击", "刺", "attack", "hit"]):
        return {"action": "attack"}
    if any(w in t for w in ["防御", "格挡", "挡", "盾", "defend", "block", "guard"]):
        return {"action": "defend"}
    if any(w in t for w in ["药", "治疗", "喝", "回血", "heal", "potion"]):
        return {"action": "use_item", "item": "healing_potion"}
    if any(w in t for w in ["逃", "跑", "撤", "flee", "run", "escape"]):
        return {"action": "flee"}
    if any(w in t for w in ["睡", "休息", "歇", "打盹", "rest", "sleep"]):
        return {"action": "rest"}
    if any(w in t for w in ["嘲讽", "挑衅", "骂", "激怒", "侮辱", "蠢", "丑", "笨", "废物", "taunt", "mock"]):
        return {"action": "taunt"}
    if any(w in t for w in ["观察", "查看", "审视", "打量", "看看", "examine", "look"]):
        return {"action": "examine"}
    return {"action": "invalid", "original": user_input}
