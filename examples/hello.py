"""Simplest example of a Coleo CLI.

Example usage:
  python hello.py
  python hello.py --name Gunther --greeting Danke

"""

from coleo import Argument, auto_cli, default


@auto_cli
def main():
    # The greeting
    greeting: Argument = default("Hello")

    # The name to greet
    name: Argument = default("you")

    return f"{greeting}, {name}!"
