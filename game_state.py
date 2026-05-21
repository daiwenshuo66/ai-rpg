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
    traits: list = field(default_factory=list)
    extras: dict = field(default_factory=dict)


@dataclass
class GameState:
    player: Character
    enemy: Character
    turn: int = 1
    combat_active: bool = True

    def to_context(self) -> dict:
        return {
            "turn": self.turn,
            "player": self._char_dict(self.player),
            "enemy": self._char_dict(self.enemy),
            "combat_active": self.combat_active,
        }

    @staticmethod
    def _char_dict(c: "Character") -> dict:
        d = {
            "name": c.name,
            "hp": c.hp,
            "max_hp": c.max_hp,
            "atk": c.atk,
            "def": c.defense,
            "items": c.items,
            "status": c.status,
        }
        if c.traits:
            d["traits"] = c.traits
        if c.extras:
            d.update(c.extras)
        return d
