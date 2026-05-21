import json
from openai import OpenAI
from config import API_KEY, BASE_URL, PARSER_MODEL

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

PARSER_SYSTEM = """你是一个游戏指令解析器。将玩家的自然语言输入解析为JSON动作。

可用动作（共20种）：

攻击类：
1. attack - 普通攻击
2. heavy_attack - 重击/猛砍/全力一击（高伤害但可能落空）
3. quick_attack - 连击/快速攻击/左右开弓（打两下，每下伤害较低）
4. kick - 踢/飞踢/扫腿（低伤害但可能眩晕敌人）

防御类：
5. defend - 防御/格挡（下次受伤减半）
6. counter - 反击/架势/见招拆招（被攻击时自动反击）
7. dodge - 闪避/躲/侧身（50%概率闪避敌人攻击）

增益类：
8. charge - 蓄力/聚气/积蓄力量（下次攻击伤害翻倍）
9. focus - 集中/瞄准/看准弱点（下次攻击暴击率提升至50%）
10. battle_cry - 战吼/呐喊/鼓舞（下次攻击ATK+5）

恢复类：
11. use_item - 使用物品（需指定item字段）
12. rest - 休息/睡觉/打盹/喘息（恢复少量HP）
13. pray - 祈祷/祈求/拜神（随机效果：治愈/神罚/无效/反噬）

社交类：
14. taunt - 嘲讽/挑衅/激怒/辱骂敌人（降低敌人下次攻击力）
15. examine - 观察/审视/打量/查看敌人（获取敌人详情）
16. negotiate - 谈判/说服/交涉/讲道理（可能让敌人投降）
17. steal - 偷窃/摸口袋/顺手牵羊（可能偷到物品或炸弹）

退出类：
18. flee - 逃跑/撤退（30%成功率）
19. surrender - 投降/放弃/认输（直接战败）

兜底：
20. invalid - 玩家输入确实与任何战斗行动无关时使用

## 动态招式（当以上20种都不合适时）

如果玩家描述了一个合理的战斗动作，但不属于以上20种，你可以创建一个动态招式模板：

{"action": "dynamic", "template": {
  "name": "招式名",
  "description": "简短描述",
  "type": "attack|defend|buff|heal|debuff|utility",
  "power": 0.9,          // 攻击倍率 (0.1~2.5, 仅attack类型)
  "accuracy": 0.85,      // 命中率 (0.2~1.0)
  "crit_bonus": 0.0,     // 额外暴击率 (0.0~0.35)
  "self_damage": 0.0,    // 反噬（自伤比例 0.0~0.3）
  "heal_power": 0.0,     // 恢复比例 (0.0~0.3, 仅heal类型，基于最大HP)
  "defense_mult": 0.0,   // 减伤倍率 (0.0~0.8, 仅defend类型)
  "lifesteal": 0.0,      // 吸血比例 (0.0~0.3, 按伤害百分比回血)
  "status_apply": "",    // 给敌人施加状态: "taunted" 或 "stunned"
  "status_self": "",     // 给自己施加状态: "defending"/"charged"/"focused"/"battle_cry"/"countering"/"dodging"
  "cost_hp": 0           // HP消耗 (0~30)
}}

动态招式设计原则：
- 强力招式必须有代价（低命中率、自伤、HP消耗）
- power > 1.5 时，accuracy 应低于 0.7 或有 self_damage
- heal_power > 0.2 时，应有 cost_hp
- 不要创造没有任何风险/代价的强力招式
- 只有确实不属于20种标准动作时才使用动态招式
- 玩家说的话明显与战斗无关（聊天、问天气等）依然用 invalid

输出格式（只输出纯JSON，无其他文字）：
- 普通攻击：{"action": "attack"}
- 重击：{"action": "heavy_attack"}
- 连击：{"action": "quick_attack"}
- 踢击：{"action": "kick"}
- 防御：{"action": "defend"}
- 反击：{"action": "counter"}
- 闪避：{"action": "dodge"}
- 蓄力：{"action": "charge"}
- 集中：{"action": "focus"}
- 战吼：{"action": "battle_cry"}
- 使用物品：{"action": "use_item", "item": "healing_potion"}
- 休息：{"action": "rest"}
- 祈祷：{"action": "pray"}
- 嘲讽：{"action": "taunt"}
- 观察：{"action": "examine"}
- 谈判：{"action": "negotiate"}
- 偷窃：{"action": "steal"}
- 逃跑：{"action": "flee"}
- 投降：{"action": "surrender"}
- 无效：{"action": "invalid", "original": "玩家的原话"}
- 动态：{"action": "dynamic", "template": {...}}

物品ID：治疗药水 = "healing_potion"

规则：
- 只输出纯JSON
- 优先匹配最合理的标准动作（20种）
- 如果是合理的战斗动作但不在标准列表中，创建动态招式
- 只有当输入确实无法映射到任何战斗行动时，才使用invalid
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

    # heavy attack (check before normal attack — more specific keywords first)
    if any(w in t for w in ["重击", "猛砍", "全力", "狠狠", "用力", "heavy"]):
        return {"action": "heavy_attack"}

    # quick attack
    if any(w in t for w in ["连击", "快速", "连续", "左右", "双击", "quick", "combo"]):
        return {"action": "quick_attack"}

    # kick
    if any(w in t for w in ["踢", "飞踢", "扫腿", "蹬", "kick"]):
        return {"action": "kick"}

    # counter (must be before normal attack — "反击" contains "击")
    if any(w in t for w in ["反击", "反攻", "以牙还牙", "见招拆招", "counter", "parry"]):
        return {"action": "counter"}

    # normal attack
    if any(w in t for w in ["攻击", "打", "砍", "砸", "击", "刺", "捅", "劈", "attack", "hit"]):
        return {"action": "attack"}

    # dodge
    if any(w in t for w in ["闪避", "躲", "闪开", "侧身", "翻滚", "dodge", "evade", "roll"]):
        return {"action": "dodge"}

    # defend
    if any(w in t for w in ["防御", "格挡", "挡", "盾", "defend", "block", "guard"]):
        return {"action": "defend"}

    # charge
    if any(w in t for w in ["蓄力", "聚气", "积蓄", "凝聚", "charge", "power up"]):
        return {"action": "charge"}

    # focus
    if any(w in t for w in ["集中", "瞄准", "专注", "看准", "弱点", "focus", "aim"]):
        return {"action": "focus"}

    # battle cry
    if any(w in t for w in ["战吼", "呐喊", "吼", "鼓舞", "怒吼", "咆哮", "cry", "shout", "roar"]):
        return {"action": "battle_cry"}

    # use item
    if any(w in t for w in ["药", "治疗", "喝", "回血", "heal", "potion"]):
        return {"action": "use_item", "item": "healing_potion"}

    # rest
    if any(w in t for w in ["睡", "休息", "歇", "打盹", "喘", "rest", "sleep"]):
        return {"action": "rest"}

    # pray
    if any(w in t for w in ["祈祷", "祈求", "祷告", "拜", "神", "上帝", "pray", "god"]):
        return {"action": "pray"}

    # taunt
    if any(w in t for w in ["嘲讽", "挑衅", "骂", "激怒", "侮辱", "蠢", "丑", "笨", "废物", "垃圾", "taunt"]):
        return {"action": "taunt"}

    # examine
    if any(w in t for w in ["观察", "查看", "审视", "打量", "看看", "端详", "examine", "look"]):
        return {"action": "examine"}

    # negotiate
    if any(w in t for w in ["谈判", "说服", "讲道理", "交涉", "商量", "求情", "和平", "negotiate", "talk"]):
        return {"action": "negotiate"}

    # steal
    if any(w in t for w in ["偷", "摸", "顺手", "窃", "steal", "pickpocket"]):
        return {"action": "steal"}

    # flee
    if any(w in t for w in ["逃", "跑", "撤", "flee", "run", "escape"]):
        return {"action": "flee"}

    # surrender
    if any(w in t for w in ["投降", "认输", "放弃", "算了", "不打了", "surrender", "give up"]):
        return {"action": "surrender"}

    # dynamic fallback: if input looks like a combat action (contains action verbs)
    action_hints = ["斩", "劈", "射", "咬", "撞", "吸", "吹", "烧", "冻", "雷",
                    "电", "火", "冰", "风", "毒", "爪", "尾", "翼", "吞", "喷",
                    "术", "法", "功", "掌", "拳", "指", "鞭", "锤", "枪", "弓",
                    "箭", "波", "气", "灵", "咒", "阵", "符", "丹", "技", "刀",
                    "剑", "罩", "盾", "甲", "暗", "影", "血", "魂", "噬", "裂",
                    "碎", "爆", "闪", "飞", "旋", "震", "破", "穿", "刺"]
    if any(w in t for w in action_hints):
        tmpl_type, power, accuracy, crit, self_dmg, heal, status_self, lifesteal = _infer_dynamic_type(t)
        return {
            "action": "dynamic",
            "template": {
                "name": user_input[:10],
                "description": user_input,
                "type": tmpl_type,
                "power": power,
                "accuracy": accuracy,
                "crit_bonus": crit,
                "self_damage": self_dmg,
                "heal_power": heal,
                "defense_mult": 0.5 if tmpl_type == "defend" else 0.0,
                "lifesteal": lifesteal,
                "status_apply": "",
                "status_self": status_self,
                "cost_hp": 0,
            },
        }

    return {"action": "invalid", "original": user_input}


def _infer_dynamic_type(text: str) -> tuple:
    """Infer template type from Chinese keywords. Returns (type, power, accuracy, crit, self_dmg, heal, status_self, lifesteal)."""
    # heal-like
    heal_words = ["吸", "回", "愈", "疗", "补", "养"]
    if any(w in text for w in heal_words) and not any(w in text for w in ["吸血"]):
        return ("heal", 0.0, 1.0, 0.0, 0.0, 0.15, "", 0.0)

    # absorb attacks (吸血 = attack + lifesteal)
    if "吸血" in text or "吸" in text:
        return ("attack", 0.8, 0.85, 0.0, 0.0, 0.0, "", 0.25)

    # defend-like
    defend_words = ["罩", "盾", "甲", "护", "挡", "壁"]
    if any(w in text for w in defend_words):
        return ("defend", 0.0, 1.0, 0.0, 0.0, 0.0, "defending", 0.0)

    # buff-like
    buff_words = ["聚", "凝", "蓄", "运", "修", "练", "悟"]
    if any(w in text for w in buff_words):
        return ("buff", 0.0, 1.0, 0.0, 0.0, 0.0, "charged", 0.0)

    # debuff-like
    debuff_words = ["毒", "咒", "封", "禁", "惑", "乱"]
    if any(w in text for w in debuff_words):
        return ("debuff", 0.0, 0.9, 0.0, 0.0, 0.0, "", 0.0)

    # high-power risky attacks
    risky_words = ["爆", "噬", "魂", "血", "裂", "碎"]
    if any(w in text for w in risky_words):
        return ("attack", 1.8, 0.65, 0.10, 0.10, 0.0, "", 0.0)

    # precision attacks
    precision_words = ["指", "穿", "刺", "暗", "影"]
    if any(w in text for w in precision_words):
        return ("attack", 0.9, 0.90, 0.15, 0.0, 0.0, "", 0.0)

    # default: normal attack-like
    return ("attack", 1.0, 0.80, 0.05, 0.0, 0.0, "", 0.0)
