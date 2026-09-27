# coding=utf-8
# encoding: utf-8
from __future__ import unicode_literals

import json


def _login(client, username, password):
    return client.post("/login", data={"username": username, "password": password})


def _create_plan(client, title="Test Plan", rows=None):
    if rows is None:
        rows = [{
            "devices": [{"type": "control_valve", "id": 1, "tag": "FV-001", "name": "测试调节阀"}],
            "planned_date_end": "2026-12-31",
            "maintenance_project": "阀体检修",
            "maintenance_scheme": "解体检查",
            "safety_measures": "办理作业票",
            "project_leader": "张伟",
            "maintenance_leader": "李强",
            "quality_acceptance": "",
            "remark": "",
        }]
    return client.post("/plan/new", data={
        "title": title,
        "description": "desc",
        "rows_json": json.dumps(rows),
    }, follow_redirects=True)


def test_plan_list_requires_login(client, init_database):
    resp = client.get("/plans")
    assert resp.status_code == 302


def test_leader_creates_plan(client, init_database):
    _login(client, "admin", "admin123")
    resp = _create_plan(client, "2026 Plan")
    assert resp.status_code == 200
    assert "2026 Plan" in resp.data.decode("utf-8")


def test_leader_publishes_plan(client, init_database):
    _login(client, "admin", "admin123")
    _create_plan(client, "Test Plan")
    resp = client.post("/plan/1/publish", follow_redirects=True)
    assert resp.status_code == 200


def test_employee_sees_published_plan(client, init_database):
    _login(client, "admin", "admin123")
    _create_plan(client, "Employee View Plan")
    client.post("/plan/1/publish", follow_redirects=True)
    _login(client, "user1", "user123")
    resp = client.get("/plans")
    assert resp.status_code == 200
    assert "Employee View Plan" in resp.data.decode("utf-8")


def test_plan_detail_renders(client, init_database):
    _login(client, "admin", "admin123")
    _create_plan(client, "Detail Test")
    resp = client.get("/plan/1")
    assert resp.status_code == 200
    text = resp.data.decode("utf-8")
    assert "Detail Test" in text
    assert "FV-001" in text
    assert "阀体检修" in text


def test_leader_archives_plan(client, init_database):
    _login(client, "admin", "admin123")
    _create_plan(client, "Archive Test")
    client.post("/plan/1/publish", follow_redirects=True)
    resp = client.post("/plan/1/archive", follow_redirects=True)
    assert resp.status_code == 200


def test_employee_cannot_create_plan(client, init_database):
    _login(client, "user1", "user123")
    resp = client.post("/plan/new", data={"title": "Should Not Work"}, follow_redirects=True)
    assert resp.status_code == 200
    text = resp.data.decode("utf-8")
    assert "无权" in text or resp.request.path != "/plans"


def test_create_requires_at_least_one_row(client, init_database):
    _login(client, "admin", "admin123")
    resp = client.post("/plan/new", data={"title": "Empty", "rows_json": "[]"}, follow_redirects=True)
    assert resp.status_code == 200
    assert "请至少添加一行" in resp.data.decode("utf-8")


def test_multiple_devices_flatten_into_items(client, init_database):
    _login(client, "admin", "admin123")
    rows = [{
        "devices": [
            {"type": "control_valve", "id": 1, "tag": "FV-001", "name": "调节阀一"},
            {"type": "onoff_valve", "id": 2, "tag": "XV-002", "name": "开关阀二"},
        ],
        "planned_date_end": "2026-10-01",
        "maintenance_project": "年度检修",
        "maintenance_scheme": "",
        "safety_measures": "",
        "project_leader": "",
        "maintenance_leader": "",
        "quality_acceptance": "",
        "remark": "",
    }]
    _create_plan(client, "Multi Row", rows)
    resp = client.get("/plan/1")
    text = resp.data.decode("utf-8")
    assert "FV-001" in text
    assert "XV-002" in text


def test_edit_plan_updates_rows(client, init_database):
    _login(client, "admin", "admin123")
    _create_plan(client, "Edit Test")
    rows = [{
        "devices": [{"type": "control_valve", "id": 3, "tag": "PV-003", "name": "新阀"}],
        "planned_date_end": "2026-11-11",
        "maintenance_project": "更换膜片",
        "maintenance_scheme": "",
        "safety_measures": "",
        "project_leader": "",
        "maintenance_leader": "",
        "quality_acceptance": "",
        "remark": "",
    }]
    resp = client.post("/plan/1/edit", data={
        "title": "Edit Test Updated",
        "description": "",
        "rows_json": json.dumps(rows),
    }, follow_redirects=True)
    assert resp.status_code == 200
    text = resp.data.decode("utf-8")
    assert "Edit Test Updated" in text
    assert "PV-003" in text
    assert "FV-001" not in text


def test_edit_form_prefills_existing_rows(client, init_database):
    _login(client, "admin", "admin123")
    rows = [{
        "devices": [{"type": "control_valve", "id": 1, "tag": "FV-001", "name": "调节阀一"}],
        "planned_date_end": "2026-12-31",
        "maintenance_project": "阀体检修",
        "maintenance_scheme": "解体检查",
        "safety_measures": "办理作业票",
        "project_leader": "张伟",
        "maintenance_leader": "李强",
        "quality_acceptance": "",
        "remark": "",
    }]
    _create_plan(client, "Prefill Test", rows)
    resp = client.get("/plan/1/edit")
    assert resp.status_code == 200
    text = resp.data.decode("utf-8")
    assert "initGroups" in text
    assert '"2026-12-31"' in text
    assert "\\u9600\\u4f53\\u68c0\\u4fee" in text
    assert "\\u5f20\\u4f1f" in text
    assert "\\u674e\\u5f3a" in text


# ========== 维护记录关联计划项 ==========

def _create_approved_valve(db, tag="FV-001"):
    from app.devices.types.control_valve import ControlValve
    valve = ControlValve(位号=tag, 名称="测试调节阀", status="approved", created_by=1)
    db.session.add(valve)
    db.session.commit()
    return valve.id


def _create_maintenance(client, valve_id, plan_item_id=""):
    return client.post("/maintenance/new", data={
        "valve_id": valve_id,
        "valve_type": "control_valve",
        "类型": "保养",
        "检修时间": "2026-08-01",
        "检修人员": "张三",
        "检修内容": "完成计划项",
        "plan_item_id": plan_item_id,
    }, follow_redirects=True)


def test_maintenance_links_and_completes_plan_item(client, init_database):
    db = init_database
    valve_id = _create_approved_valve(db)
    _login(client, "admin", "admin123")
    rows = [{
        "devices": [{"type": "control_valve", "id": valve_id, "tag": "FV-001", "name": "测试调节阀"}],
        "planned_date_end": "2026-12-31",
        "maintenance_project": "年度检修",
        "maintenance_scheme": "",
        "safety_measures": "",
        "project_leader": "",
        "maintenance_leader": "",
        "quality_acceptance": "",
        "remark": "",
    }]
    _create_plan(client, "Link Plan", rows)
    client.post("/plan/1/publish", follow_redirects=True)

    _login(client, "user1", "user123")
    resp = _create_maintenance(client, valve_id, plan_item_id="1")
    assert resp.status_code == 200

    from app.models import MaintenanceRecord, MaintenancePlanItem
    record = MaintenanceRecord.query.first()
    item = MaintenancePlanItem.query.get(1)
    assert record is not None
    assert item.maintenance_id == record.id
    assert item.status == "completed"


def test_maintenance_edit_unlinks_plan_item(client, init_database):
    db = init_database
    valve_id = _create_approved_valve(db)
    _login(client, "admin", "admin123")
    rows = [{
        "devices": [{"type": "control_valve", "id": valve_id, "tag": "FV-001", "name": "测试调节阀"}],
        "planned_date_end": "2026-12-31",
        "maintenance_project": "年度检修",
        "maintenance_scheme": "",
        "safety_measures": "",
        "project_leader": "",
        "maintenance_leader": "",
        "quality_acceptance": "",
        "remark": "",
    }]
    _create_plan(client, "Link Plan", rows)
    client.post("/plan/1/publish", follow_redirects=True)

    _login(client, "user1", "user123")
    _create_maintenance(client, valve_id, plan_item_id="1")

    from app.models import MaintenanceRecord, MaintenancePlanItem
    record = MaintenanceRecord.query.first()
    resp = client.post(f"/maintenance/edit/{record.id}", data={
        "valve_id": valve_id,
        "valve_type": "control_valve",
        "类型": "保养",
        "检修时间": "2026-08-02",
        "检修人员": "张三",
        "检修内容": "修改后内容",
        "plan_item_id": "",
    }, follow_redirects=True)
    assert resp.status_code == 200
    item = MaintenancePlanItem.query.get(1)
    assert item.maintenance_id is None
    assert item.status == "pending"


def test_completed_maintenance_after_deadline_shows_overdue(client, init_database):
    db = init_database
    valve_id = _create_approved_valve(db)
    _login(client, "admin", "admin123")
    rows = [{
        "devices": [{"type": "control_valve", "id": valve_id, "tag": "FV-001", "name": "测试调节阀"}],
        "planned_date_end": "2026-07-31",
        "maintenance_project": "年度检修",
        "maintenance_scheme": "",
        "safety_measures": "",
        "project_leader": "",
        "maintenance_leader": "",
        "quality_acceptance": "",
        "remark": "",
    }]
    _create_plan(client, "Overdue Plan", rows)
    client.post("/plan/1/publish", follow_redirects=True)

    _login(client, "user1", "user123")
    _create_maintenance(client, valve_id, plan_item_id="1")

    from app.models import MaintenancePlanItem
    item = MaintenancePlanItem.query.get(1)
    assert item.status == "completed"
    assert item.maintenance_record.检修时间.date() > item.planned_date_end

def test_non_valve_plan_item_confirmed_without_maintenance(client, init_database):
    db = init_database
    from app.devices.types.flow_meter import FlowMeter
    device = FlowMeter(位号="FM-001", 设备名称="测试流量计", 装置名称="装置A", status="approved", created_by=1)
    db.session.add(device)
    db.session.commit()
    device_id = device.id

    _login(client, "admin", "admin123")
    rows = [{
        "devices": [{"type": "flow_meter", "id": device_id, "tag": "FM-001", "name": "测试流量计"}],
        "planned_date_end": "2026-12-31",
        "maintenance_project": "流量计检修",
        "maintenance_scheme": "",
        "safety_measures": "",
        "project_leader": "",
        "maintenance_leader": "",
        "quality_acceptance": "",
        "remark": "",
    }]
    _create_plan(client, "Non-Valve Plan", rows)
    client.post("/plan/1/publish", data={"recipient_ids": [2]}, follow_redirects=True)

    client.get("/logout")
    _login(client, "user1", "user123")
    resp = client.post("/plan/1/confirm-item/1", follow_redirects=True)
    assert resp.status_code == 200

    from app.models import MaintenancePlanItem
    item = MaintenancePlanItem.query.get(1)
    assert item.status == "completed"
    assert item.maintenance_id is None
    assert item.completed_by == 2  # user1 id

    _login(client, "admin", "admin123")
    resp = client.get("/plan/1")
    text = resp.data.decode("utf-8")
    assert "已完成" in text


def test_non_valve_plan_overdue_by_completed_at(client, init_database):
    db = init_database
    from app.devices.types.flow_meter import FlowMeter
    device = FlowMeter(位号="FM-002", 设备名称="测试流量计2", 装置名称="装置A", status="approved", created_by=1)
    db.session.add(device)
    db.session.commit()
    device_id = device.id

    _login(client, "admin", "admin123")
    rows = [{
        "devices": [{"type": "flow_meter", "id": device_id, "tag": "FM-002", "name": "测试流量计2"}],
        "planned_date_end": "2026-07-31",
        "maintenance_project": "流量计检修",
        "maintenance_scheme": "",
        "safety_measures": "",
        "project_leader": "",
        "maintenance_leader": "",
        "quality_acceptance": "",
        "remark": "",
    }]
    _create_plan(client, "Overdue Non-Valve Plan", rows)
    client.post("/plan/1/publish", data={"recipient_ids": [2]}, follow_redirects=True)

    client.get("/logout")
    _login(client, "user1", "user123")
    resp = client.post("/plan/1/confirm-item/1", follow_redirects=True)
    assert resp.status_code == 200

    from app.models import MaintenancePlanItem
    item = MaintenancePlanItem.query.get(1)
    assert item.status == "completed"
    assert item.completed_at.date() > item.planned_date_end

    _login(client, "admin", "admin123")
    resp = client.get("/plan/1")
    text = resp.data.decode("utf-8")
    assert "已逾期" in text
    assert "1 逾期" in text


def test_confirm_item_only_for_non_valve(client, init_database):
    db = init_database
    from app.devices.types.control_valve import ControlValve
    valve = ControlValve(位号="FV-003", 名称="测试调节阀", status="approved", created_by=1)
    db.session.add(valve)
    db.session.commit()
    valve_id = valve.id

    _login(client, "admin", "admin123")
    rows = [{
        "devices": [{"type": "control_valve", "id": valve_id, "tag": "FV-003", "name": "测试调节阀"}],
        "planned_date_end": "2026-12-31",
        "maintenance_project": "年度检修",
        "maintenance_scheme": "",
        "safety_measures": "",
        "project_leader": "",
        "maintenance_leader": "",
        "quality_acceptance": "",
        "remark": "",
    }]
    _create_plan(client, "Valve Plan", rows)
    client.post("/plan/1/publish", data={"recipient_ids": [2]}, follow_redirects=True)

    client.get("/logout")
    _login(client, "user1", "user123")
    resp = client.post("/plan/1/confirm-item/1", follow_redirects=True)
    assert resp.status_code == 200
    text = resp.data.decode("utf-8")
    assert "阀门类型需通过维护记录完成" in text

    from app.models import MaintenancePlanItem
    item = MaintenancePlanItem.query.get(1)
    assert item.status == "pending"


def test_non_valve_plan_list_shows_all_instruments(client, init_database):
    db = init_database
    _login(client, "admin", "admin123")
    from app.devices.types.flow_meter import FlowMeter
    device = FlowMeter(位号="FM-003", 设备名称="测试流量计3", 装置名称="装置A", status="approved", created_by=1)
    db.session.add(device)
    db.session.commit()

    rows = [{
        "devices": [{"type": "flow_meter", "id": device.id, "tag": "FM-003", "name": "测试流量计3"}],
        "planned_date_end": "2026-12-31",
        "maintenance_project": "流量计检修",
        "maintenance_scheme": "",
        "safety_measures": "",
        "project_leader": "",
        "maintenance_leader": "",
        "quality_acceptance": "",
        "remark": "",
    }]
    resp = _create_plan(client, "All Instruments Plan", rows)
    assert resp.status_code == 200
    text = resp.data.decode("utf-8")
    assert "FM-003" in text

