import random
import os


def get_random_word():
    # Primary location for the word list
    wordlist_path = os.path.expanduser("~/.local/share/wordle/words.txt")
    if os.path.exists(wordlist_path):
        with open(wordlist_path, "r") as f:
            words = [line.strip().upper() for line in f if len(line.strip()) == 5]

        # Avoid obvious plurals and keep it to relatively common words
        common_targets = [w for w in words if not w.endswith("S") and len(set(w)) >= 4]
        if common_targets:
            return random.choice(common_targets)
        return random.choice(words)

    # Fallback to a hardcoded list
    fallback = [
        "BRAIN",
        "LIGHT",
        "DREAM",
        "POWER",
        "FLAME",
        "STARE",
        "CRANE",
        "PLANT",
        "SHINE",
        "GHOST",
        "BREAD",
    ]
    return random.choice(fallback)


if __name__ == "__main__":
    print(get_random_word())
