Battleship (Salvo Rules)

Goal: Sink all of your opponent's ships before they sink yours.
Grid: 10x10 (a-j, 1-10).
Ships:
- Carrier (5 units)
- Battleship (4 units)
- Cruiser (3 units)
- Submarine (3 units)
- Destroyer (2 units)

Phases:
1. Placement: You will be asked to place each of your 5 ships. Use the format: `place <ship_name> <coord> <orientation>` where orientation is `h` (horizontal) or `v` (vertical). Orientation `h` means the ship extends to the right; `v` means it extends down.
2. Attack (Salvo): Each turn, you take a number of shots equal to the number of your remaining ships. Use the format: `fire <coord1> <coord2> ... [. optional message]`

Gameplay:
- After you fire, you will be told which shots were hits and which were misses.
- A ship is sunk when all of its units have been hit.
- The game ends when one player loses all 5 ships.
