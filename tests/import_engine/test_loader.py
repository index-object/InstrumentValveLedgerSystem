import pytest

from app.import_engine.loader import DataLoader


class MockModel:
    tag_no: str = ""
    device_name: str = ""
    sequence_no: str = ""
    status: str = ""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestDataLoader:
    def test_create_record(self):
        model_cls = MockModel
        data = {"tag_no": "TAG-001", "device_name": "压力表"}
        loader = DataLoader()
        record = loader.create_record(model_cls, data)
        assert record.tag_no == "TAG-001"
        assert record.device_name == "压力表"

    def test_create_record_with_extra_fields(self):
        model_cls = MockModel
        data = {"tag_no": "TAG-001", "nonexistent_field": "should_not_exist"}
        loader = DataLoader()
        record = loader.create_record(model_cls, data)
        assert record.tag_no == "TAG-001"
        assert not hasattr(record, "nonexistent_field")

    def test_create_multiple_records(self):
        model_cls = MockModel
        rows = [
            {"tag_no": "TAG-001"},
            {"tag_no": "TAG-002"},
        ]
        loader = DataLoader()
        records = loader.create_records(model_cls, rows)
        assert len(records) == 2
        assert records[0].tag_no == "TAG-001"
        assert records[1].tag_no == "TAG-002"

    def test_sort_by_sequence(self):
        model_cls = MockModel
        rows = [
            {"sequence_no": "3", "tag_no": "TAG-003"},
            {"sequence_no": "1", "tag_no": "TAG-001"},
            {"sequence_no": "2", "tag_no": "TAG-002"},
        ]
        loader = DataLoader()
        records = loader.create_records(model_cls, rows)
        assert records[0].tag_no == "TAG-001"
        assert records[1].tag_no == "TAG-002"
        assert records[2].tag_no == "TAG-003"

    def test_create_nonexistent_field_skipped(self):
        model_cls = MockModel
        data = {"tag_no": "TAG-001", "__nonexistent__": "should_be_skipped"}
        loader = DataLoader()
        record = loader.create_record(model_cls, data)
        assert record.tag_no == "TAG-001"
        assert not hasattr(record, "__nonexistent__")

    def test_empty_rows_list(self):
        model_cls = MockModel
        loader = DataLoader()
        records = loader.create_records(model_cls, [])
        assert records == []
