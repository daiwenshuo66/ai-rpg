import sys
import io
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")

from game_state import Character, GameState
from engine import process_action, enemy_turn
from ai_parser import parse_input, mock_parse
from ai_narrator import narrate, mock_narrate
from ai_character import (
    BUDGET_TIERS, parse_character, mock_parse_character,
    validate_and_recalculate, build_character,
)
from ai_enemy import generate_enemy, build_enemy
from config import API_KEY, DEBUG
import config


def select_budget() -> tuple[str, int | None]:
    tiers = list(BUDGET_TIERS.items())
    print("\n  选择你的灵根资质：")
    for i, (key, tier) in enumerate(tiers, 1):
        pts = f"{tier['points']}点" if tier['points'] else "无限"
        print(f"    {i}. {tier['label']} ({pts}) - {tier['desc']}")
    print()

    while True:
        try:
            choice = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            sys.exit(0)
        if choice in ("1", "2", "3", "4"):
            key, tier = tiers[int(choice) - 1]
            return key, tier["points"]
        print("  请输入 1-4")


def display_preview(parsed: dict, breakdown: dict, budget: int | None):
    stats = parsed["stats"]
    print(f"\n{'═' * 50}")
    print(f"  角色预览")
    print(f"{'═' * 50}")
    print(f"  名称: {parsed.get('name', '?')}")
    if parsed.get("title"):
        print(f"  称号: {parsed['title']}")
    print()
    print(f"  气血: {stats['hp']:>4}  ({breakdown.get('hp', 0)} 资质点)")
    print(f"  攻击: {stats['atk']:>4}  ({breakdown.get('atk', 0)} 资质点)")
    print(f"  防御: {stats['defense']:>4}  ({breakdown.get('defense', 0)} 资质点)")

    potions = parsed.get("items", {}).get("healing_potion", 0)
    if potions > 0:
        print(f"  回血丹: x{potions}  ({breakdown.get('items', 0)} 资质点)")

    traits = parsed.get("traits", [])
    if traits:
        print()
        print("  天赋/特质:")
        from ai_character import KNOWN_TRAIT_COSTS
        for t in traits:
            marker = "★" if t.get("mechanical") else "☆"
            cost = ""
            if t.get("mechanical") and t["id"] in KNOWN_TRAIT_COSTS:
                cost = f" ({KNOWN_TRAIT_COSTS[t['id']]}点)"
            print(f"    {marker} {t.get('name', t['id'])} - {t.get('description', '')}{cost}")

    print(f"\n  {'─' * 46}")
    total = breakdown.get("total", 0)
    budget_str = str(budget) if budget is not None else "∞"
    status = "✓" if (budget is None or total <= budget) else "✗ 超出!"
    print(f"  总计: {total} / {budget_str} 资质点  {status}")
    print(f"{'═' * 50}")


def create_character(mock_mode: bool) -> Character:
    while True:
        tier_key, budget = select_budget()
        tier = BUDGET_TIERS[tier_key]

        while True:
            budget_str = f"{budget}点" if budget else "无限"
            print(f"\n  [{tier['label']}] 资质点: {budget_str}")
            print("  描述你的角色（修仙背景，自由发挥）：")

            try:
                description = input("  > ").strip()
            except (EOFError, KeyboardInterrupt):
                sys.exit(0)

            if not description:
                continue

            if not mock_mode:
                print("  [解析中...]")
            do_parse = mock_parse_character if mock_mode else parse_character
            parsed = do_parse(description, budget)

            parsed, breakdown, valid, error = validate_and_recalculate(parsed, budget)

            if not valid:
                print(f"\n  ✗ {error}")
                print("  请重新描述一个更简单的角色。")
                continue

            display_preview(parsed, breakdown, budget)

            print("\n  [Y] 确认  [R] 重新描述  [B] 重选灵根")
            try:
                choice = input("  > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                sys.exit(0)

            if choice in ("y", "yes", "确认", ""):
                return build_character(parsed)
            elif choice in ("b",):
                break
            # else: loop back to description


def create_initial_state() -> GameState:
    player = Character(
        name="勇者",
        hp=100,
        max_hp=100,
        atk=15,
        defense=8,
        items={"healing_potion": 2},
    )
    enemy = Character(
        name="哥布林首领",
        hp=50,
        max_hp=50,
        atk=12,
        defense=5,
    )
    return GameState(player=player, enemy=enemy)


def display_status(state: GameState):
    p = state.player
    e = state.enemy
    bar_p = _hp_bar(p.hp, p.max_hp)
    bar_e = _hp_bar(e.hp, e.max_hp)
    print(f"\n{'='*50}")
    print(f"  回合 {state.turn}")
    print(f"  {p.name} {bar_p} {p.hp}/{p.max_hp}  药水x{p.items.get('healing_potion', 0)}")
    print(f"  {e.name} {bar_e} {e.hp}/{e.max_hp}")
    print(f"{'='*50}")


def _hp_bar(hp: int, max_hp: int, length: int = 20) -> str:
    filled = int(length * hp / max_hp) if max_hp > 0 else 0
    return f"[{'#' * filled}{'.' * (length - filled)}]"


def _display_trace(player_result: dict, enemy_result: dict = None):
    W = 48
    print()
    print(f"  +{'- 引擎计算 ' + '-' * (W - 12)}+")

    for step in player_result.get("_trace", []):
        print(f"  | {_pad_cjk(step, W - 1)}|")

    if enemy_result and enemy_result.get("_trace"):
        print(f"  |{'-' * W}|")
        for step in enemy_result.get("_trace", []):
            print(f"  | {_pad_cjk(step, W - 1)}|")

    print(f"  +{'-' * W}+")


def _pad_cjk(text: str, width: int) -> str:
    display_w = 0
    for ch in text:
        display_w += 2 if ("一" <= ch <= "鿿" or "＀" <= ch <= "￯") else 1
    return text + " " * max(0, width - display_w)


def main():
    mock_mode = "--mock" in sys.argv

    if not mock_mode and not API_KEY:
        print("未检测到 API_KEY，自动切换到 mock 模式。")
        print("请在 config.py 中设置你的 DeepSeek API Key\n")
        mock_mode = True

    mode_label = "Mock 模式（关键词匹配 + 模板叙述）" if mock_mode else "AI 模式（DeepSeek V4 Pro）"

    print("\n" + "=" * 50)
    print("       修仙 RPG - 灵根觉醒")
    print("=" * 50)
    print(f"  [{mode_label}]")
    print()

    player = create_character(mock_mode)

    if not mock_mode:
        print("  [生成敌人...]")
    enemy_data = generate_enemy(player, mock_mode)
    enemy, enemy_desc = build_enemy(enemy_data)
    state = GameState(player=player, enemy=enemy)

    print()
    if enemy.extras.get("title"):
        print(f"  【{enemy.name} · {enemy.extras['title']}】")
    else:
        print(f"  【{enemy.name}】")
    print(f"  {enemy_desc}")
    print()
    print("  可用行动（自由输入即可）：")
    print("    攻击 / 重击 / 连击 / 踢")
    print("    防御 / 反击 / 闪避")
    print("    蓄力 / 集中 / 战吼")
    print("    药水 / 休息 / 祈祷")
    print("    嘲讽 / 观察 / 偷窃 / 谈判")
    print("    逃跑 / 投降")
    print("    输入 quit 退出")

    do_parse = mock_parse if mock_mode else lambda inp: parse_input(inp, state.to_context())
    do_narrate = mock_narrate if mock_mode else narrate

    while state.combat_active:
        display_status(state)

        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n游戏结束。")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "退出", "q"):
            print("\n游戏结束。")
            break
        if user_input.lower() in ("debug", "debug 1", "debug 0"):
            import action_template
            config.DEBUG = not config.DEBUG
            action_template.DEBUG = config.DEBUG
            print(f"  [DEBUG {'ON' if config.DEBUG else 'OFF'}]")
            continue
        if user_input.lower() in ("templates", "模板", "招式"):
            from action_template import get_all_templates
            templates = get_all_templates()
            if not templates:
                print("  [暂无已注册的动态模板]")
            else:
                print(f"\n  已注册动态模板 ({len(templates)} 个):")
                print(f"  {'─' * 46}")
                for name, t in templates.items():
                    tp = t.get('type', '?')
                    uses = t.get('use_count', 0)
                    power = t.get('power', '-')
                    acc = t.get('accuracy', '-')
                    print(f"    {name:12s} [{tp:6s}] power={power} acc={acc} (使用{uses}次)")
                print(f"  {'─' * 46}")
            continue

        # --- Layer 1: Parse ---
        if not mock_mode:
            print("  [解析中...]")
        action = do_parse(user_input)
        if config.DEBUG:
            print(f"  [DEBUG] 解析结果: {json.dumps(action, ensure_ascii=False)}")
        else:
            print(f"  -> 动作: {json.dumps({k:v for k,v in action.items() if k != 'template'}, ensure_ascii=False)}")

        # --- Layer 2: Engine (player) ---
        player_result = process_action(action, state)

        # --- Layer 2: Engine (enemy) ---
        enemy_result = None
        if state.combat_active:
            enemy_result = enemy_turn(state)

        state.turn += 1

        # --- Visualize engine trace ---
        _display_trace(player_result, enemy_result)

        # --- Layer 3: Narrate ---
        if not mock_mode:
            print("  [生成叙述...]")
        narrative = do_narrate(
            player_result=player_result,
            enemy_result=enemy_result,
            context=state.to_context(),
            user_input=user_input,
        )
        print(f"\n{narrative}")

        # --- End check ---
        if not state.combat_active:
            print()
            print("=" * 50)
            if state.player.hp <= 0:
                print("  你被击败了... GAME OVER")
            elif state.enemy.hp <= 0:
                print(f"  胜利！{state.enemy.name} 倒下了！")
            else:
                print("  你逃离了战斗。")
            print("=" * 50)


if __name__ == "__main__":
    main()
