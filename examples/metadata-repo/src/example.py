# === CONTRACTS ===
# id: double_nonnegative
#   given: a nonnegative integer
#   then: return twice the supplied value
#   class: behavior
# === END CONTRACTS ===


def double(value: int) -> int:
    """Return twice the supplied value."""
    return value * 2


def main() -> None:
    """Print the double of four."""
    print(double(4))
