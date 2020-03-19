"""Simple script.

Example usage:
  python guess.py
  python guess.py --minimum 1 --maximum 10 --rounds 3

To see all options:
  python guess.py -h

"""

import random

from coleo import Argument, auto_cli, default, tooled


@tooled
def guess():
    # Minimal possible number
    minimum: Argument & int = default(0)
    # Maximal possible number
    maximum: Argument & int = default(100)
    # Maximal number of tries
    maxtries: Argument & int = default(10)

    # Force the number to guess (defaults to random)
    target: Argument & int = default(random.randint(minimum, maximum))

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


@tooled
def main():
    # Number of rounds of guessing
    rounds: Argument & int = default(1)

    for i in range(rounds):
        guess()


if __name__ == "__main__":
    auto_cli(main, description="Guessing game")
