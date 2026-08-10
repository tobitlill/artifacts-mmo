from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    x: int = 0
    y: int = 0
