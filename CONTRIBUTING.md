# Contributing

## Developer Guide: The `GameLogic` Interface

To implement a new game, subclass `GameLogic` and override the following methods:

- `render_player_view(player_idx: int) -> str`: Return the SxPB-formatted string of the game state for the given player.
- `make_move(player_idx: int, move: str) -> MoveResult`: Apply a move and return a `MoveResult(success: bool, reason: str)`.
- `is_game_over() -> bool`: Return whether the game has reached an end state.
- `get_current_player() -> Optional[int]`: Return the index of the player whose turn it is.
- `get_prompt(player_idx: int) -> str`: Return the instruction for the current player's turn.

Optional methods include `render_player_history`, `get_visible_players`, and `get_rules`.

# Development

```sh
pdm install --dev
pdm update --update-eager
pdm test
pdm lint
```
