from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..game_page import GamePage


class GamePageComponent:
    """Base class for GamePage components."""

    def __init__(self, game_page: "GamePage"):
        self.game_page = game_page
        self.config_manager = game_page.config_manager
        self.game_name = game_page.game_name
