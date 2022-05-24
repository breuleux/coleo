"""Demonstrate subcommands.

Example usage:
  python multi.py greet --name Olivier --greeting Bonjour
  python multi.py calc add 10 20
  python multi.py calc pow -b 2 -e 10

"""

from coleo import Option, auto_cli, default


@auto_cli
class main:
    """Interface with multiple subcommands."""

    class calc:
        """Calculate something."""

        def add():
            """Add two numbers together."""
            # The two numbers to add
            # [positional: 2]
            num: Option & int
            x, y = num
            return x + y

        def mul():
            """Multiply two numbers together."""
            # The two numbers to multiply
            # [positional: 2]
            num: Option & int
            x, y = num
            return x * y

        def pow():
            """Compute the base to the exponent."""
            # Base of the operation
            # [alias: -b]
            base: Option & int
            # Exponent of the operation
            # [alias: -e]
            exponent: Option & int
            return base**exponent

    def greet():
        """Greet someone."""
        # The greeting
        greeting: Option = default("Hello")
        # The name to greet
        name: Option = default("you")
        return f"{greeting}, {name}!"
