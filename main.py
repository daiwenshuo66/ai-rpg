import sys
import io
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")

from game_state import Character, GameState
from engine import process_action, enemy_turn
from ai_parser import parse_input, mock_parse
from ai_narrator import narrate, mock_narrate
from config import API_KEY


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
    print("       AI RPG 原型 - 哥布林洞窟")
    print("=" * 50)
    print(f"  [{mode_label}]")
    print()
    print("  你走进一个阴暗的洞窟，火把的光芒照亮了前方——")
    print("  一个体型壮硕的哥布林首领挡住了去路。")
    print("  它手持一把生锈的弯刀，向你龇牙咧嘴。")
    print()
    print("  可用行动（自由输入即可）：")
    print("    攻击 / 防御 / 使用药水 / 逃跑")
    print("    输入 quit 退出")

    state = create_initial_state()

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

        # --- Layer 1: Parse ---
        if not mock_mode:
            print("  [解析中...]")
        action = do_parse(user_input)
        print(f"  -> 动作: {json.dumps(action, ensure_ascii=False)}")

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
                print("  胜利！哥布林首领倒下了！")
            else:
                print("  你逃离了战斗。")
            print("=" * 50)


if __name__ == "__main__":
    main()
