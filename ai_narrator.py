import json
from openai import OpenAI
from config import API_KEY, BASE_URL, NARRATOR_MODEL

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

NARRATOR_SYSTEM = """你是一个暗黑奇幻RPG的叙事者。将游戏引擎的JSON结果转化为沉浸式中文叙述。

你会收到三部分信息：
1. 玩家的原始输入（他们说了什么）
2. 玩家行动的引擎结果（JSON）
3. 敌人行动的引擎结果（JSON，可能为空）

核心规则：
- 战斗数值、胜负、伤害等一切结果必须严格以引擎JSON为准，绝不编造
- 但叙述的语气、氛围、细节描写应该回应玩家原始输入的态度和情感
  - 玩家狂妄？叙述可以配合渲染气势，或用结果反衬（吹了牛但只砍了一点血）
  - 玩家谨慎？叙述体现小心翼翼的战斗风格
  - 玩家说了搞笑/离谱的话？旁白可以简短回应，但不喧宾夺主

风格：
- 第二人称描述玩家（"你"），第三人称描述敌人
- 生动简洁，2-4句话
- 战斗有打击感和画面感
- 末尾用【】显示关键数值"""


def narrate(player_result: dict, enemy_result: dict = None, context: dict = None, user_input: str = "") -> str:
    try:
        content = ""
        if user_input:
            content += f"玩家原始输入：「{user_input}」\n"
        content += f"玩家行动结果：{json.dumps(player_result, ensure_ascii=False)}"
        if enemy_result:
            content += (
                f"\n敌人行动结果：{json.dumps(enemy_result, ensure_ascii=False)}"
            )
        if context:
            content += f"\n当前状态：{json.dumps(context, ensure_ascii=False)}"

        response = client.chat.completions.create(
            model=NARRATOR_MODEL,
            max_tokens=400,
            messages=[
                {"role": "system", "content": NARRATOR_SYSTEM},
                {"role": "user", "content": content},
            ],
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"[叙事生成失败: {e}]\n{_fallback_text(player_result, enemy_result)}"


def mock_narrate(player_result: dict, enemy_result: dict = None, **_) -> str:
    return _fallback_text(player_result, enemy_result)


def _fallback_text(player_result: dict, enemy_result: dict = None) -> str:
    lines = []

    action = player_result.get("action")
    if action == "attack":
        crit = "暴击！" if player_result.get("critical") else ""
        lines.append(
            f"你发起攻击！{crit}造成 {player_result['damage']} 点伤害。"
        )
        lines.append(
            f"{player_result['target']} HP: {player_result['target_hp']}/{player_result['target_max_hp']}"
        )
        if not player_result.get("target_alive"):
            lines.append(f"{player_result['target']} 倒下了！")
    elif action == "defend":
        lines.append("你摆出防御姿态，准备迎接下一次攻击。")
    elif action == "use_item":
        if player_result.get("success"):
            lines.append(
                f"你使用了治疗药水，恢复 {player_result['heal']} 点HP。"
                f"（剩余 {player_result['remaining']} 瓶）"
            )
        else:
            lines.append(f"使用失败：{player_result.get('reason', '未知原因')}")
    elif action == "flee":
        if player_result.get("success"):
            lines.append("你成功逃离了战斗！")
        else:
            lines.append("你试图逃跑，但失败了！")

    if enemy_result:
        e_action = enemy_result.get("action")
        actor = enemy_result.get("actor", "敌人")
        if e_action == "attack":
            crit = "暴击！" if enemy_result.get("critical") else ""
            lines.append(
                f"\n{actor} 向你攻击！{crit}造成 {enemy_result['damage']} 点伤害。"
            )
            lines.append(
                f"你的 HP: {enemy_result['target_hp']}/{enemy_result['target_max_hp']}"
            )
            if not enemy_result.get("target_alive"):
                lines.append("你倒下了...")
        elif e_action == "defend":
            lines.append(f"\n{actor} 摆出了防御姿态。")

    return "\n".join(lines)
