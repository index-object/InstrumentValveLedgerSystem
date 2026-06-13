import pytest

from app.import_engine.verifier import SummaryVerifier, VerificationResult


class MockRecord:
    __tablename__ = "mock_table"

    def __init__(self, grade="", tablename=None):
        self.设备等级 = grade
        if tablename:
            self.__tablename__ = tablename


class TestSummaryVerifier:
    def test_parse_summary_basic(self):
        verifier = SummaryVerifier()
        rows = [
            {"装置名称": "气化装置", "A级": "5", "B级": "10", "C级": "3"},
            {"装置名称": "合成装置", "A级": "2", "B级": "8", "C级": "1"},
        ]
        result = verifier.parse_summary(rows)
        assert len(result) == 2
        assert result[0]["unit_name"] == "气化装置"
        assert result[0]["grade_a"] == 5
        assert result[0]["grade_b"] == 10
        assert result[0]["grade_c"] == 3
        assert result[1]["unit_name"] == "合成装置"

    def test_parse_summary_varied_column_names(self):
        verifier = SummaryVerifier()
        rows = [
            {"中心": "动力中心", "A": "3", "B": "2", "C": "1"},
        ]
        result = verifier.parse_summary(rows)
        assert len(result) == 1
        assert result[0]["unit_name"] == "动力中心"
        assert result[0]["grade_a"] == 3

    def test_parse_summary_empty(self):
        verifier = SummaryVerifier()
        assert verifier.parse_summary([]) == []

    def test_verify_no_summary_returns_empty(self):
        verifier = SummaryVerifier()
        result = verifier.verify([], [MockRecord("A")])
        assert len(result.mismatches) == 0
        assert result.actual_counts == {}

    def test_verify_counts_correctly(self):
        verifier = SummaryVerifier()
        records = [
            MockRecord("A"),
            MockRecord("B"),
            MockRecord("C"),
            MockRecord("A"),
            MockRecord("invalid"),
        ]
        result = verifier.verify(
            [{"装置名称": "装置1", "A级": "2", "B级": "1", "C级": "1"}],
            records,
        )
        assert result.actual_counts["mock_table"]["A"] == 2
        assert result.actual_counts["mock_table"]["B"] == 1
        assert result.actual_counts["mock_table"]["C"] == 1

    def test_verify_mismatch_detected(self):
        verifier = SummaryVerifier()
        records = [
            MockRecord("A"),
            MockRecord("A"),
            MockRecord("B"),
        ]
        summary = [{"装置名称": "装置1", "A级": "1", "B级": "1", "C级": "1"}]
        result = verifier.verify(summary, records)
        actual = result.actual_counts["mock_table"]
        expected = result.summary_data[0]
        mismatches = SummaryVerifier.compare(expected, actual, "装置1")
        assert len(mismatches) > 0
        assert any(m["unit"] == "装置1" for m in mismatches)
        assert any(m["grade"] == "A" for m in mismatches)

    def test_compare_exact_match(self):
        expected = {"unit_name": "装置1", "grade_a": 2, "grade_b": 1, "grade_c": 3}
        actual = {"A": 2, "B": 1, "C": 3}
        mismatches = SummaryVerifier.compare(expected, actual, "装置1")
        assert mismatches == []

    def test_compare_with_diff(self):
        expected = {"unit_name": "装置1", "grade_a": 5, "grade_b": 2, "grade_c": 1}
        actual = {"A": 3, "B": 2, "C": 1}
        mismatches = SummaryVerifier.compare(expected, actual, "装置1")
        assert len(mismatches) == 1
        assert mismatches[0]["grade"] == "A"
        assert mismatches[0]["expected"] == 5
        assert mismatches[0]["actual"] == 3

    def test_parse_int_cleanup(self):
        verifier = SummaryVerifier()
        assert verifier._parse_int("5") == 5
        assert verifier._parse_int("1,234") == 1234
        assert verifier._parse_int("") == 0
        assert verifier._parse_int("abc") == 0
        assert verifier._parse_int("3.0") == 3
