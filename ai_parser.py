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

输出格式（只输出纯JSON，无其他文字）：
- 攻击：{"action": "attack"}
- 防御：{"action": "defend"}
- 使用物品：{"action": "use_item", "item": "healing_potion"}
- 逃跑：{"action": "flee"}

物品ID：治疗药水 = "healing_potion"

规则：
- 只输出纯JSON
- 输入不明确时选最合理的动作
- 完全无法理解时输出 {"action": "attack"}"""


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
        print(f"  [解析异常: {e}，默认执行攻击]")
        return {"action": "attack"}


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
    return {"action": "attack"}
