"""Simple script.

Example usage:
  python guess.py
  python guess.py --minimum 1 --maximum 10 --rounds 3

To see all options:
  python guess.py -h

"""

import random

from coleo import Option, auto_cli, default, tooled


@tooled
def guess():
    # Minimal possible number
    minimum: Option & int = default(0)
    # Maximal possible number
    maximum: Option & int = default(100)

    # [group: whimsy]
    # Maximal number of tries
    maxtries: Option & int = default(10)

    # Force the number to guess (defaults to random)
    target: Option & int = default(random.randint(minimum, maximum))

    assert minimum <= target <= maximum

    print(f"Please guess a number between {minimum} and {maximum}")
    for i in range(maxtries):
        guess = float(input("? "))
        if guess == target:
            print("Yes! :D")
            return True
        elif i == maxtries - 1:
            print("You failed :(")
            return False
        elif guess < target:
            print("Too low. Guess again.")
        elif guess > target:
            print("Too high. Guess again.")


@auto_cli
def main():
    """Guessing game"""
    # Number of rounds of guessing
    rounds: Option & int = default(1)

    for i in range(rounds):
        guess()
