import pytest
import io
import os
import time
from openpyxl import Workbook

from app import db
from app.models import User, MaintenanceRecord


def _login(client, username, password):
    return client.post("/login", data={"username": username, "password": password})


def _xlsx_stream(rows):
    """把二维行数据打包成可上传的 xlsx 字节流。"""
    wb = Workbook()
    ws = wb.active
    ws.append(["装置名称", "设备位号", "设备名称", "检修时间", "检修内容", "检修人员", "类型"])
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    wb.close()
    buf.seek(0)
    return buf


def _cookie_bytes(response):
    """响应里 Set-Cookie 的总字节数；浏览器会静默丢弃超过 4093 字节的会话 Cookie。"""
    return sum(len(s) for s in response.headers.getlist("Set-Cookie"))


def _seed_devices(app, count):
    from app.devices.types.pressure_transmitter import PressureTransmitter

    with app.app_context():
        user = User.query.filter_by(username="user1").first()
        for i in range(count):
            db.session.add(PressureTransmitter(
                装置名称="气化装置", 位号=f"PT-{i:04d}", 设备名称=f"变送器{i}",
                status="approved", created_by=user.id,
            ))
        db.session.commit()


class TestParseExcel:
    def test_parse_valid_file(self, tmp_path):
        from app.routes.maintenance_import import _parse_xlsx

        wb = Workbook()
        ws = wb.active
        ws.title = "维护记录"
        ws.append(["装置名称", "设备位号", "设备名称", "检修时间", "检修内容", "检修人员", "类型"])
        ws.append(["气化装置", "PT-001", "压力变送器", "2025-03-15", "更换膜片", "张三", "大修"])
        ws.append(["气化装置", "PT-002", "压力变送器", "2025-04-01", "校准", "李四", "小修"])
        filepath = str(tmp_path / "test.xlsx")
        wb.save(filepath)
        wb.close()

        records = _parse_xlsx(filepath)
        assert len(records) == 2
        assert records[0]["装置名称"] == "气化装置"
        assert records[0]["设备位号"] == "PT-001"
        assert records[0]["检修人员"] == "张三"

    def test_parse_empty_rows_skipped(self, tmp_path):
        from app.routes.maintenance_import import _parse_xlsx

        wb = Workbook()
        ws = wb.active
        ws.append(["装置名称", "设备位号"])
        ws.append(["气化装置", "PT-001"])
        ws.append([None, None])
        ws.append(["", ""])
        ws.append(["合成装置", "TT-002"])
        filepath = str(tmp_path / "test.xlsx")
        wb.save(filepath)
        wb.close()

        records = _parse_xlsx(filepath)
        assert len(records) == 2

    def test_parse_missing_required_columns(self, tmp_path):
        from app.routes.maintenance_import import _parse_xlsx

        wb = Workbook()
        ws = wb.active
        ws.append(["装置名称", "设备位号"])
        ws.append(["", "PT-001"])
        ws.append(["气化装置", ""])
        ws.append(["气化装置", "PT-002"])
        filepath = str(tmp_path / "test.xlsx")
        wb.save(filepath)
        wb.close()

        records = _parse_xlsx(filepath)
        assert len(records) == 1
        assert records[0]["设备位号"] == "PT-002"

    def test_parse_header_only_file(self, tmp_path):
        from app.routes.maintenance_import import _parse_xlsx

        wb = Workbook()
        ws = wb.active
        ws.append(["装置名称", "设备位号"])
        filepath = str(tmp_path / "test.xlsx")
        wb.save(filepath)
        wb.close()

        records = _parse_xlsx(filepath)
        assert len(records) == 0

    def test_parse_empty_file(self, tmp_path):
        from app.routes.maintenance_import import _parse_xlsx

        wb = Workbook()
        ws = wb.active
        filepath = str(tmp_path / "test.xlsx")
        wb.save(filepath)
        wb.close()

        records = _parse_xlsx(filepath)
        assert len(records) == 0


class TestImportIntegration:
    """纯单元测试，绕过 fixtures 和数据库，直接测试 resolve_device 和 import 的逻辑函数"""

    def test_resolve_device_missing_args(self):
        from app.utils.device_lookup import resolve_device
        assert resolve_device("装置", "/") is None
        assert resolve_device("装置", "") is None
        assert resolve_device("装置", "-") is None
        assert resolve_device("装置", "\\") is None
        assert resolve_device("", "TAG") is None
        assert resolve_device(None, "TAG") is None
        assert resolve_device("装置", None) is None

    def test_parse_datetime(self):
        from app.routes.maintenance_import import _parse_datetime
        from datetime import datetime

        d = _parse_datetime("2025-03-15")
        assert d is not None
        assert d.year == 2025 and d.month == 3 and d.day == 15

        d = _parse_datetime("2025-03-15 14:30:00")
        assert d is not None
        assert d.hour == 14 and d.minute == 30

        d = _parse_datetime("")
        assert d is None

        d = _parse_datetime(None)
        assert d is None

        d = _parse_datetime("2025/03/15")
        assert d is not None
        assert d.year == 2025 and d.month == 3 and d.day == 15

    def test_get_type_name(self):
        from app.routes.maintenance_import import _get_type_name
        name = _get_type_name("control_valve")
        assert name is not None
        assert isinstance(name, str)
        assert len(name) > 0

    def test_get_type_name_unknown(self):
        from app.routes.maintenance_import import _get_type_name
        assert _get_type_name("nonexistent_type") == "nonexistent_type"

    def test_check_duplicate_none_when_no_dt(self):
        from app.routes.maintenance_import import _check_duplicate
        assert _check_duplicate("装置", "TAG", "") is False
        assert _check_duplicate("装置", "TAG", None) is False

    def test_duplicate_filtered_in_preview(self, app):
        from app.routes.maintenance_import import _check_duplicate
        with app.app_context():
            assert _check_duplicate("x", "y", "2025-01-01") is False


# ========== 回归：大文件导入不再撑爆会话 Cookie ==========
#
# 上传时曾把整份解析结果（raw/matched/unmatched/ambiguous/duplicates）
# 写进 Flask 的签名 Cookie 会话。会话 Cookie 上限约 4KB，文件稍大就会被
# 浏览器静默丢弃，用户点「确认导入」只会看到「找不到已上传的文件，请重新
# 上传」。现在解析结果存服务器端，会话里只留一个 token。


class TestLargeImportSessionCookie:
    def test_large_upload_session_cookie_stays_small(self, app, client, init_database):
        """120 条记录的导入，上传与执行两步的会话 Cookie 都必须低于浏览器上限"""
        count = 120
        _seed_devices(app, count)
        _login(client, "user1", "user123")

        rows = [["气化装置", f"PT-{i:04d}", f"变送器{i}", "2025-03-15",
                 f"更换膜片并校验密封面第{i}次", "张三", "大修"] for i in range(count)]
        resp = client.post(
            "/maintenance/import/upload",
            data={"file": (_xlsx_stream(rows), "检修记录.xlsx")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        assert "已匹配" in resp.get_data(as_text=True)
        assert _cookie_bytes(resp) < 4093

        resp = client.post("/maintenance/import/execute",
                           data={"unmatched_action": "skip"}, follow_redirects=True)
        assert _cookie_bytes(resp) < 4093

        body = resp.get_data(as_text=True)
        assert "导入完成" in body
        assert "找不到已上传的文件" not in body
        with app.app_context():
            assert MaintenanceRecord.query.count() == count

    def test_many_skipped_rows_reported_and_cookie_small(self, app, client, init_database):
        """大量未匹配行的「跳过明细」同样不能撑爆会话 Cookie"""
        # 取 300 条：未匹配行字段少、压缩率高，120 条时旧实现刚好还没超限，
        # 300 条才会超过 4093（实测旧实现上传环节约 7KB）。
        count = 300
        _login(client, "user1", "user123")

        rows = [["不存在装置", f"XX-{i:04d}", "-", "2025-03-16",
                 f"内容{i}", "李四", "小修"] for i in range(count)]
        upload_resp = client.post(
            "/maintenance/import/upload",
            data={"file": (_xlsx_stream(rows), "未匹配.xlsx")},
            content_type="multipart/form-data",
        )
        assert _cookie_bytes(upload_resp) < 4093

        resp = client.post("/maintenance/import/execute", data={"unmatched_action": "skip"})
        assert _cookie_bytes(resp) < 4093

        page = client.get(resp.headers["Location"]).get_data(as_text=True)
        assert f"{count} 条数据被跳过" in page
        assert "不存在装置" in page

    def test_execute_without_upload_shows_friendly_message(self, app, client, init_database):
        """没有上传记录时提交，给可读提示而不是 500"""
        _login(client, "user1", "user123")
        resp = client.post("/maintenance/import/execute",
                           data={"unmatched_action": "skip"}, follow_redirects=True)
        assert resp.status_code == 200
        assert "找不到已上传的文件" in resp.get_data(as_text=True)

    def test_execute_token_consumed_once(self, app, client, init_database):
        """token 一次性消费，重复提交同一预览不会重复导入"""
        _seed_devices(app, 1)
        _login(client, "user1", "user123")
        rows = [["气化装置", "PT-0000", "变送器0", "2025-03-15", "更换膜片", "张三", "大修"]]
        client.post(
            "/maintenance/import/upload",
            data={"file": (_xlsx_stream(rows), "单条.xlsx")},
            content_type="multipart/form-data",
        )
        client.post("/maintenance/import/execute", data={"unmatched_action": "skip"})
        resp = client.post("/maintenance/import/execute",
                           data={"unmatched_action": "skip"}, follow_redirects=True)
        assert "找不到已上传的文件" in resp.get_data(as_text=True)
        with app.app_context():
            assert MaintenanceRecord.query.count() == 1


class TestImportScratchStore:
    """服务器端中间数据存储的基础行为"""

    def test_save_load_delete_roundtrip(self, tmp_path):
        from app.utils.import_cache import save_scratch, load_scratch, delete_scratch

        data = {"raw": [{"装置名称": "气化装置"}], "中文键": "值"}
        token = save_scratch(str(tmp_path), data)
        assert load_scratch(str(tmp_path), token) == data

        delete_scratch(str(tmp_path), token)
        assert load_scratch(str(tmp_path), token) is None

    def test_illegal_token_rejected(self, tmp_path):
        from app.utils.import_cache import save_scratch, load_scratch, delete_scratch

        token = save_scratch(str(tmp_path), {"x": 1})
        # 非法 token 一律返回 None，且不会越出上传目录
        for bad in (None, "", "not-a-token", "../../etc/passwd", token.upper(), token[:8]):
            assert load_scratch(str(tmp_path), bad) is None
            delete_scratch(str(tmp_path), bad)  # 不应抛异常
        assert load_scratch(str(tmp_path), token) == {"x": 1}

    def test_scratch_files_hidden_from_import_cache(self, tmp_path):
        from app.utils.import_cache import save_scratch, get_import_cache_files

        save_scratch(str(tmp_path), {"x": 1})
        assert get_import_cache_files(str(tmp_path)) == []

    def test_cleanup_scratch_removes_expired_only(self, tmp_path):
        from app.utils.import_cache import save_scratch, load_scratch, cleanup_scratch

        expired = save_scratch(str(tmp_path), {"old": True})
        fresh = save_scratch(str(tmp_path), {"old": False})
        old_time = time.time() - 25 * 3600
        os.utime(os.path.join(str(tmp_path), f"_scratch_{expired}.json"), (old_time, old_time))

        assert cleanup_scratch(str(tmp_path)) == 1
        assert load_scratch(str(tmp_path), expired) is None
        assert load_scratch(str(tmp_path), fresh) == {"old": False}

