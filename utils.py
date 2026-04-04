from datetime import datetime


def ts() -> str:
    """Return a [HH:MM:SS] timestamp prefix for console output."""
    return datetime.now().strftime("[%H:%M:%S]")


def log(msg: str = "", **kwargs) -> None:
    """print() with a timestamp prefix on every line."""
    for line in str(msg).splitlines() or [""]:
        print(f"{ts()} {line}", **kwargs)
