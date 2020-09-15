"""Simplest example of a Coleo CLI.

Example usage:
  python hello.py
  python hello.py --name Gunther --greeting Danke

"""

from coleo import Option, auto_cli, default


@auto_cli
def main():
    # The greeting
    greeting: Option = default("Hello")

    # The name to greet
    name: Option = default("you")

    return f"{greeting}, {name}!"
