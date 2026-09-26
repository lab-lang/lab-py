"""An SBOL part identity."""

from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True, slots=True)
class Part:
    """An SBOL part identity."""

    iri: str

    def __post_init__(self) -> None:
        parsed = urlsplit(self.iri)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or not parsed.path.strip("/")
        ):
            raise ValueError(f"Part IRI must be an absolute http(s) URI, got {self.iri!r}.")
