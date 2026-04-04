# Wordle Protocol

This directory contains the protocol for playing Wordle between an Agent (Guesser) and a User (Host).

## Objective
The Guesser attempts to identify a secret 5-letter word chosen by the Host within 6 tries.

## Game Loop

1. **Guesser** states a 5-letter word.
   * Format: Just the word, bolded (e.g., **ARISE**).

2. **Host** evaluates the guess and replies with an SxPB snippet.
   * The snippet MUST include the specific guess line (`guessN`) and the `pinned` state.
   * **Case Sensitivity Matters:**
     * **UPPERCASE** in `guessN`: Letter is present in the secret word (Yellow or Green).
     * **lowercase** in `guessN`: Letter is absent from the secret word (Gray).
   * **Pinned:** Shows only letters in the correct position (Green). Use `_` for unknown slots.

   **Example Host Reply:**
   ```sxpb
   (guess1 (()) A R I s e) ; A, R, I are in the word. s, e are not.
   (pinned (()) _ _ _ _ _) ; No letters are in the correct spot yet.
   ```

3. **Guesser** updates the full game state and makes the next guess.
   * The Guesser outputs the **entire** board state in a code block.
   * The board tracks:
     * All previous guesses.
     * `pinned`: The current "Green" structure.
     * `present`: List of letters known to be in the word (Yellow/Green).
     * `absent`: List of letters known to be excluded (Gray).
   * After the block, the Guesser states the next word.

## Data Structures

### `guessN`
A list of 5 characters representing a specific attempt.
* `T` (Upper): Present in word.
* `t` (Lower): Absent from word.

### `pinned`
A list of 5 characters representing the known structure.
* `T`: Correct letter in correct spot (Green).
* `_`: Unknown.

### `present` / `absent`
Helper lists for the AI to track constraints.
* `present`: Union of all UPPERCASE letters seen so far.
* `absent`: Union of all lowercase letters seen so far.

## Example Session

**Guesser:** **STARE**

**Host:**
```sxpb
(guess1 (()) s t A r E)
(pinned (()) _ _ _ _ E)
```

**Guesser:**
```sxpb
(board
 (guess1 (()) s t A r E)
 ...
 (pinned (()) _ _ _ _ E)
)
(present (()) A E)
(absent (()) R S T)
(guess_count 1)
```
My next guess is: **PLACE**
