# Telephone

Telephone is a game of communication and quirks.

## Roles
* **Source (p0):** Chooses the initial message to pass down the line.
* **Judge (p1):** Chooses their own quirk and participates as the first player in the chain. At the end, reviews the entire chain of messages and judges everyone's performance.
* **Players (p2 to pN):** Choose their own unique quirks. Receive a message from the previous player, adapt it according to their chosen quirk while preserving its core meaning, and pass it to the next player.

## Gameplay
1. **Choose Quirks:** Each player (from p1 to pN) sequentially chooses their own quirk by issuing `quirk <description>`.
2. **Choose Message:** The Source (p0) writes the starting message.
3. **Pass Message:** Each player (starting with p1) receives the message, rewrites it in their quirky style, and submits it.
4. **Judge:** Once the last player submits their message, the Judge (p1) sees the entire history, picks a winner based on message preservation and roleplay, and outputs their verdict as `winner pN <reason>`.
