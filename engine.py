import random
from game_state import GameState


def process_action(action: dict, state: GameState) -> dict:
    action_type = action.get("action")

    if action_type == "dynamic":
        return _process_dynamic(action, state)

    handlers = {
        "attack": _process_attack,
        "defend": _process_defend,
        "use_item": _process_use_item,
        "flee": _process_flee,
        "rest": _process_rest,
        "taunt": _process_taunt,
        "examine": _process_examine,
        "heavy_attack": _process_heavy_attack,
        "quick_attack": _process_quick_attack,
        "counter": _process_counter,
        "charge": _process_charge,
        "dodge": _process_dodge,
        "focus": _process_focus,
        "battle_cry": _process_battle_cry,
        "steal": _process_steal,
        "negotiate": _process_negotiate,
        "surrender": _process_surrender,
        "pray": _process_pray,
        "kick": _process_kick,
        "invalid": _process_invalid,
    }
    handler = handlers.get(action_type)
    if handler:
        return handler(action, state)
    return _process_invalid(action, state)


# ---------- buff helpers ----------

def _consume_attack_buffs(attacker, trace):
    atk_bonus = 0
    crit_rate = 0.15
    dmg_mult = 1.0

    if "battle_cry" in attacker.status:
        atk_bonus = 5
        attacker.status.remove("battle_cry")
        trace.append(f"战吼加持: ATK +5")

    if "focused" in attacker.status:
        crit_rate = 0.50
        attacker.status.remove("focused")
        trace.append(f"集中精神: 暴击率 → 50%")

    if "charged" in attacker.status:
        dmg_mult = 2.0
        attacker.status.remove("charged")
        trace.append(f"蓄力释放: 伤害 x2")

    return atk_bonus, crit_rate, dmg_mult


def _apply_damage(base_damage, dmg_mult, defender, trace):
    if dmg_mult != 1.0:
        before = base_damage
        base_damage = int(base_damage * dmg_mult)
        trace.append(f"倍率加成: {before} x{dmg_mult:.1f} = {base_damage}")

    if "defending" in defender.status:
        before = base_damage
        base_damage = max(1, base_damage // 2)
        defender.status.remove("defending")
        trace.append(f"目标防御中: {before} ÷2 = {base_damage}")

    base_damage = max(1, base_damage)
    hp_before = defender.hp
    defender.hp = max(0, defender.hp - base_damage)
    trace.append(f"最终伤害: {base_damage}")
    trace.append(f"{defender.name} HP: {hp_before} → {defender.hp}")
    return base_damage


def _check_kill(attacker, defender, state, result):
    if defender.hp <= 0:
        state.combat_active = False
        result["combat_end"] = True
        result["winner"] = attacker.name


# ---------- player actions ----------

def _process_attack(action: dict, state: GameState) -> dict:
    attacker = state.player
    defender = state.enemy
    trace = []

    trace.append(f"{attacker.name} 攻击 → {defender.name}")
    atk_bonus, crit_rate, dmg_mult = _consume_attack_buffs(attacker, trace)

    atk = attacker.atk + atk_bonus
    raw = atk - defender.defense // 2
    trace.append(f"基础伤害: ATK({atk}) - DEF({defender.defense})÷2 = {raw}")

    roll = random.randint(-3, 3)
    base_damage = max(1, raw + roll)
    trace.append(f"随机浮动: {roll:+d} → {base_damage}")

    crit_roll = random.random()
    is_critical = crit_roll < crit_rate
    trace.append(f"暴击判定: {crit_roll:.2f} (需<{crit_rate:.2f}) → {'暴击!' if is_critical else '未暴击'}")
    if is_critical:
        before = base_damage
        base_damage = int(base_damage * 1.5)
        trace.append(f"暴击加成: {before} x1.5 = {base_damage}")

    final = _apply_damage(base_damage, dmg_mult, defender, trace)

    result = {
        "action": "attack",
        "success": True,
        "damage": final,
        "critical": is_critical,
        "target": defender.name,
        "target_hp": defender.hp,
        "target_max_hp": defender.max_hp,
        "target_alive": defender.hp > 0,
        "_trace": trace,
    }
    _check_kill(attacker, defender, state, result)
    return result


def _process_defend(action: dict, state: GameState) -> dict:
    trace = []
    trace.append(f"{state.player.name} 进入防御姿态")
    trace.append(f"效果: 下次受到的伤害减半")
    if "defending" not in state.player.status:
        state.player.status.append("defending")
    return {
        "action": "defend",
        "success": True,
        "actor": state.player.name,
        "effect": "next_damage_halved",
        "actor_hp": state.player.hp,
        "actor_max_hp": state.player.max_hp,
        "_trace": trace,
    }


def _process_use_item(action: dict, state: GameState) -> dict:
    item = action.get("item", "")
    trace = []

    if item == "healing_potion" and state.player.items.get("healing_potion", 0) > 0:
        trace.append(f"使用物品: 治疗药水")
        heal = random.randint(20, 30)
        trace.append(f"恢复量: random(20~30) = {heal}")
        hp_before = state.player.hp
        state.player.hp = min(state.player.max_hp, state.player.hp + heal)
        actual_heal = state.player.hp - hp_before
        trace.append(f"{state.player.name} HP: {hp_before} +{actual_heal} → {state.player.hp}/{state.player.max_hp}")
        state.player.items["healing_potion"] -= 1
        remaining = state.player.items["healing_potion"]
        trace.append(f"剩余药水: {remaining} 瓶")
        return {
            "action": "use_item",
            "success": True,
            "item": "healing_potion",
            "heal": actual_heal,
            "actor_hp": state.player.hp,
            "actor_max_hp": state.player.max_hp,
            "remaining": remaining,
            "_trace": trace,
        }

    trace.append(f"使用物品: {item or '?'}")
    trace.append(f"失败: {'背包中没有该物品' if item else '未指定物品'}")
    return {
        "action": "use_item",
        "success": False,
        "reason": f"没有 {item}" if item else "未指定物品",
        "_trace": trace,
    }


def _process_flee(action: dict, state: GameState) -> dict:
    trace = []
    trace.append(f"{state.player.name} 尝试逃跑")
    roll = random.random()
    success = roll < 0.3
    trace.append(f"逃跑判定: {roll:.2f} (需<0.30) → {'成功!' if success else '失败'}")
    if success:
        state.combat_active = False
        return {"action": "flee", "success": True, "combat_end": True, "_trace": trace}
    return {"action": "flee", "success": False, "_trace": trace}


def _process_rest(action: dict, state: GameState) -> dict:
    trace = []
    trace.append(f"{state.player.name} 选择休息")
    heal = random.randint(5, 10)
    trace.append(f"恢复量: random(5~10) = {heal}")
    hp_before = state.player.hp
    state.player.hp = min(state.player.max_hp, state.player.hp + heal)
    actual_heal = state.player.hp - hp_before
    trace.append(f"{state.player.name} HP: {hp_before} +{actual_heal} → {state.player.hp}/{state.player.max_hp}")
    return {
        "action": "rest",
        "success": True,
        "heal": actual_heal,
        "actor_hp": state.player.hp,
        "actor_max_hp": state.player.max_hp,
        "_trace": trace,
    }


def _process_taunt(action: dict, state: GameState) -> dict:
    trace = []
    trace.append(f"{state.player.name} 嘲讽 → {state.enemy.name}")
    if "taunted" not in state.enemy.status:
        state.enemy.status.append("taunted")
    trace.append(f"效果: {state.enemy.name} 下次攻击力 -3")
    return {
        "action": "taunt",
        "success": True,
        "target": state.enemy.name,
        "effect": "next_attack_weakened",
        "_trace": trace,
    }


def _process_examine(action: dict, state: GameState) -> dict:
    enemy = state.enemy
    trace = []
    trace.append(f"{state.player.name} 仔细观察 {enemy.name}")
    hp_ratio = enemy.hp / enemy.max_hp
    if hp_ratio > 0.7:
        condition = "状态良好"
    elif hp_ratio > 0.3:
        condition = "伤痕累累"
    else:
        condition = "摇摇欲坠"
    trace.append(f"观察结果: HP {enemy.hp}/{enemy.max_hp} ({hp_ratio:.0%}), ATK {enemy.atk}, DEF {enemy.defense}")
    trace.append(f"状态判断: {condition}")
    return {
        "action": "examine",
        "success": True,
        "target": enemy.name,
        "target_hp": enemy.hp,
        "target_max_hp": enemy.max_hp,
        "target_atk": enemy.atk,
        "target_def": enemy.defense,
        "condition": condition,
        "_trace": trace,
    }


def _process_heavy_attack(action: dict, state: GameState) -> dict:
    attacker = state.player
    defender = state.enemy
    trace = []

    trace.append(f"{attacker.name} 发动重击 → {defender.name}")
    atk_bonus, crit_rate, dmg_mult = _consume_attack_buffs(attacker, trace)

    miss_roll = random.random()
    trace.append(f"命中判定: {miss_roll:.2f} (需≥0.35) → {'命中!' if miss_roll >= 0.35 else 'MISS!'}")
    if miss_roll < 0.35:
        return {
            "action": "heavy_attack",
            "success": False,
            "miss": True,
            "target": defender.name,
            "_trace": trace,
        }

    atk = attacker.atk + atk_bonus
    raw = atk - defender.defense // 2
    base_damage = max(1, raw + random.randint(-2, 4))
    trace.append(f"重击伤害: ATK({atk}) - DEF÷2 + 浮动 = {base_damage}")

    crit_roll = random.random()
    is_critical = crit_roll < crit_rate
    trace.append(f"暴击判定: {crit_roll:.2f} (需<{crit_rate:.2f}) → {'暴击!' if is_critical else '未暴击'}")
    if is_critical:
        before = base_damage
        base_damage = int(base_damage * 1.5)
        trace.append(f"暴击加成: {before} x1.5 = {base_damage}")

    base_damage = int(base_damage * 1.8)
    trace.append(f"重击倍率: x1.8 → {base_damage}")

    final = _apply_damage(base_damage, dmg_mult, defender, trace)

    result = {
        "action": "heavy_attack",
        "success": True,
        "damage": final,
        "critical": is_critical,
        "target": defender.name,
        "target_hp": defender.hp,
        "target_max_hp": defender.max_hp,
        "target_alive": defender.hp > 0,
        "_trace": trace,
    }
    _check_kill(attacker, defender, state, result)
    return result


def _process_quick_attack(action: dict, state: GameState) -> dict:
    attacker = state.player
    defender = state.enemy
    trace = []

    trace.append(f"{attacker.name} 发动连击 → {defender.name}")
    atk_bonus, crit_rate, dmg_mult = _consume_attack_buffs(attacker, trace)

    atk = attacker.atk + atk_bonus
    total_damage = 0
    hits = []

    for i in range(2):
        if defender.hp <= 0:
            break
        raw = int(atk * 0.6) - defender.defense // 2
        hit_dmg = max(1, raw + random.randint(-2, 2))

        crit_roll = random.random()
        is_crit = crit_roll < crit_rate
        if is_crit:
            hit_dmg = int(hit_dmg * 1.5)

        if dmg_mult != 1.0:
            hit_dmg = int(hit_dmg * dmg_mult)

        hit_dmg = max(1, hit_dmg)
        defender.hp = max(0, defender.hp - hit_dmg)
        total_damage += hit_dmg
        hits.append({"damage": hit_dmg, "critical": is_crit})
        trace.append(f"第{i+1}击: {hit_dmg} {'暴击!' if is_crit else ''}")

    trace.append(f"总伤害: {total_damage}")
    trace.append(f"{defender.name} HP: → {defender.hp}/{defender.max_hp}")

    result = {
        "action": "quick_attack",
        "success": True,
        "damage": total_damage,
        "hits": hits,
        "target": defender.name,
        "target_hp": defender.hp,
        "target_max_hp": defender.max_hp,
        "target_alive": defender.hp > 0,
        "_trace": trace,
    }
    _check_kill(attacker, defender, state, result)
    return result


def _process_counter(action: dict, state: GameState) -> dict:
    trace = []
    trace.append(f"{state.player.name} 进入反击姿态")
    trace.append(f"效果: 若本回合受到攻击，将自动反击")
    if "countering" not in state.player.status:
        state.player.status.append("countering")
    return {
        "action": "counter",
        "success": True,
        "actor": state.player.name,
        "effect": "will_counterattack",
        "actor_hp": state.player.hp,
        "actor_max_hp": state.player.max_hp,
        "_trace": trace,
    }


def _process_charge(action: dict, state: GameState) -> dict:
    trace = []
    trace.append(f"{state.player.name} 开始蓄力")
    trace.append(f"效果: 下次攻击伤害翻倍")
    if "charged" not in state.player.status:
        state.player.status.append("charged")
    return {
        "action": "charge",
        "success": True,
        "actor": state.player.name,
        "effect": "next_attack_doubled",
        "actor_hp": state.player.hp,
        "actor_max_hp": state.player.max_hp,
        "_trace": trace,
    }


def _process_dodge(action: dict, state: GameState) -> dict:
    trace = []
    trace.append(f"{state.player.name} 准备闪避")
    trace.append(f"效果: 50% 概率闪避本回合敌人攻击")
    if "dodging" not in state.player.status:
        state.player.status.append("dodging")
    return {
        "action": "dodge",
        "success": True,
        "actor": state.player.name,
        "effect": "may_dodge_next",
        "actor_hp": state.player.hp,
        "actor_max_hp": state.player.max_hp,
        "_trace": trace,
    }


def _process_focus(action: dict, state: GameState) -> dict:
    trace = []
    trace.append(f"{state.player.name} 集中精神")
    trace.append(f"效果: 下次攻击暴击率提升至 50%")
    if "focused" not in state.player.status:
        state.player.status.append("focused")
    return {
        "action": "focus",
        "success": True,
        "actor": state.player.name,
        "effect": "next_crit_50pct",
        "actor_hp": state.player.hp,
        "actor_max_hp": state.player.max_hp,
        "_trace": trace,
    }


def _process_battle_cry(action: dict, state: GameState) -> dict:
    trace = []
    trace.append(f"{state.player.name} 发出战吼！")
    trace.append(f"效果: 下次攻击 ATK +5")
    if "battle_cry" not in state.player.status:
        state.player.status.append("battle_cry")
    return {
        "action": "battle_cry",
        "success": True,
        "actor": state.player.name,
        "effect": "next_attack_atk_plus5",
        "actor_hp": state.player.hp,
        "actor_max_hp": state.player.max_hp,
        "_trace": trace,
    }


def _process_steal(action: dict, state: GameState) -> dict:
    trace = []
    trace.append(f"{state.player.name} 尝试偷窃 {state.enemy.name}")
    roll = random.random()
    success = roll < 0.25
    trace.append(f"偷窃判定: {roll:.2f} (需<0.25) → {'成功!' if success else '失败'}")

    if success:
        item = random.choice(["healing_potion", "healing_potion", "bomb"])
        if item == "healing_potion":
            state.player.items["healing_potion"] = state.player.items.get("healing_potion", 0) + 1
            trace.append(f"偷到: 治疗药水! (现有 {state.player.items['healing_potion']} 瓶)")
            return {
                "action": "steal",
                "success": True,
                "item": "healing_potion",
                "item_name": "治疗药水",
                "remaining": state.player.items["healing_potion"],
                "_trace": trace,
            }
        else:
            dmg = random.randint(8, 15)
            state.enemy.hp = max(0, state.enemy.hp - dmg)
            trace.append(f"偷到: 炸弹! 直接对敌人造成 {dmg} 伤害")
            trace.append(f"{state.enemy.name} HP: → {state.enemy.hp}/{state.enemy.max_hp}")
            result = {
                "action": "steal",
                "success": True,
                "item": "bomb",
                "item_name": "炸弹",
                "damage": dmg,
                "target_hp": state.enemy.hp,
                "target_max_hp": state.enemy.max_hp,
                "_trace": trace,
            }
            _check_kill(state.player, state.enemy, state, result)
            return result

    return {
        "action": "steal",
        "success": False,
        "_trace": trace,
    }


def _process_negotiate(action: dict, state: GameState) -> dict:
    trace = []
    enemy = state.enemy
    trace.append(f"{state.player.name} 尝试与 {enemy.name} 谈判")

    hp_ratio = enemy.hp / enemy.max_hp
    base_chance = 0.10
    if hp_ratio <= 0.3:
        base_chance = 0.35
        trace.append(f"敌人血量低({hp_ratio:.0%})，谈判成功率提升")
    elif hp_ratio <= 0.5:
        base_chance = 0.20
        trace.append(f"敌人受伤({hp_ratio:.0%})，谈判成功率小幅提升")

    roll = random.random()
    success = roll < base_chance
    trace.append(f"谈判判定: {roll:.2f} (需<{base_chance:.2f}) → {'成功!' if success else '失败'}")

    if success:
        state.combat_active = False
        return {
            "action": "negotiate",
            "success": True,
            "combat_end": True,
            "outcome": "enemy_surrendered",
            "_trace": trace,
        }
    return {
        "action": "negotiate",
        "success": False,
        "_trace": trace,
    }


def _process_surrender(action: dict, state: GameState) -> dict:
    trace = []
    trace.append(f"{state.player.name} 放下武器，选择投降")
    trace.append(f"结果: 战斗结束，你被击败了")
    state.player.hp = 0
    state.combat_active = False
    return {
        "action": "surrender",
        "success": True,
        "combat_end": True,
        "winner": state.enemy.name,
        "_trace": trace,
    }


def _process_pray(action: dict, state: GameState) -> dict:
    trace = []
    trace.append(f"{state.player.name} 闭目祈祷")
    roll = random.random()

    if roll < 0.30:
        heal = random.randint(15, 25)
        hp_before = state.player.hp
        state.player.hp = min(state.player.max_hp, state.player.hp + heal)
        actual = state.player.hp - hp_before
        trace.append(f"神圣之光! 恢复 {actual} HP ({roll:.2f} < 0.30)")
        trace.append(f"HP: {hp_before} → {state.player.hp}/{state.player.max_hp}")
        return {
            "action": "pray",
            "success": True,
            "outcome": "heal",
            "heal": actual,
            "actor_hp": state.player.hp,
            "actor_max_hp": state.player.max_hp,
            "_trace": trace,
        }
    elif roll < 0.50:
        dmg = random.randint(8, 15)
        state.enemy.hp = max(0, state.enemy.hp - dmg)
        trace.append(f"天降神罚! 对敌人造成 {dmg} 神圣伤害 ({roll:.2f} < 0.50)")
        trace.append(f"{state.enemy.name} HP: → {state.enemy.hp}/{state.enemy.max_hp}")
        result = {
            "action": "pray",
            "success": True,
            "outcome": "smite",
            "damage": dmg,
            "target": state.enemy.name,
            "target_hp": state.enemy.hp,
            "target_max_hp": state.enemy.max_hp,
            "_trace": trace,
        }
        _check_kill(state.player, state.enemy, state, result)
        return result
    elif roll < 0.75:
        trace.append(f"一片寂静... 什么也没发生 ({roll:.2f} < 0.75)")
        return {
            "action": "pray",
            "success": True,
            "outcome": "nothing",
            "_trace": trace,
        }
    else:
        dmg = random.randint(5, 10)
        state.player.hp = max(0, state.player.hp - dmg)
        trace.append(f"祈祷反噬! 受到 {dmg} 点伤害 ({roll:.2f} ≥ 0.75)")
        trace.append(f"HP: → {state.player.hp}/{state.player.max_hp}")
        result = {
            "action": "pray",
            "success": True,
            "outcome": "backfire",
            "damage": dmg,
            "actor_hp": state.player.hp,
            "actor_max_hp": state.player.max_hp,
            "_trace": trace,
        }
        if state.player.hp <= 0:
            state.combat_active = False
            result["combat_end"] = True
            result["winner"] = state.enemy.name
        return result


def _process_kick(action: dict, state: GameState) -> dict:
    attacker = state.player
    defender = state.enemy
    trace = []

    trace.append(f"{attacker.name} 飞踢 → {defender.name}")

    raw = int(attacker.atk * 0.5) - defender.defense // 4
    dmg = max(1, raw + random.randint(-1, 2))
    trace.append(f"踢击伤害: ATK×0.5 - DEF÷4 + 浮动 = {dmg}")

    hp_before = defender.hp
    defender.hp = max(0, defender.hp - dmg)
    trace.append(f"{defender.name} HP: {hp_before} → {defender.hp}")

    stun_roll = random.random()
    stunned = stun_roll < 0.30
    trace.append(f"眩晕判定: {stun_roll:.2f} (需<0.30) → {'眩晕!' if stunned else '未眩晕'}")
    if stunned and "stunned" not in defender.status:
        defender.status.append("stunned")

    result = {
        "action": "kick",
        "success": True,
        "damage": dmg,
        "stunned": stunned,
        "target": defender.name,
        "target_hp": defender.hp,
        "target_max_hp": defender.max_hp,
        "target_alive": defender.hp > 0,
        "_trace": trace,
    }
    _check_kill(attacker, defender, state, result)
    return result


def _process_invalid(action: dict, state: GameState) -> dict:
    trace = []
    original = action.get("original", "???")
    trace.append(f"{state.player.name} 犹豫不决")
    trace.append(f"原始输入: \"{original}\"")
    trace.append(f"结果: 浪费了一个回合")
    return {
        "action": "invalid",
        "success": False,
        "original": original,
        "actor_hp": state.player.hp,
        "actor_max_hp": state.player.max_hp,
        "_trace": trace,
    }


def _process_dynamic(action: dict, state: GameState) -> dict:
    from action_template import validate_template, execute_dynamic, lookup_template
    template = action.get("template", {})

    cached = lookup_template(template.get("name", ""))
    if cached:
        template = dict(cached)

    template, valid, error = validate_template(template)
    if not valid:
        return _process_invalid({"original": error}, state)
    return execute_dynamic(template, state)


# ---------- enemy turn ----------

def enemy_turn(state: GameState) -> dict:
    enemy = state.enemy
    player = state.player
    trace = []

    hp_ratio = enemy.hp / enemy.max_hp
    trace.append(f"{enemy.name} AI 决策 (HP {enemy.hp}/{enemy.max_hp} = {hp_ratio:.0%})")

    # stunned: skip turn entirely
    if "stunned" in enemy.status:
        enemy.status.remove("stunned")
        trace.append(f"状态: 眩晕中! 无法行动")
        return {
            "action": "stunned",
            "actor": enemy.name,
            "skipped": True,
            "_trace": trace,
        }

    # low-HP defend chance
    if hp_ratio < 0.3 and "defending" not in enemy.status:
        defend_roll = random.random()
        trace.append(f"低血量防御判定: {defend_roll:.2f} (需<0.40)")
        if defend_roll < 0.4:
            enemy.status.append("defending")
            trace.append(f"决策: 防御")
            return {
                "action": "defend",
                "actor": enemy.name,
                "effect": "next_damage_halved",
                "_trace": trace,
            }

    # attack
    trace.append(f"决策: 攻击 → {player.name}")

    atk = enemy.atk
    if "taunted" in enemy.status:
        atk = max(1, atk - 3)
        enemy.status.remove("taunted")
        trace.append(f"被嘲讽: ATK {enemy.atk} → {atk}")

    # check player dodging
    if "dodging" in player.status:
        player.status.remove("dodging")
        dodge_roll = random.random()
        trace.append(f"目标闪避判定: {dodge_roll:.2f} (需<0.50) → {'闪避成功!' if dodge_roll < 0.5 else '闪避失败'}")
        if dodge_roll < 0.5:
            return {
                "action": "attack",
                "actor": enemy.name,
                "target": player.name,
                "dodged": True,
                "damage": 0,
                "_trace": trace,
            }

    raw = atk - player.defense // 2
    trace.append(f"基础伤害: ATK({atk}) - DEF({player.defense})÷2 = {raw}")

    roll = random.randint(-3, 3)
    base_damage = max(1, raw + roll)
    trace.append(f"随机浮动: {roll:+d} → {base_damage}")

    crit_roll = random.random()
    is_critical = crit_roll < 0.10
    trace.append(f"暴击判定: {crit_roll:.2f} (需<0.10) → {'暴击!' if is_critical else '未暴击'}")
    if is_critical:
        before = base_damage
        base_damage = int(base_damage * 1.5)
        trace.append(f"暴击加成: {before} x1.5 = {base_damage}")

    if "defending" in player.status:
        before = base_damage
        base_damage = max(1, base_damage // 2)
        player.status.remove("defending")
        trace.append(f"目标防御中: {before} ÷2 = {base_damage}")

    hp_before = player.hp
    player.hp = max(0, player.hp - base_damage)
    trace.append(f"最终伤害: {base_damage}")
    trace.append(f"{player.name} HP: {hp_before} → {player.hp}")

    result = {
        "action": "attack",
        "actor": enemy.name,
        "target": player.name,
        "damage": base_damage,
        "critical": is_critical,
        "target_hp": player.hp,
        "target_max_hp": player.max_hp,
        "target_alive": player.hp > 0,
        "_trace": trace,
    }

    if player.hp <= 0:
        state.combat_active = False
        result["combat_end"] = True
        result["winner"] = enemy.name

    # counter: player auto-counterattacks after being hit
    if "countering" in player.status and player.hp > 0:
        player.status.remove("countering")
        counter_dmg = max(1, player.atk // 2 + random.randint(-2, 2))
        enemy.hp = max(0, enemy.hp - counter_dmg)
        trace.append(f"--- 反击触发! ---")
        trace.append(f"{player.name} 反击: {counter_dmg} 伤害")
        trace.append(f"{enemy.name} HP: → {enemy.hp}/{enemy.max_hp}")
        result["counter_triggered"] = True
        result["counter_damage"] = counter_dmg
        result["counter_target_hp"] = enemy.hp
        if enemy.hp <= 0:
            state.combat_active = False
            result["combat_end"] = True
            result["winner"] = player.name

    return result
