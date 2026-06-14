from dataclasses import dataclass, field


@dataclass
class VerificationResult:
    mismatches: list[dict] = field(default_factory=list)
    summary_data: list[dict] = field(default_factory=list)
    actual_counts: dict[str, dict[str, int]] = field(default_factory=dict)


class SummaryVerifier:

    def parse_summary(self, summary_rows: list[dict]) -> list[dict]:
        results = []
        for row in summary_rows:
            entry = {"unit_name": "", "grade_a": 0, "grade_b": 0, "grade_c": 0}
            for key, val in row.items():
                k = key.strip()
                v = str(val).strip() if val is not None else "0"
                if "装置" in k or "中心" in k or "名称" in k:
                    entry["unit_name"] = v
                elif "A" in k or "a" in k:
                    entry["grade_a"] = self._parse_int(v)
                elif "B" in k or "b" in k:
                    entry["grade_b"] = self._parse_int(v)
                elif "C" in k or "c" in k:
                    entry["grade_c"] = self._parse_int(v)
            if entry["unit_name"]:
                results.append(entry)
        return results

    def verify(
        self,
        summary_rows: list[dict],
        actual_records: list,
        grade_attr: str = "设备等级",
    ) -> VerificationResult:
        result = VerificationResult()

        if not summary_rows:
            return result

        summary_data = self.parse_summary(summary_rows)
        result.summary_data = summary_data

        for rec in actual_records:
            grade = getattr(rec, grade_attr, "") or ""
            type_key = type(rec).__tablename__
            if type_key not in result.actual_counts:
                result.actual_counts[type_key] = {"A": 0, "B": 0, "C": 0}
            g = grade.strip().upper()
            if g in ("A", "B", "C"):
                result.actual_counts[type_key][g] += 1

        for entry in summary_data:
            for type_key, counts in result.actual_counts.items():
                mismatches = self.compare(entry, counts, entry["unit_name"])
                result.mismatches.extend(mismatches)

        return result

    @staticmethod
    def compare(
        expected: dict,
        actual: dict[str, int],
        unit_name: str = "",
    ) -> list[dict]:
        mismatches = []
        grade_map = [("A", "grade_a"), ("B", "grade_b"), ("C", "grade_c")]
        for grade_short, grade_key in grade_map:
            exp = expected.get(grade_key, 0)
            act = actual.get(grade_short, 0)
            if exp != act:
                mismatches.append({
                    "unit": unit_name,
                    "grade": grade_short,
                    "expected": exp,
                    "actual": act,
                })
        return mismatches

    @staticmethod
    def _parse_int(val: str) -> int:
        try:
            return int(float(val.replace(",", "").strip()))
        except (ValueError, AttributeError):
            return 0
