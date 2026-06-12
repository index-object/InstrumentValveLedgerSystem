from typing import Optional


class ColumnMapper:
    def __init__(self, synonyms: Optional[dict[str, list[str]]] = None):
        self._synonyms: dict[str, list[str]] = synonyms or {}
        self._reverse_map: dict[str, str] = {}
        self._build_reverse_map()

    def _build_reverse_map(self) -> None:
        for standard, variants in self._synonyms.items():
            for variant in variants:
                self._reverse_map[variant] = standard

    def resolve(self, column_name: Optional[str]) -> Optional[str]:
        if not column_name:
            return column_name
        s = column_name.strip()
        if s in self._reverse_map:
            return self._reverse_map[s]
        return s

    def map_row(
        self,
        row: dict[str, str],
        column_mapping: dict[str, str],
    ) -> dict[str, str]:
        result = {}
        for excel_col, model_attr in column_mapping.items():
            resolved = self.resolve(excel_col)
            resolved_synonyms = (
                [resolved] + self._synonyms.get(resolved, [])
                if resolved != excel_col
                else [excel_col] + self._synonyms.get(excel_col, [])
            )

            found_value = None
            for candidate in resolved_synonyms:
                if candidate in row and row[candidate].strip():
                    found_value = row[candidate].strip()
                    break

            for raw_col, val in row.items():
                if val.strip():
                    std = self.resolve(raw_col)
                    if std == resolved or std == excel_col:
                        found_value = val.strip()
                        break

            if found_value:
                result[model_attr] = found_value

        return result

    def map_rows(
        self,
        rows: list[dict[str, str]],
        column_mapping: dict[str, str],
    ) -> list[dict[str, str]]:
        return [self.map_row(row, column_mapping) for row in rows]

    @staticmethod
    def build_mapping(type_config: dict) -> dict[str, str]:
        return type_config.get("column_mapping", {})
