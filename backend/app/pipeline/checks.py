"""Check records shared by every stage of the pipeline."""

from dataclasses import asdict, dataclass

PASS, WARN, FAIL, UNVERIFIABLE = "pass", "warn", "fail", "unverifiable"


@dataclass
class Check:
    id: str
    group: str  # file | geometry | face | pose | background | lighting | checklist
    label: str
    status: str
    message: str
    stage: str = "output"  # input | output
    basis: str = "verified"  # verified (MFA sheet) | provisional (PhotoGen threshold)
    measured: float | str | None = None
    expected: str | None = None
    unit: str | None = None
    remedy: str | None = None  # retake | adjust | None

    def as_dict(self) -> dict:
        d = asdict(self)
        if isinstance(d["measured"], float):
            d["measured"] = round(d["measured"], 2)
        return d


def worst(checks: list[Check]) -> str:
    statuses = {c.status for c in checks}
    for s in (FAIL, WARN):
        if s in statuses:
            return s
    return PASS
