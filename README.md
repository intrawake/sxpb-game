# SxPB Game Room 

A collection of turn-based games and social deduction scenarios implemented for LLM evaluation and interactive play. All games utilize the [SxPB](https://github.com/sxproto/sxpb) (S-expression Protocol Buffer) format for structured state representation.

## Features

- **Standardized Interface:** All games implement a unified `GameLogic` abstract base class, making it easy to plug in new games or evaluation agents.
- **SxPB Integration:** Game states and player views are rendered in SxPB, providing a clear, hierarchical format that LLMs can easily parse.
- **Multi-Player Support:** Supports various player counts, from solo puzzles (Minesweeper, Sudoku) to large social deduction groups (Mafia).
- **Extensible:** Designed to be used as a backend for LLM benchmarking or as a standalone game server.

## Implemented Games

The repository currently includes implementations for:

- **Tic-Tac-Toe:** The classic 3x3 grid game.
- **Connect Four:** Four-in-a-row on a vertical grid.
- **Blackjack:** Standard casino rules with a random dealer.
- **Mastermind:** Code-breaking logic puzzle.
- **Wordle:** Word-guessing game with color-coded feedback.
- **Minesweeper:** Grid-based bomb-finding puzzle.
- **Sudoku:** Numbers-based logic puzzle.
- **Old Maid:** Card-shedding and pair-matching game.
- **Don't Mess with Cthulhu:** Social deduction and hidden identity game.
- **Codenames:** Team-based word association and deduction.
- **Mafia:** Large-scale social deduction with roles like Detective, Doctor, and Vigilante.
- **Chameleon:** Social deduction where one player must blend in without knowing the secret word.
- **Trolley Problem:** A moral and logical reasoning scenario where players argue for different ethical outcomes.

## Getting Started

### Prerequisites

- Python 3.9+
- [PDM](https://pdm.fming.dev/) (Python Development Master)

### Installation

```bash
git clone https://github.com/intrawake/sxpb-game.git
cd sxpb-game
pdm install
```

### Running a Game Server

You can run a game between multiple LLM agents (or algorithmic players) using the provided server:

```bash
# Example: Wordle Battle between two models
pdm run server --game wordle \
  --players "(()) (() (name Codemaker) (model dono-gemini-lite)) (() (name Codebreaker) (model dono-gemma3-27b))"
```

## License

This project is licensed under the **0BSD (Zero-Clause BSD)**. See the [LICENSE](LICENSE) file for details.

---
*Maintained by [paprika-bot](https://github.com/sockpaprika).*
