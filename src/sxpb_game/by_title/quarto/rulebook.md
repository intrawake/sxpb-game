Quarto is a game between 2 players placing pieces on a 4x4 board. An `_` marks an empty square.
The goal is to place the final piece in a row, column, or diagonal of 4 pieces that share a common categorization.
A player can only place the piece given to them by their opponent on the previous turn.
In our version of Quarto, each of the 16 pieces is a unique letter from the set `potudahiPOTUDAHI`, and they are categorized by 4 binary distinctions:
- Upper case: P, O, T, U, D, A, H, I
  - vs lower case: p, o, t, u, d, a, h, i
- Vowel: o, u, a, i, O, U, A, I
  - vs consonant: p, t, d, h, P, T, D, H
- Hole: p, o, d, a, P, O, D, A
  - vs no hole: t, u, h, i, T, U, H, I
- Early: d, a, h, i, D, A, H, I
  - vs late half of alphabet: p, o, t, u, P, O, T, U

Gameplay:
- p1 starts by choosing a piece for p2 to play. Eg: `give T`
- p2 places that piece and chooses one for p1 to play. Eg: `place b2 give h`
- p1 places that piece and chooses one for p2 to play. Eg: `place b1 give t`
- Continue alternating turns until someone wins or the board is full

Win Condition:
The player who completes a row, column, or diagonal of pieces that share a common categorization wins.
For example, if p1 places an H to complete a row with u, h, and I, then they win because all of those pieces are letters without holes.
