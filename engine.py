import random
from game_state import GameState


def process_action(action: dict, state: GameState) -> dict:
    action_type = action.get("action")
    handlers = {
        "attack": _process_attack,
        "defend": _process_defend,
        "use_item": _process_use_item,
        "flee": _process_flee,
        "rest": _process_rest,
        "taunt": _process_taunt,
        "examine": _process_examine,
        "invalid": _process_invalid,
    }
    handler = handlers.get(action_type)
    if handler:
        return handler(action, state)
    return _process_invalid(action, state)


def _process_attack(action: dict, state: GameState) -> dict:
    attacker = state.player
    defender = state.enemy
    trace = []

    trace.append(f"{attacker.name} 攻击 → {defender.name}")

    raw = attacker.atk - defender.defense // 2
    trace.append(f"基础伤害: ATK({attacker.atk}) - DEF({defender.defense})÷2 = {raw}")

    roll = random.randint(-3, 3)
    base_damage = max(1, raw + roll)
    trace.append(f"随机浮动: {roll:+d} → {base_damage}")

    crit_roll = random.random()
    is_critical = crit_roll < 0.15
    trace.append(f"暴击判定: {crit_roll:.2f} (需<0.15) → {'暴击!' if is_critical else '未暴击'}")
    if is_critical:
        before = base_damage
        base_damage = int(base_damage * 1.5)
        trace.append(f"暴击加成: {before} x1.5 = {base_damage}")

    if "defending" in defender.status:
        before = base_damage
        base_damage = max(1, base_damage // 2)
        defender.status.remove("defending")
        trace.append(f"目标防御中: {before} ÷2 = {base_damage}")

    hp_before = defender.hp
    defender.hp = max(0, defender.hp - base_damage)
    trace.append(f"最终伤害: {base_damage}")
    trace.append(f"{defender.name} HP: {hp_before} → {defender.hp}")

    result = {
        "action": "attack",
        "success": True,
        "damage": base_damage,
        "critical": is_critical,
        "target": defender.name,
        "target_hp": defender.hp,
        "target_max_hp": defender.max_hp,
        "target_alive": defender.hp > 0,
        "_trace": trace,
    }

    if defender.hp <= 0:
        state.combat_active = False
        result["combat_end"] = True
        result["winner"] = attacker.name

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


def enemy_turn(state: GameState) -> dict:
    enemy = state.enemy
    player = state.player
    trace = []

    hp_ratio = enemy.hp / enemy.max_hp
    trace.append(f"{enemy.name} AI 决策 (HP {enemy.hp}/{enemy.max_hp} = {hp_ratio:.0%})")

    if (
        hp_ratio < 0.3
        and "defending" not in enemy.status
    ):
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

    trace.append(f"决策: 攻击 → {player.name}")

    atk = enemy.atk
    if "taunted" in enemy.status:
        atk = max(1, atk - 3)
        enemy.status.remove("taunted")
        trace.append(f"被嘲讽: ATK {enemy.atk} → {atk}")

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

    return result
