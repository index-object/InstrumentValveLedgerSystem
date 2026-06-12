import os
import yaml
import pytest

from app.import_engine.mapper import ColumnMapper


class TestColumnMapper:
    def _make_mapper(self):
        synonyms_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "app", "import_engine", "config", "synonyms.yaml",
        )
        with open(synonyms_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return ColumnMapper(data.get("synonyms", {}))

    def test_exact_column_name_match(self):
        mapper = self._make_mapper()
        assert mapper.resolve("位号") == "位号"
        assert mapper.resolve("设备名称") == "设备名称"

    def test_synonym_match(self):
        mapper = self._make_mapper()
        assert mapper.resolve("设备分级") == "设备等级"
        assert mapper.resolve("tag_no") == "位号"
        assert mapper.resolve("制造厂") == "生产厂家"

    def test_synonym_with_whitespace(self):
        mapper = self._make_mapper()
        assert mapper.resolve(" 设备分级 ") == "设备等级"
        assert mapper.resolve("设备等级（A/B/C）") == "设备等级"

    def test_no_match_returns_original(self):
        mapper = self._make_mapper()
        assert mapper.resolve("完全不存在的列名") == "完全不存在的列名"

    def test_empty_or_none(self):
        mapper = self._make_mapper()
        assert mapper.resolve("") == ""
        assert mapper.resolve(None) is None

    def test_map_row_basic(self):
        mapper = self._make_mapper()
        row = {"位号": "TAG-001", "设备名称": "压力表", "设备分级": "A"}
        column_mapping = {
            "位号": "tag_no",
            "设备名称": "device_name",
            "设备等级": "device_grade",
        }
        result = mapper.map_row(row, column_mapping)
        assert result["tag_no"] == "TAG-001"
        assert result["device_name"] == "压力表"
        assert result["device_grade"] == "A"

    def test_map_row_skips_unmapped_columns(self):
        mapper = self._make_mapper()
        row = {"位号": "TAG-001", "备注": "something", "无关列": "xxx"}
        column_mapping = {"位号": "tag_no"}
        result = mapper.map_row(row, column_mapping)
        assert result["tag_no"] == "TAG-001"
        assert "无关列" not in result
        assert "备注" not in result

    def test_map_row_empty_values_excluded(self):
        mapper = self._make_mapper()
        row = {"位号": "TAG-001", "设备名称": "", "生产厂家": ""}
        column_mapping = {
            "位号": "tag_no",
            "设备名称": "device_name",
            "生产厂家": "manufacturer",
        }
        result = mapper.map_row(row, column_mapping)
        assert result["tag_no"] == "TAG-001"
        assert "device_name" not in result
        assert "manufacturer" not in result

    def test_map_rows_batch(self):
        mapper = self._make_mapper()
        rows = [
            {"位号": "TAG-001", "设备分级": "A"},
            {"位号": "TAG-002", "设备分级": "B"},
        ]
        column_mapping = {"位号": "tag_no", "设备等级": "device_grade"}
        results = mapper.map_rows(rows, column_mapping)
        assert len(results) == 2
        assert results[0]["tag_no"] == "TAG-001"
        assert results[0]["device_grade"] == "A"
        assert results[1]["tag_no"] == "TAG-002"

    def test_synonym_applied_in_map_row(self):
        mapper = self._make_mapper()
        row = {"仪表位号": "TAG-001", "制造厂家": "某某公司"}
        column_mapping = {"位号": "tag_no", "生产厂家": "manufacturer"}
        result = mapper.map_row(row, column_mapping)
        assert result["tag_no"] == "TAG-001"
        assert result["manufacturer"] == "某某公司"

    def test_unknown_columns_still_mapped_to_default(self):
        mapper = self._make_mapper()
        row = {"位号": "TAG-001", "extra_col": "value"}
        column_mapping = {"位号": "tag_no", "extra_col": "extra_field"}
        result = mapper.map_row(row, column_mapping)
        assert result["tag_no"] == "TAG-001"
        assert result["extra_field"] == "value"

    def test_build_mapping_from_type_config(self):
        type_config = {
            "column_mapping": {
                "位号": "tag_no",
                "设备名称": "device_name",
                "设备等级": "device_grade",
            }
        }
        result = ColumnMapper.build_mapping(type_config)
        assert result == {
            "位号": "tag_no",
            "设备名称": "device_name",
            "设备等级": "device_grade",
        }

    def test_build_mapping_missing_key(self):
        result = ColumnMapper.build_mapping({})
        assert result == {}
