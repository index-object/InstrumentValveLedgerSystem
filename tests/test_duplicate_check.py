import pytest
from app.utils.duplicate_check import check_duplicate


class _Expr:
    """比较表达式，携带字段名、操作符和值"""
    def __init__(self, field, op, value):
        self.field = field
        self.op = op
        self.value = value


class _Column:
    """模拟 SQLAlchemy 列属性，支持 == 和 != 比较"""
    def __set_name__(self, owner, name):
        self.name = name
    def __eq__(self, other):
        return _Expr(self.name, "eq", other)
    def __ne__(self, other):
        return _Expr(self.name, "ne", other)


class MockDevice:
    id: int = 0
    装置名称: str = ""
    位号: str = ""
    status: str = "draft"

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class MockQuery:
    def __init__(self, records):
        self.records = records

    def filter(self, *args):
        result = list(self.records)
        for arg in args:
            if isinstance(arg, _Expr):
                if arg.op == "ne":
                    result = [r for r in result if getattr(r, arg.field, None) != arg.value]
                elif arg.op == "eq":
                    result = [r for r in result if getattr(r, arg.field, None) == arg.value]
        self.records = result
        return self

    def first(self):
        return self.records[0] if self.records else None


class TestCheckDuplicate:
    def test_duplicate_found(self):
        class FakeModel:
            装置名称 = _Column()
            位号 = _Column()
            status = _Column()
            query = MockQuery([
                MockDevice(装置名称="装置A", 位号="TAG-001", status="approved")
            ])
        assert check_duplicate(FakeModel, "装置A", "TAG-001") is True

    def test_no_duplicate(self):
        class FakeModel:
            装置名称 = _Column()
            位号 = _Column()
            status = _Column()
            query = MockQuery([])
        assert check_duplicate(FakeModel, "装置A", "TAG-999") is False

    def test_draft_excluded(self):
        class FakeModel:
            装置名称 = _Column()
            位号 = _Column()
            status = _Column()
            query = MockQuery([
                MockDevice(装置名称="装置A", 位号="TAG-001", status="draft")
            ])
        assert check_duplicate(FakeModel, "装置A", "TAG-001") is False

    def test_exclude_id(self):
        dev = MockDevice(id=1, 装置名称="装置A", 位号="TAG-001", status="approved")
        class FakeModel:
            装置名称 = _Column()
            位号 = _Column()
            status = _Column()
            id = _Column()
            query = MockQuery([dev])
        assert check_duplicate(FakeModel, "装置A", "TAG-001", exclude_id=1) is False

    def test_empty_unit_name_returns_false(self):
        class FakeModel:
            装置名称 = _Column()
            位号 = _Column()
            status = _Column()
            query = MockQuery([])
        assert check_duplicate(FakeModel, "", "TAG-001") is False

    def test_empty_tag_no_returns_false(self):
        class FakeModel:
            装置名称 = _Column()
            位号 = _Column()
            status = _Column()
            query = MockQuery([])
        assert check_duplicate(FakeModel, "装置A", "") is False
