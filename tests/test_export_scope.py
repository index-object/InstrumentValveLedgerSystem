# coding=utf-8
"""导出范围（按用户区分）回归测试。

背景：导出入口过去不区分用户——员工在列表页只能看到自己创建的数据，
但"导出"会把全系统数据都导出去；勾选导出（ids）还会完全绕过状态与
归属过滤，等于给任何登录用户开了导出他人草稿 / 待审批数据的后门。
这里锁定修复后的口径：导出范围 = 该用户在当前页面能看到的数据。
"""

import io

import pandas as pd

from app import db
from app.models import User, Ledger, MaintenanceRecord
from app.devices.types.control_valve import ControlValve
from app.devices.types.pressure_transmitter import PressureTransmitter


def _login(client, username, password):
    return client.post("/login", data={"username": username, "password": password})


def _rows(response):
    """把 xlsx 响应解析成行字典列表（空表返回空列表）。"""
    df = pd.read_excel(io.BytesIO(response.data))
    return [] if df.empty else df.to_dict("records")


def _new_employee(name, real_name):
    user = User(username=name, role="employee", real_name=real_name, dept="维修部")
    user.set_password("password")
    db.session.add(user)
    db.session.flush()
    return user


# ========== 维护记录导出 ==========


def _seed_maintenance(app):
    with app.app_context():
        user1 = User.query.filter_by(username="user1").first()
        user2 = _new_employee("export_user2", "员工乙")
        mine = MaintenanceRecord(
            device_type="control_valve", device_id=9001,
            设备位号="MV-001", 设备名称="我的记录", 检修内容="我的检修", created_by=user1.id,
        )
        other = MaintenanceRecord(
            device_type="control_valve", device_id=9002,
            设备位号="MV-002", 设备名称="他人记录", 检修内容="他人检修", created_by=user2.id,
        )
        db.session.add_all([mine, other])
        db.session.commit()
        return mine.id, other.id


def test_employee_maintenance_export_only_own(app, client, init_database):
    """员工导出维护记录时只应看到自己创建的记录"""
    _seed_maintenance(app)

    _login(client, "user1", "user123")
    resp = client.get("/maintenance/export")
    assert resp.status_code == 200

    rows = _rows(resp)
    assert [r["设备位号"] for r in rows] == ["MV-001"]
    assert rows[0]["创建人"] == "张三"


def test_employee_maintenance_export_ids_cannot_escape(app, client, init_database):
    """员工勾选他人的维护记录 id 导出时应被拒绝，不能绕过归属限制"""
    _, other_id = _seed_maintenance(app)

    _login(client, "user1", "user123")
    resp = client.get(f"/maintenance/export?ids={other_id}")
    assert resp.status_code == 200
    assert _rows(resp) == []


def test_admin_maintenance_export_sees_all(app, client, init_database):
    """管理员导出维护记录时可以看到全部记录"""
    _seed_maintenance(app)

    _login(client, "admin", "admin123")
    rows = _rows(client.get("/maintenance/export"))
    assert {r["设备位号"] for r in rows} == {"MV-001", "MV-002"}


def test_maintenance_export_respects_search(app, client, init_database):
    """导出应套用当前搜索条件，与列表页看到的一致"""
    _seed_maintenance(app)

    _login(client, "admin", "admin123")
    rows = _rows(client.get("/maintenance/export?search=他人检修"))
    assert [r["设备位号"] for r in rows] == ["MV-002"]


# ========== 非阀门仪表导出 ==========


def _seed_devices(app):
    with app.app_context():
        user1 = User.query.filter_by(username="user1").first()
        user2 = _new_employee("export_user2", "员工乙")
        mine = PressureTransmitter(
            位号="PT-001", 设备名称="我的变送器", status="approved", created_by=user1.id
        )
        other = PressureTransmitter(
            位号="PT-002", 设备名称="他人变送器", status="approved", created_by=user2.id
        )
        db.session.add_all([mine, other])
        db.session.commit()
        return mine.id, other.id


def test_employee_device_export_only_own(app, client, init_database):
    """员工导出仪表数据时只应看到自己创建的数据（与列表页一致）"""
    _seed_devices(app)

    _login(client, "user1", "user123")
    rows = _rows(client.get("/device/pressure_transmitter/export"))
    assert [r["位号"] for r in rows] == ["PT-001"]


def test_employee_device_export_ids_cannot_escape(app, client, init_database):
    """员工勾选他人的仪表 id 导出时应被过滤"""
    _, other_id = _seed_devices(app)

    _login(client, "user1", "user123")
    rows = _rows(
        client.get(f"/device/pressure_transmitter/export?ids={other_id}")
    )
    assert rows == []


def test_admin_device_export_sees_all(app, client, init_database):
    """管理员导出仪表数据时可以看到全部数据"""
    _seed_devices(app)

    _login(client, "admin", "admin123")
    rows = _rows(client.get("/device/pressure_transmitter/export"))
    assert {r["位号"] for r in rows} == {"PT-001", "PT-002"}


# ========== 阀门台账导出 ==========


def _seed_ledger_valves(app):
    with app.app_context():
        user1 = User.query.filter_by(username="user1").first()
        user2 = _new_employee("export_user2", "员工乙")
        ledger = Ledger(名称="导出测试台账", 类型="control_valve", created_by=user1.id)
        db.session.add(ledger)
        db.session.flush()

        own_draft = ControlValve(
            ledger_id=ledger.id, 位号="CV-OWN", 名称="本人草稿",
            status="draft", created_by=user1.id,
        )
        other_draft = ControlValve(
            ledger_id=ledger.id, 位号="CV-OTHER-DRAFT", 名称="他人草稿",
            status="draft", created_by=user2.id,
        )
        other_approved = ControlValve(
            ledger_id=ledger.id, 位号="CV-OTHER-APPROVED", 名称="他人已审批",
            status="approved", created_by=user2.id,
        )
        db.session.add_all([own_draft, other_draft, other_approved])
        db.session.commit()
        return {
            "ledger_id": ledger.id,
            "own_draft": own_draft.id,
            "other_draft": other_draft.id,
            "other_approved": other_approved.id,
        }


def test_employee_valve_export_mine_scope(app, client, init_database):
    """「我的台账」导出包含本人草稿与全员可见的已审批数据，不含他人草稿"""
    ids = _seed_ledger_valves(app)

    _login(client, "user1", "user123")
    rows = _rows(
        client.get(
            "/export",
            query_string={
                "device_type": "control_valve",
                "from": "mine",
                "ledger_id": ids["ledger_id"],
            },
        )
    )
    assert {r["位号"] for r in rows} == {"CV-OWN", "CV-OTHER-APPROVED"}


def test_employee_valve_export_ids_cannot_escape(app, client, init_database):
    """在完整可见范围内勾选他人草稿 id，也必须被导出权限拦下"""
    ids = _seed_ledger_valves(app)

    _login(client, "user1", "user123")
    rows = _rows(
        client.get(
            "/export",
            query_string={
                "device_type": "control_valve",
                "from": "mine",
                "ledger_id": ids["ledger_id"],
                "ids": str(ids["other_draft"]),
            },
        )
    )
    assert rows == []


def test_valve_export_all_scope_only_approved(app, client, init_database):
    """「全部台账」入口导出只含已审批数据，与列表页口径一致"""
    ids = _seed_ledger_valves(app)

    _login(client, "user1", "user123")
    rows = _rows(
        client.get(
            "/export",
            query_string={
                "device_type": "control_valve",
                "ledger_id": ids["ledger_id"],
            },
        )
    )
    assert {r["位号"] for r in rows} == {"CV-OTHER-APPROVED"}


def test_valve_export_status_filter_matches_list(app, client, init_database):
    """显式状态筛选下导出与列表一样放开快照限制，但仍按用户收口"""
    ids = _seed_ledger_valves(app)

    _login(client, "user1", "user123")
    rows = _rows(
        client.get(
            "/export",
            query_string={
                "device_type": "control_valve",
                "ledger_id": ids["ledger_id"],
                "status": "draft",
            },
        )
    )
    # 列表页会列出台账内全部草稿，员工导出时只保留自己创建的那份
    assert {r["位号"] for r in rows} == {"CV-OWN"}


def test_admin_valve_export_mine_scope_sees_all(app, client, init_database):
    """管理员在「我的台账」入口可以导出全部状态数据"""
    ids = _seed_ledger_valves(app)

    _login(client, "admin", "admin123")
    rows = _rows(
        client.get(
            "/export",
            query_string={
                "device_type": "control_valve",
                "from": "mine",
                "ledger_id": ids["ledger_id"],
            },
        )
    )
    assert {r["位号"] for r in rows} == {"CV-OWN", "CV-OTHER-DRAFT", "CV-OTHER-APPROVED"}


def test_export_filename_is_utf8_encoded(app, client, init_database):
    """中文文件名使用 RFC 6266 编码，避免下载文件名丢失上下文"""
    ids = _seed_ledger_valves(app)

    _login(client, "user1", "user123")
    resp = client.get(
        "/export",
        query_string={
            "device_type": "control_valve",
            "from": "mine",
            "ledger_id": ids["ledger_id"],
        },
    )
    disposition = resp.headers["Content-Disposition"]
    assert "filename*=UTF-8''" in disposition


# ========== 非阀门台账误用阀门导出入口 ==========


def test_valve_export_redirects_for_non_valve_type(app, client, init_database):
    """非阀门类型命中阀门导出入口时应转交设备导出，而不是 500"""
    with app.app_context():
        user1 = User.query.filter_by(username="user1").first()
        ledger = Ledger(名称="压力变送器台账", 类型="pressure_transmitter", created_by=user1.id)
        db.session.add(ledger)
        db.session.flush()
        db.session.add(
            PressureTransmitter(
                ledger_id=ledger.id, 位号="PT-100", 设备名称="变送器",
                status="approved", created_by=user1.id,
            )
        )
        db.session.commit()
        ledger_id = ledger.id

    _login(client, "user1", "user123")
    resp = client.get(
        "/export",
        query_string={"device_type": "pressure_transmitter", "ledger_id": ledger_id},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert [r["位号"] for r in _rows(resp)] == ["PT-100"]
