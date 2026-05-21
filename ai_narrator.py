import json
from openai import OpenAI
from config import API_KEY, BASE_URL, NARRATOR_MODEL

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

NARRATOR_SYSTEM = """你是一个修仙世界RPG的叙事者。将游戏引擎的JSON结果转化为沉浸式中文叙述。

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
- 使用修仙世界的语言风格：灵气、真元、法力、气血、神识、道韵等

特殊动作处理：
- invalid: 玩家做了与战斗无关的事，浪费了一回合。创造性地描述为什么没效果，可以幽默调侃
- dynamic: 玩家使用了自创招式，template_name字段是招式名。根据结果(命中/miss/伤害)生动描述这个独特招式
- rest: 短暂休息，恢复了少量HP
- taunt: 嘲讽敌人，它被激怒了
- examine: 仔细观察敌人，获得情报
- heavy_attack: 全力重击，可能命中可能落空，命中时威力极大
- quick_attack: 快速连击，灵活迅猛
- counter: 摆好反击架势，伺机而动
- charge: 凝聚力量，为下次攻击蓄力
- dodge: 灵活走位，准备闪避
- focus: 屏息凝神，寻找破绽
- battle_cry: 气势爆发，大声怒吼
- steal: 趁乱摸索敌人口袋
- negotiate: 尝试用言语解决问题
- surrender: 放下武器认输
- pray: 向神明祈祷，结果不可预知（治愈/神罚/沉默/反噬）
- kick: 近身飞踢，可能让敌人眩晕

敌人回合特殊情况：
- 若敌人stunned（眩晕），描述它摇摇晃晃无法行动
- 若敌人攻击被dodged（闪避），描述玩家灵巧地避开
- 若触发counter_triggered（反击），描述玩家的漂亮反击

风格：
- 第二人称描述玩家（"你"），第三人称描述敌人
- 生动简洁，2-4句话
- 修仙世界的战斗描写：灵力流转、剑气纵横、妖气翻涌
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
        lines.append(f"你发起攻击！{crit}造成 {player_result['damage']} 点伤害。")
        lines.append(f"{player_result['target']} HP: {player_result['target_hp']}/{player_result['target_max_hp']}")
        if not player_result.get("target_alive"):
            lines.append(f"{player_result['target']} 倒下了！")

    elif action == "heavy_attack":
        if player_result.get("miss"):
            lines.append(f"你全力挥出重击——但扑了个空！")
        else:
            crit = "暴击！" if player_result.get("critical") else ""
            lines.append(f"你全力劈下！{crit}重击造成 {player_result['damage']} 点巨额伤害！")
            lines.append(f"{player_result['target']} HP: {player_result['target_hp']}/{player_result['target_max_hp']}")
            if not player_result.get("target_alive"):
                lines.append(f"一击毙命！{player_result['target']} 倒下了！")

    elif action == "quick_attack":
        hits = player_result.get("hits", [])
        desc = "、".join([f"{h['damage']}" + ("(暴击)" if h.get("critical") else "") for h in hits])
        lines.append(f"你迅速连击！两次攻击分别造成 {desc} 点伤害，共 {player_result['damage']} 点！")
        lines.append(f"{player_result['target']} HP: {player_result['target_hp']}/{player_result['target_max_hp']}")
        if not player_result.get("target_alive"):
            lines.append(f"{player_result['target']} 倒下了！")

    elif action == "kick":
        stun = "敌人被踢得头晕眼花！" if player_result.get("stunned") else ""
        lines.append(f"你一脚踢出！造成 {player_result['damage']} 点伤害。{stun}")
        lines.append(f"{player_result['target']} HP: {player_result['target_hp']}/{player_result['target_max_hp']}")
        if not player_result.get("target_alive"):
            lines.append(f"{player_result['target']} 倒下了！")

    elif action == "defend":
        lines.append("你摆出防御姿态，准备迎接下一次攻击。")

    elif action == "counter":
        lines.append("你沉肩低身，摆出反击架势——来吧，谁先出手谁吃亏。")

    elif action == "dodge":
        lines.append("你轻移脚步，准备闪避下一次攻击。")

    elif action == "charge":
        lines.append("你深吸一口气，力量在体内凝聚... 下次攻击将势不可挡！")

    elif action == "focus":
        lines.append("你屏息凝神，目光如鹰，锁定敌人的破绽... 下次攻击暴击率大幅提升！")

    elif action == "battle_cry":
        lines.append("你发出震耳欲聋的战吼！气势暴涨，下次攻击力量将更加强大！")

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

    elif action == "rest":
        heal = player_result.get("heal", 0)
        lines.append(f"你靠在岩壁上短暂地喘息，恢复了 {heal} 点HP。")
        lines.append(f"你的 HP: {player_result.get('actor_hp')}/{player_result.get('actor_max_hp')}")

    elif action == "taunt":
        target = player_result.get("target", "敌人")
        lines.append(f"你朝{target}大声嘲讽！它被激怒了，动作变得急躁。")
        lines.append(f"效果：{target}下次攻击力降低。")

    elif action == "examine":
        target = player_result.get("target", "敌人")
        condition = player_result.get("condition", "未知")
        lines.append(f"你仔细打量着{target}——它看起来{condition}。")
        lines.append(f"HP: {player_result.get('target_hp')}/{player_result.get('target_max_hp')} | ATK: {player_result.get('target_atk')} | DEF: {player_result.get('target_def')}")

    elif action == "steal":
        if player_result.get("success"):
            item_name = player_result.get("item_name", "某物")
            if player_result.get("item") == "bomb":
                lines.append(f"你灵巧地从敌人身上摸到了一颗{item_name}——轰！炸了它 {player_result['damage']} 点伤害！")
            else:
                lines.append(f"你趁敌人不注意，顺走了一瓶{item_name}！（现有 {player_result.get('remaining')} 瓶）")
        else:
            lines.append("你试图偷窃，但手滑了——什么也没摸到。")

    elif action == "negotiate":
        if player_result.get("success"):
            lines.append("出乎意料！敌人被你的言辞说服，放下了武器。")
        else:
            lines.append("你试图和敌人讲道理，但它对你的提议嗤之以鼻。")

    elif action == "surrender":
        lines.append("你放下武器，低下了头... 战斗以失败告终。")

    elif action == "pray":
        outcome = player_result.get("outcome")
        if outcome == "heal":
            lines.append(f"神圣之光降临！你感受到温暖的力量，恢复了 {player_result.get('heal')} 点HP。")
        elif outcome == "smite":
            lines.append(f"天降神罚！一道金色闪电击中了{player_result.get('target')}，造成 {player_result.get('damage')} 点神圣伤害！")
        elif outcome == "nothing":
            lines.append("你虔诚祈祷... 但一片寂静。看来神明今天不在。")
        elif outcome == "backfire":
            lines.append(f"你的祈祷似乎触怒了某种力量... 反噬降临，你受到 {player_result.get('damage')} 点伤害！")

    elif action == "invalid":
        original = player_result.get("original", "")
        lines.append(f"你想了想「{original}」——但这不是战斗中该做的事。")
        lines.append("你犹豫不决，白白浪费了一个回合！")

    elif action == "dynamic":
        name = player_result.get("template_name", "未知招式")
        if player_result.get("miss"):
            lines.append(f"你使出「{name}」——但没有命中！")
        elif player_result.get("damage"):
            crit = "暴击！" if player_result.get("critical") else ""
            lines.append(f"你使出「{name}」！{crit}造成 {player_result['damage']} 点伤害。")
            if player_result.get("target"):
                lines.append(f"{player_result['target']} HP: {player_result.get('target_hp', '?')}/{player_result.get('target_max_hp', '?')}")
            if not player_result.get("target_alive", True):
                lines.append(f"{player_result.get('target', '敌人')} 倒下了！")
        elif player_result.get("heal"):
            lines.append(f"你使出「{name}」，恢复了 {player_result['heal']} 点气血。")
        else:
            lines.append(f"你使出「{name}」！")

    # --- enemy result ---
    if enemy_result:
        e_action = enemy_result.get("action")
        actor = enemy_result.get("actor", "敌人")

        if e_action == "stunned":
            lines.append(f"\n{actor} 头晕目眩，无法行动！")
        elif e_action == "attack":
            if enemy_result.get("dodged"):
                lines.append(f"\n{actor} 向你攻击——但你灵巧地侧身闪过！")
            else:
                crit = "暴击！" if enemy_result.get("critical") else ""
                lines.append(f"\n{actor} 向你攻击！{crit}造成 {enemy_result['damage']} 点伤害。")
                lines.append(f"你的 HP: {enemy_result['target_hp']}/{enemy_result['target_max_hp']}")
                if not enemy_result.get("target_alive"):
                    lines.append("你倒下了...")

            if enemy_result.get("counter_triggered"):
                lines.append(f"你抓住破绽反击！对{actor}造成 {enemy_result['counter_damage']} 点伤害！")
                lines.append(f"{actor} HP: {enemy_result['counter_target_hp']}")
        elif e_action == "defend":
            lines.append(f"\n{actor} 摆出了防御姿态。")

    return "\n".join(lines)
