from dataclasses import dataclass


@dataclass(frozen=True)
class Problem:
    path: str
    location: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.location}: {self.message}"