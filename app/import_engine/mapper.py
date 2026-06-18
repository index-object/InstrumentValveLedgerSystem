from typing import Optional


class ColumnMapper:
    # 常见后缀，按长度降序排列避免短后缀提前匹配
    _UNIT_SUFFIXES = [
        "（mm）", "(mm)", "MPa", "Mpa", "KPa", "kPa", "Kpa", "mm",
        "℃", "%",
    ]

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

    def _clean_col(self, s: str) -> str:
        return s.replace("\r", "").replace("\n", "").strip()

    @classmethod
    def _strip_unit(cls, s: str) -> str:
        for suffix in cls._UNIT_SUFFIXES:
            if s.endswith(suffix):
                return s[: -len(suffix)]
        return s

    def map_row(
        self,
        row: dict[str, str],
        column_mapping: dict[str, str],
    ) -> dict[str, str]:
        result = {}
        cleaned_row = {self._clean_col(k): v for k, v in row.items()}

        for excel_col, model_attr in column_mapping.items():
            resolved = self.resolve(excel_col)
            resolved_synonyms = (
                [resolved] + self._synonyms.get(resolved, [])
                if resolved != excel_col
                else [excel_col] + self._synonyms.get(excel_col, [])
            )

            found_value = None
            for candidate in resolved_synonyms:
                if candidate in cleaned_row and cleaned_row[candidate].strip():
                    found_value = cleaned_row[candidate].strip()
                    break

            for raw_col, val in cleaned_row.items():
                if val.strip():
                    std = self.resolve(raw_col)
                    if std == resolved or std == excel_col:
                        found_value = val.strip()
                        break
                    if "." in raw_col:
                        sub = raw_col.rsplit(".", 1)[-1]
                        if sub != raw_col:
                            c_std = self.resolve(sub)
                            if c_std == resolved or c_std == excel_col:
                                found_value = val.strip()
                                break
                            if sub in resolved_synonyms:
                                found_value = val.strip()
                                break
                        merged = raw_col.replace(".", "")
                        c_std = self.resolve(merged)
                        if c_std == resolved or c_std == excel_col:
                            found_value = val.strip()
                            break
                        if merged in resolved_synonyms:
                            found_value = val.strip()
                            break

            if found_value:
                result[model_attr] = found_value
                continue

            for raw_col, val in cleaned_row.items():
                if not val.strip():
                    continue
                stripped = self._strip_unit(raw_col)
                if stripped and stripped != raw_col:
                    c_std = self.resolve(stripped)
                    if c_std == resolved or c_std == excel_col:
                        found_value = val.strip()
                        break
                    if stripped in resolved_synonyms:
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
