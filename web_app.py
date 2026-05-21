import asyncio
import time
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from game_state import Character, GameState
from engine import process_action, enemy_turn
from ai_parser import parse_input, mock_parse
from ai_narrator import narrate, mock_narrate
from ai_character import (
    BUDGET_TIERS, parse_character, mock_parse_character,
    validate_and_recalculate, build_character,
)
from ai_enemy import generate_enemy, build_enemy
from config import DEBUG
import config


# --- Session management ---

class Session:
    def __init__(self, state: GameState, mock_mode: bool):
        self.state = state
        self.mock_mode = mock_mode
        self.lock = asyncio.Lock()
        self.last_active = time.time()


sessions: dict[str, Session] = {}


# --- FastAPI app ---

app = FastAPI()


class NewGameRequest(BaseModel):
    mock: bool = False
    character: dict | None = None


class ActionRequest(BaseModel):
    session_id: str
    input: str


class ParseCharacterRequest(BaseModel):
    description: str
    budget: int | None = None
    mock: bool = False


@app.get("/api/tiers")
async def get_tiers():
    return {"tiers": BUDGET_TIERS}


@app.post("/api/debug")
async def toggle_debug():
    import action_template
    config.DEBUG = not config.DEBUG
    action_template.DEBUG = config.DEBUG
    return {"debug": config.DEBUG}


@app.get("/api/templates")
async def list_templates():
    from action_template import get_all_templates
    return {"templates": get_all_templates()}


@app.post("/api/parse-character")
async def handle_parse_character(req: ParseCharacterRequest):
    if req.mock:
        parsed = mock_parse_character(req.description, req.budget)
    else:
        parsed = await asyncio.to_thread(
            parse_character, req.description, req.budget
        )

    parsed, breakdown, valid, error = validate_and_recalculate(parsed, req.budget)
    return {
        "character": parsed,
        "breakdown": breakdown,
        "valid": valid,
        "error": error,
    }


@app.post("/api/new")
async def new_game(req: NewGameRequest):
    session_id = uuid.uuid4().hex[:12]

    if req.character:
        _, _, valid, error = validate_and_recalculate(dict(req.character), None)
        if not valid:
            raise HTTPException(400, error)
        player = build_character(req.character)
    else:
        player = Character(
            name="散修", hp=100, max_hp=100, atk=15, defense=8,
            items={"healing_potion": 2},
        )

    if req.mock:
        enemy_data = generate_enemy(player, mock_mode=True)
    else:
        enemy_data = await asyncio.to_thread(generate_enemy, player, False)
    enemy, enemy_desc = build_enemy(enemy_data)

    state = GameState(player=player, enemy=enemy)
    sessions[session_id] = Session(state, req.mock)

    title = enemy_data.get("title", "")
    intro = f"【{enemy.name} · {title}】\n{enemy_desc}" if title else f"【{enemy.name}】\n{enemy_desc}"

    return {
        "session_id": session_id,
        "state": state.to_context(),
        "intro": intro,
    }


@app.post("/api/action")
async def handle_action(req: ActionRequest):
    session = sessions.get(req.session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if not session.state.combat_active:
        raise HTTPException(400, "Combat has ended")

    async with session.lock:
        session.last_active = time.time()
        state = session.state

        if session.mock_mode:
            action = mock_parse(req.input)
        else:
            action = await asyncio.to_thread(
                parse_input, req.input, state.to_context()
            )

        player_result = process_action(action, state)

        enemy_result = None
        if state.combat_active:
            enemy_result = enemy_turn(state)

        state.turn += 1

        if session.mock_mode:
            narrative = mock_narrate(player_result, enemy_result)
        else:
            narrative = await asyncio.to_thread(
                narrate, player_result, enemy_result,
                state.to_context(), req.input,
            )

        game_over = None
        if not state.combat_active:
            if state.player.hp <= 0:
                game_over = {"winner": state.enemy.name, "message": "你被击败了... GAME OVER"}
            elif state.enemy.hp <= 0:
                game_over = {"winner": state.player.name, "message": f"胜利！{state.enemy.name} 倒下了！"}
            else:
                game_over = {"winner": None, "message": "你逃离了战斗。"}

        response = {
            "state": state.to_context(),
            "action": {k: v for k, v in player_result.items() if k != "_trace"},
            "enemy_result": (
                {k: v for k, v in enemy_result.items() if k != "_trace"}
                if enemy_result else None
            ),
            "narrative": narrative,
            "trace": {
                "player": player_result.get("_trace", []),
                "enemy": enemy_result.get("_trace", []) if enemy_result else [],
            },
            "game_over": game_over,
        }

        if config.DEBUG:
            response["debug"] = {
                "parsed_action": action,
                "raw_player_result": player_result,
            }

        return response


# --- Session cleanup ---

@app.on_event("startup")
async def start_cleanup():
    async def cleanup_loop():
        while True:
            await asyncio.sleep(300)
            now = time.time()
            expired = [sid for sid, s in sessions.items() if now - s.last_active > 3600]
            for sid in expired:
                del sessions[sid]
    asyncio.create_task(cleanup_loop())


# --- Serve frontend ---

app.mount("/", StaticFiles(directory="static", html=True), name="static")
