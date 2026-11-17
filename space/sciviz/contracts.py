from dataclasses import dataclass


class SciVizError(ValueError):
    """A short, safe error that can be shown alongside the visitor's input."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class Article:
    title: str
    text: str
    source_url: str | None
    source_kind: str
    truncated: bool = False
