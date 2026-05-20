from dataclasses import dataclass, field


@dataclass
class Character:
    name: str
    hp: int
    max_hp: int
    atk: int
    defense: int
    items: dict = field(default_factory=dict)
    status: list = field(default_factory=list)


@dataclass
class GameState:
    player: Character
    enemy: Character
    turn: int = 1
    combat_active: bool = True

    def to_context(self) -> dict:
        return {
            "turn": self.turn,
            "player": {
                "name": self.player.name,
                "hp": self.player.hp,
                "max_hp": self.player.max_hp,
                "atk": self.player.atk,
                "def": self.player.defense,
                "items": self.player.items,
                "status": self.player.status,
            },
            "enemy": {
                "name": self.enemy.name,
                "hp": self.enemy.hp,
                "max_hp": self.enemy.max_hp,
                "atk": self.enemy.atk,
                "def": self.enemy.defense,
                "status": self.enemy.status,
            },
            "combat_active": self.combat_active,
        }
