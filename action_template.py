"""
Dynamic action template system.

When AI encounters an input that doesn't match the 20 built-in actions,
it can create a dynamic action template on-the-fly. The template is
validated by deterministic rules (not another AI) before execution.

Template JSON schema (from AI):
{
  "action": "dynamic",
  "template": {
    "name": "旋风斩",
    "description": "旋转身体挥出一记横扫",
    "type": "attack",           # attack | defend | buff | heal | debuff | utility
    "power": 0.9,               # damage multiplier vs base ATK (attack type)
    "accuracy": 0.85,           # hit chance 0.0-1.0
    "crit_bonus": 0.0,          # added to base 15% crit rate
    "self_damage": 0.0,         # fraction of damage dealt to self (risky moves)
    "heal_power": 0.0,          # fraction of max_hp healed (heal type)
    "defense_mult": 0.0,        # damage reduction multiplier (defend type)
    "status_apply": "",         # status to apply to target (debuff type)
    "status_self": "",          # status to apply to self (buff type)
    "cost_hp": 0                # HP cost to use this action
  }
}
"""

import json
import os
import random
from game_state import GameState
from config import DEBUG

# ---------- template registry (persistent) ----------

REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "data", "templates.json")

_registry: dict[str, dict] = {}
_registry_loaded = False


def _ensure_loaded():
    global _registry, _registry_loaded
    if _registry_loaded:
        return
    _registry_loaded = True
    if os.path.exists(REGISTRY_PATH):
        try:
            with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
                _registry = json.load(f)
        except (json.JSONDecodeError, IOError):
            _registry = {}


def _save_registry():
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(_registry, f, ensure_ascii=False, indent=2)


def register_template(template: dict):
    _ensure_loaded()
    name = template.get("name", "")
    if not name:
        return
    clean = {k: v for k, v in template.items() if not k.startswith("_")}
    clean["use_count"] = _registry.get(name, {}).get("use_count", 0) + 1
    _registry[name] = clean
    _save_registry()


def lookup_template(name: str) -> dict | None:
    _ensure_loaded()
    return _registry.get(name)


def get_all_templates() -> dict:
    _ensure_loaded()
    return dict(_registry)

# ---------- validation bounds ----------

VALID_TYPES = {"attack", "defend", "buff", "heal", "debuff", "utility"}

ALLOWED_STATUS_TARGET = {"taunted", "stunned"}
ALLOWED_STATUS_SELF = {"defending", "charged", "focused", "battle_cry", "countering", "dodging"}

BOUNDS = {
    "power":        (0.1, 2.5),
    "accuracy":     (0.2, 1.0),
    "crit_bonus":   (0.0, 0.35),
    "self_damage":  (0.0, 0.3),
    "heal_power":   (0.0, 0.3),
    "defense_mult": (0.0, 0.8),
    "lifesteal":    (0.0, 0.3),
    "cost_hp":      (0, 30),
}


def validate_template(template: dict) -> tuple[dict, bool, str]:
    if not isinstance(template, dict):
        return {}, False, "template is not a dict"

    action_type = template.get("type", "")
    if action_type not in VALID_TYPES:
        return template, False, f"unknown type: {action_type}"

    clamped = []
    for key, (lo, hi) in BOUNDS.items():
        val = template.get(key, 0)
        try:
            val = float(val) if isinstance(val, str) else val
        except (ValueError, TypeError):
            val = 0
        if isinstance(lo, int) and isinstance(hi, int):
            clamped_val = max(lo, min(hi, int(val)))
        else:
            clamped_val = max(lo, min(hi, float(val)))
        if clamped_val != val:
            clamped.append(f"{key}: {val} → {clamped_val}")
        template[key] = clamped_val

    status_apply = template.get("status_apply", "")
    if status_apply and status_apply not in ALLOWED_STATUS_TARGET:
        clamped.append(f"status_apply: '{status_apply}' → removed")
        template["status_apply"] = ""

    status_self = template.get("status_self", "")
    if status_self and status_self not in ALLOWED_STATUS_SELF:
        clamped.append(f"status_self: '{status_self}' → removed")
        template["status_self"] = ""

    if not template.get("name"):
        template["name"] = "未知招式"

    if DEBUG and clamped:
        template["_debug_clamped"] = clamped

    return template, True, ""


# ---------- execution ----------

def execute_dynamic(template: dict, state: GameState) -> dict:
    action_type = template["type"]
    player = state.player
    enemy = state.enemy
    trace = []
    name = template.get("name", "动态招式")

    trace.append(f"{player.name} 使用「{name}」")

    if DEBUG:
        source = f"已注册(使用{template.get('use_count', 0)}次)" if template.get("use_count") else "新模板"
        trace.append(f"[DEBUG] 动态模板 [{source}]: type={action_type} power={template.get('power','-')} "
                     f"acc={template.get('accuracy','-')} crit+={template.get('crit_bonus','-')} "
                     f"self_dmg={template.get('self_damage','-')} heal={template.get('heal_power','-')} "
                     f"lifesteal={template.get('lifesteal','-')} cost_hp={template.get('cost_hp','-')}")
        if template.get("status_apply"):
            trace.append(f"[DEBUG] status_apply={template['status_apply']}")
        if template.get("status_self"):
            trace.append(f"[DEBUG] status_self={template['status_self']}")
        if template.get("_debug_clamped"):
            trace.append(f"[DEBUG] 校验修正: {', '.join(template['_debug_clamped'])}")

    if template.get("cost_hp", 0) > 0:
        cost = template["cost_hp"]
        player.hp = max(1, player.hp - cost)
        trace.append(f"消耗气血: {cost} (HP → {player.hp})")

    if action_type == "attack":
        result = _exec_attack(template, state, trace)
    elif action_type == "defend":
        result = _exec_defend(template, state, trace)
    elif action_type == "buff":
        result = _exec_buff(template, state, trace)
    elif action_type == "heal":
        result = _exec_heal(template, state, trace)
    elif action_type == "debuff":
        result = _exec_debuff(template, state, trace)
    else:
        result = _exec_utility(template, state, trace)

    if result.get("success"):
        register_template(template)

    return result


def _exec_attack(t: dict, state: GameState, trace: list) -> dict:
    player = state.player
    enemy = state.enemy
    power = t.get("power", 1.0)
    accuracy = t.get("accuracy", 0.85)
    crit_bonus = t.get("crit_bonus", 0.0)
    self_damage_frac = t.get("self_damage", 0.0)

    hit_roll = random.random()
    trace.append(f"命中判定: {hit_roll:.2f} (需<{accuracy:.2f}) → {'命中' if hit_roll < accuracy else 'MISS'}")

    if hit_roll >= accuracy:
        return {
            "action": "dynamic", "template_name": t.get("name", "?"),
            "success": False, "miss": True, "target": enemy.name,
            "_trace": trace,
        }

    from engine import _consume_attack_buffs, _apply_damage, _check_kill

    atk_bonus, crit_rate, dmg_mult = _consume_attack_buffs(player, trace)

    atk = player.atk + atk_bonus
    raw = int(atk * power) - enemy.defense // 2
    base_damage = max(1, raw + random.randint(-3, 3))
    trace.append(f"伤害计算: ATK({atk}) x{power:.1f} - DEF÷2 + 浮动 = {base_damage}")

    effective_crit = min(0.50, crit_rate + crit_bonus)
    crit_roll = random.random()
    is_critical = crit_roll < effective_crit
    trace.append(f"暴击判定: {crit_roll:.2f} (需<{effective_crit:.2f}) → {'暴击!' if is_critical else '未暴击'}")
    if is_critical:
        before = base_damage
        base_damage = int(base_damage * 1.5)
        trace.append(f"暴击加成: {before} x1.5 = {base_damage}")

    final = _apply_damage(base_damage, dmg_mult, enemy, trace)

    if self_damage_frac > 0:
        self_dmg = max(1, int(final * self_damage_frac))
        player.hp = max(0, player.hp - self_dmg)
        trace.append(f"反噬伤害: {self_dmg} (HP → {player.hp})")

    lifesteal = t.get("lifesteal", 0.0)
    if lifesteal > 0 and final > 0:
        stolen = max(1, int(final * lifesteal))
        hp_before = player.hp
        player.hp = min(player.max_hp, player.hp + stolen)
        actual = player.hp - hp_before
        trace.append(f"吸血: {actual} HP ({hp_before} → {player.hp})")

    result = {
        "action": "dynamic", "template_name": t.get("name", "?"),
        "success": True, "damage": final, "critical": is_critical,
        "target": enemy.name, "target_hp": enemy.hp,
        "target_max_hp": enemy.max_hp, "target_alive": enemy.hp > 0,
        "_trace": trace,
    }
    _check_kill(player, enemy, state, result)

    if player.hp <= 0:
        state.combat_active = False
        result["combat_end"] = True
        result["winner"] = enemy.name

    return result


def _exec_defend(t: dict, state: GameState, trace: list) -> dict:
    player = state.player
    if "defending" not in player.status:
        player.status.append("defending")
    trace.append(f"效果: 防御姿态（下次伤害减半）")
    status_self = t.get("status_self", "")
    if status_self and status_self != "defending" and status_self not in player.status:
        player.status.append(status_self)
        trace.append(f"额外状态: {status_self}")
    return {
        "action": "dynamic", "template_name": t.get("name", "?"),
        "success": True, "effect": "defending",
        "actor": player.name, "actor_hp": player.hp,
        "actor_max_hp": player.max_hp,
        "_trace": trace,
    }


def _exec_buff(t: dict, state: GameState, trace: list) -> dict:
    player = state.player
    status_self = t.get("status_self", "")
    if status_self and status_self in ALLOWED_STATUS_SELF and status_self not in player.status:
        player.status.append(status_self)
        trace.append(f"获得状态: {status_self}")
    else:
        if "focused" not in player.status:
            player.status.append("focused")
            trace.append(f"获得状态: focused (默认)")
    return {
        "action": "dynamic", "template_name": t.get("name", "?"),
        "success": True, "effect": status_self or "focused",
        "actor": player.name, "actor_hp": player.hp,
        "actor_max_hp": player.max_hp,
        "_trace": trace,
    }


def _exec_heal(t: dict, state: GameState, trace: list) -> dict:
    player = state.player
    heal_power = t.get("heal_power", 0.15)
    heal = max(1, int(player.max_hp * heal_power) + random.randint(-3, 3))
    hp_before = player.hp
    player.hp = min(player.max_hp, player.hp + heal)
    actual = player.hp - hp_before
    trace.append(f"恢复: {actual} HP ({hp_before} → {player.hp}/{player.max_hp})")
    return {
        "action": "dynamic", "template_name": t.get("name", "?"),
        "success": True, "heal": actual,
        "actor_hp": player.hp, "actor_max_hp": player.max_hp,
        "_trace": trace,
    }


def _exec_debuff(t: dict, state: GameState, trace: list) -> dict:
    enemy = state.enemy
    status_apply = t.get("status_apply", "")
    if status_apply and status_apply in ALLOWED_STATUS_TARGET and status_apply not in enemy.status:
        enemy.status.append(status_apply)
        trace.append(f"{enemy.name} 获得状态: {status_apply}")
    else:
        if "taunted" not in enemy.status:
            enemy.status.append("taunted")
            trace.append(f"{enemy.name} 获得状态: taunted (默认)")
    return {
        "action": "dynamic", "template_name": t.get("name", "?"),
        "success": True, "target": enemy.name,
        "effect": status_apply or "taunted",
        "_trace": trace,
    }


def _exec_utility(t: dict, state: GameState, trace: list) -> dict:
    trace.append(f"效果: 暂无实际战斗效果，但叙事者会描述这个动作")
    return {
        "action": "dynamic", "template_name": t.get("name", "?"),
        "success": True,
        "actor": state.player.name,
        "actor_hp": state.player.hp,
        "actor_max_hp": state.player.max_hp,
        "_trace": trace,
    }
