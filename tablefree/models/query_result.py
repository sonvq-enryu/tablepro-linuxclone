from dataclasses import dataclass


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[list[object]]
    column_types: list[str]
    row_count: int
    duration_ms: float
    error: str | None = None
    affected_rows: int = 0
