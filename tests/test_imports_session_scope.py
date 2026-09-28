# coding=utf-8
"""台账导入（/imports）会话 Cookie 容量回归测试。

背景：/imports 曾把解析错误（``import_errors``）、同批次重复的用户选择
（``import_conflict_choices``）、跳过明细（``import_skipped``）直接写进 Flask
的签名 Cookie 会话。会话 Cookie 上限约 4KB（Werkzeug 上限 4093 字节），数据
量一大就被浏览器静默丢弃，后续步骤读不到状态，用户会看到「找不到已上传的
文件」或状态错乱。现在这些数据都存服务器端，会话里只留一个随机 token。

这里用假引擎替换真实解析，只验证路由层与会话的交互，避免依赖分类器。
"""

import io

import pytest

from app import db
from app.import_engine.engine import ImportResult, SheetImportResult
from app.models import User
from app.devices.types.pressure_transmitter import PressureTransmitter


SHEET = "压力变送器"
TYPE_CODE = "pressure_transmitter"


def _login(client):
    return client.post("/login", data={"username": "user1", "password": "user123"})


def _xlsx_upload(filename="台账.xlsx"):
    """路由只负责把文件落盘，内容由假引擎接管，最小字节流即可。"""
    return (io.BytesIO(b"fake-xlsx-bytes"), filename)


def _cookie_bytes(response):
    """响应里 Set-Cookie 的总字节数；浏览器会丢弃超过 4093 字节的会话 Cookie。"""
    return sum(len(s) for s in response.headers.getlist("Set-Cookie"))


def _make_records(app, count):
    with app.app_context():
        user_id = User.query.filter_by(username="user1").first().id
    return [
        PressureTransmitter(
            装置名称="气化装置", 位号=f"PT-{i:04d}", 设备名称=f"变送器{i}",
            status="draft", created_by=user_id,
        )
        for i in range(count)
    ]


def _make_result(records, errors=None):
    sheet = SheetImportResult(
        sheet_name=SHEET, type_key=SHEET, type_code=TYPE_CODE, type_name="远传压力",
        row_count=len(records), records=records,
        headers=["装置名称", "位号", "设备名称"], sample_rows=[],
    )
    return ImportResult(sheets=[sheet], total_records=len(records), errors=list(errors or []))


class _FakeEngine:
    """始终返回同一份构造好的解析结果，让路由逻辑可被精确验证。"""

    def __init__(self, result):
        self._result = result

    def import_file(self, filepath, type_overrides=None):
        return self._result


@pytest.fixture
def patch_engine(monkeypatch):
    def _patch(result):
        monkeypatch.setattr("app.routes.imports.get_engine", lambda: _FakeEngine(result))
    return _patch


class TestImportsSessionScope:
    def test_upload_does_not_store_parse_errors_in_session(self, app, client, init_database, patch_engine):
        """2000 条解析错误（真实台账文件的量级）不再进会话，预览页仍能显示"""
        errors = [f"第 {i} 行：位号缺失，已跳过该行" for i in range(2000)]
        patch_engine(_make_result([], errors=errors))

        _login(client)
        resp = client.post("/imports/upload", data={"file": _xlsx_upload()},
                           content_type="multipart/form-data")
        assert resp.status_code == 302
        assert _cookie_bytes(resp) < 4093

        page = client.get("/imports/preview")
        assert page.status_code == 200
        assert "位号缺失" in page.get_data(as_text=True)

    def test_execute_does_not_store_skipped_details_in_session(self, app, client, init_database, patch_engine):
        """2000 条被跳过的明细（真实台账文件的量级）不再撑爆会话，列表页仍完整展示"""
        count = 2000
        patch_engine(_make_result(_make_records(app, count)))

        # 预置同（装置名称 + 位号）的已有设备，导入时按「数据库中已存在」跳过
        with app.app_context():
            for record in _make_records(app, count):
                db.session.add(record)
            db.session.commit()

        _login(client)
        client.post("/imports/upload", data={"file": _xlsx_upload()},
                    content_type="multipart/form-data")
        resp = client.post("/imports/execute", data={
            f"dedup_mode_{SHEET}": "skip",
            f"ledger_name_{SHEET}": "测试台账",
        })
        assert resp.status_code == 302
        assert _cookie_bytes(resp) < 4093

        page = client.get(resp.headers["Location"]).get_data(as_text=True)
        assert f"{count} 条数据被跳过" in page
        assert "数据库中已存在" in page

    def test_conflict_choices_roundtrip_keeps_session_small(self, app, client, init_database, patch_engine):
        """同批次重复的用户选择经服务器端存取后仍然生效"""
        records = _make_records(app, 4)
        records[1].位号 = records[0].位号
        records[3].位号 = records[2].位号
        patch_engine(_make_result(records))

        _login(client)
        resp = client.post("/imports/upload", data={"file": _xlsx_upload()},
                           content_type="multipart/form-data")
        assert resp.status_code == 302
        assert "/imports/conflicts" in resp.headers["Location"]
        assert _cookie_bytes(resp) < 4093

        assert client.get("/imports/conflicts").status_code == 200

        resp = client.post("/imports/resolve-conflicts", data={
            f"choice_{SHEET}__气化装置|PT-0000": 1,
            f"choice_{SHEET}__气化装置|PT-0002": 3,
        })
        assert resp.status_code == 302
        assert _cookie_bytes(resp) < 4093

        # 选择被读回并应用：保留重复组里的第 2 行，不再报冲突
        resp = client.get("/imports/preview")
        assert resp.status_code == 200

    def test_execute_without_upload_shows_friendly_message(self, app, client, init_database):
        _login(client)
        resp = client.post("/imports/execute", data={}, follow_redirects=True)
        assert resp.status_code == 200
        assert "找不到已上传的文件" in resp.get_data(as_text=True)


class TestConflictChoiceHelpers:
    def test_load_without_token_returns_empty(self, app, client):
        with app.test_request_context("/imports/preview"):
            from app.routes.imports import _load_conflict_choices
            assert _load_conflict_choices() == {}

    def test_bogus_token_returns_empty(self, app):
        from flask import session
        from app.routes.imports import _load_conflict_choices
        with app.test_request_context("/imports/preview"):
            session["import_conflict_choices_token"] = "../../etc/passwd"
            assert _load_conflict_choices() == {}

    def test_save_and_load_roundtrip(self, app):
        from app.routes.imports import _save_conflict_choices, _load_conflict_choices, _clear_conflict_choices
        choices = {SHEET: {"气化装置|PT-0000": 2}}
        with app.test_request_context("/imports/resolve-conflicts"):
            _save_conflict_choices(choices)
            assert _load_conflict_choices() == choices
            _clear_conflict_choices()
            assert _load_conflict_choices() == {}
