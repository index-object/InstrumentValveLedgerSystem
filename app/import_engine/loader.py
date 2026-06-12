from typing import Any, Optional


class DataLoader:
    def create_record(self, model_class: type, data: dict[str, str]) -> Any:
        record = model_class()
        for key, val in data.items():
            if hasattr(record, key) and val is not None:
                try:
                    setattr(record, key, val)
                except Exception:
                    pass
        return record

    def create_records(
        self,
        model_class: type,
        rows: list[dict[str, str]],
    ) -> list[Any]:
        records = [self.create_record(model_class, row) for row in rows]
        records.sort(key=lambda r: self._sort_key(r))
        return records

    def _sort_key(self, record: Any) -> tuple:
        for attr in ("sequence_no", "序号"):
            val = getattr(record, attr, None)
            if val is not None:
                try:
                    return (0, int(val))
                except (ValueError, TypeError):
                    return (1, str(val))
        return (2, "")
