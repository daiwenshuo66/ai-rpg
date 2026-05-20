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

INTRO_TEXT = (
    "你走进一个阴暗的洞窟，火把的光芒照亮了前方——\n"
    "一个体型壮硕的哥布林首领挡住了去路。\n"
    "它手持一把生锈的弯刀，向你龇牙咧嘴。"
)


# --- Session management ---

class Session:
    def __init__(self, state: GameState, mock_mode: bool):
        self.state = state
        self.mock_mode = mock_mode
        self.lock = asyncio.Lock()
        self.last_active = time.time()


sessions: dict[str, Session] = {}


def create_initial_state() -> GameState:
    player = Character(
        name="勇者", hp=100, max_hp=100, atk=15, defense=8,
        items={"healing_potion": 2},
    )
    enemy = Character(
        name="哥布林首领", hp=50, max_hp=50, atk=12, defense=5,
    )
    return GameState(player=player, enemy=enemy)


# --- FastAPI app ---

app = FastAPI()


class NewGameRequest(BaseModel):
    mock: bool = False


class ActionRequest(BaseModel):
    session_id: str
    input: str


@app.post("/api/new")
async def new_game(req: NewGameRequest):
    session_id = uuid.uuid4().hex[:12]
    state = create_initial_state()
    sessions[session_id] = Session(state, req.mock)
    return {
        "session_id": session_id,
        "state": state.to_context(),
        "intro": INTRO_TEXT,
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
                game_over = {"winner": state.player.name, "message": "胜利！哥布林首领倒下了！"}
            else:
                game_over = {"winner": None, "message": "你逃离了战斗。"}

        return {
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
