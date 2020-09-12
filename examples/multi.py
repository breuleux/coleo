"""Demonstrate subcommands.

Example usage:
  python multi.py greet --name Olivier --greeting Bonjour
  python multi.py calc add 10 20
  python multi.py calc pow -b 2 -e 10

"""

from coleo import Argument, auto_cli, default


@auto_cli
class main:
    """Interface with multiple subcommands."""

    class calc:
        """Calculate something."""

        def add():
            """Add two numbers together."""
            # The two numbers to add
            # [positional: 2]
            num: Argument & int
            x, y = num
            return x + y

        def mul():
            """Multiply two numbers together."""
            # The two numbers to multiply
            # [positional: 2]
            num: Argument & int
            x, y = num
            return x * y

        def pow():
            """Compute the base to the exponent."""
            # Base of the operation
            # [alias: -b]
            base: Argument & int
            # Exponent of the operation
            # [alias: -e]
            exponent: Argument & int
            return base ** exponent

    def greet():
        """Greet someone."""
        # The greeting
        greeting: Argument = default("Hello")
        # The name to greet
        name: Argument = default("you")
        return f"{greeting}, {name}!"
