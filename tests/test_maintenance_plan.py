# coding=utf-8
# encoding: utf-8
from __future__ import unicode_literals

import json


def _login(client, username, password):
    return client.post("/login", data={"username": username, "password": password})


def _logout(client):
    return client.get("/logout")


def _row(devices, category="valve", start="2026-07-01", end="2026-12-31", **fields):
    """构造一行计划明细（新格式：含 category 与计划起止日期）"""
    row = {
        "category": category,
        "devices": devices,
        "planned_date_start": start,
        "planned_date_end": end,
        "maintenance_project": fields.get("maintenance_project", "阀体检修"),
        "maintenance_scheme": fields.get("maintenance_scheme", "解体检查"),
        "safety_measures": fields.get("safety_measures", "办理作业票"),
        "project_leader": fields.get("project_leader", "张伟"),
        "maintenance_leader": fields.get("maintenance_leader", "李强"),
        "quality_acceptance": fields.get("quality_acceptance", ""),
        "remark": fields.get("remark", ""),
    }
    if "group_id" in fields:
        row["group_id"] = fields["group_id"]
    return row


def _valve_device(device_id=1, tag="FV-001", name="测试调节阀"):
    return {"type": "control_valve", "id": device_id, "tag": tag, "name": name}


def _default_rows(device_id=1, tag="FV-001"):
    return [_row([_valve_device(device_id, tag)])]


def _create_plan(client, title="Test Plan", rows=None):
    if rows is None:
        rows = _default_rows()
    return client.post("/plan/new", data={
        "title": title,
        "description": "desc",
        "rows_json": json.dumps(rows),
    }, follow_redirects=True)


def _publish(client, plan_id=1, recipients="2"):
    """发布计划。必须选择通知对象，否则后端拒绝发布。"""
    data = {"recipient_ids": [recipients]} if recipients else {}
    return client.post(f"/plan/{plan_id}/publish", data=data, follow_redirects=True)


def _create_approved_valve(db, tag="FV-001"):
    from app.devices.types.control_valve import ControlValve
    valve = ControlValve(位号=tag, 名称="测试调节阀", status="approved", created_by=1)
    db.session.add(valve)
    db.session.commit()
    return valve.id


def _create_approved_instrument(db, tag="FM-001"):
    from app.devices.types.flow_meter import FlowMeter
    device = FlowMeter(位号=tag, 设备名称="测试流量计", 装置名称="装置A",
                       status="approved", created_by=1)
    db.session.add(device)
    db.session.commit()
    return device.id


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


# ========== 基础访问与权限 ==========

def test_plan_list_requires_login(client, init_database):
    resp = client.get("/plans")
    assert resp.status_code == 302


def test_leader_creates_plan(client, init_database):
    _login(client, "admin", "admin123")
    resp = _create_plan(client, "2026 Plan")
    assert resp.status_code == 200
    assert "2026 Plan" in resp.data.decode("utf-8")


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


# ========== 计划时间区间 ==========

def test_row_requires_full_date_range(client, init_database):
    """缺少计划开始日期时应被拒绝，而不是静默把起止写成同一天"""
    _login(client, "admin", "admin123")
    rows = [_row([_valve_device()])]
    rows[0]["planned_date_start"] = ""
    resp = client.post("/plan/new", data={
        "title": "缺日期", "rows_json": json.dumps(rows),
    }, follow_redirects=True)
    assert "未填写完整的计划开始/结束日期" in resp.data.decode("utf-8")


def test_row_rejects_reversed_date_range(client, init_database):
    _login(client, "admin", "admin123")
    rows = [_row([_valve_device()], start="2026-12-31", end="2026-07-01")]
    resp = client.post("/plan/new", data={
        "title": "倒置日期", "rows_json": json.dumps(rows),
    }, follow_redirects=True)
    assert "计划结束日期早于开始日期" in resp.data.decode("utf-8")


def test_plan_persists_date_range(client, init_database):
    db = init_database
    _login(client, "admin", "admin123")
    _create_plan(client, "区间计划", [_row([_valve_device()], start="2026-05-01", end="2026-05-15")])
    from app.models import MaintenancePlanGroup
    group = MaintenancePlanGroup.query.first()
    assert group.planned_date_start.isoformat() == "2026-05-01"
    assert group.planned_date_end.isoformat() == "2026-05-15"


# ========== 阀门 / 其他仪表分区 ==========

def test_valve_and_instrument_rows_split_into_groups(client, init_database):
    """阀门与仪表各自成为独立任务组，并按 category 标记"""
    db = init_database
    valve_id = _create_approved_valve(db)
    meter_id = _create_approved_instrument(db)
    _login(client, "admin", "admin123")
    rows = [
        _row([_valve_device(valve_id)], category="valve", start="2026-05-01", end="2026-05-15"),
        _row([{"type": "flow_meter", "id": meter_id, "tag": "FM-001", "name": "测试流量计"}],
             category="instrument", start="2026-06-01", end="2026-06-10"),
    ]
    _create_plan(client, "分类计划", rows)

    from app.models import MaintenancePlanGroup
    groups = {g.category: g for g in MaintenancePlanGroup.query.all()}
    assert set(groups) == {"valve", "instrument"}
    assert groups["valve"].items[0].device_type == "control_valve"
    assert groups["instrument"].items[0].device_type == "flow_meter"
    # 计划项冗余日期与所属任务组一致
    for g in groups.values():
        for item in g.items:
            assert item.planned_date_start == g.planned_date_start
            assert item.planned_date_end == g.planned_date_end


def test_row_rejects_device_of_wrong_category(client, init_database):
    """阀门行里混入仪表应被明确拒绝，避免完成路径混淆"""
    db = init_database
    meter_id = _create_approved_instrument(db)
    _login(client, "admin", "admin123")
    rows = [_row([{"type": "flow_meter", "id": meter_id, "tag": "FM-001", "name": "测试流量计"}],
                 category="valve")]
    resp = client.post("/plan/new", data={
        "title": "混放", "rows_json": json.dumps(rows),
    }, follow_redirects=True)
    assert "应属于" in resp.data.decode("utf-8")


def test_multiple_devices_share_one_group(client, init_database):
    db = init_database
    _login(client, "admin", "admin123")
    rows = [_row([
        _valve_device(1, "FV-001", "调节阀一"),
        {"type": "onoff_valve", "id": 2, "tag": "XV-002", "name": "开关阀二"},
    ])]
    _create_plan(client, "Multi Row", rows)

    from app.models import MaintenancePlanGroup, MaintenancePlanItem
    assert MaintenancePlanGroup.query.count() == 1
    assert MaintenancePlanItem.query.count() == 2


def test_detail_separates_valve_and_instrument(client, init_database):
    db = init_database
    valve_id = _create_approved_valve(db)
    meter_id = _create_approved_instrument(db)
    _login(client, "admin", "admin123")
    rows = [
        _row([_valve_device(valve_id)], category="valve"),
        _row([{"type": "flow_meter", "id": meter_id, "tag": "FM-001", "name": "测试流量计"}],
             category="instrument"),
    ]
    _create_plan(client, "分区展示", rows)
    text = client.get("/plan/1").data.decode("utf-8")
    assert "阀门检修任务" in text
    assert "其他仪表检修任务" in text
    assert "FV-001" in text and "FM-001" in text


# ========== 完成路径 ==========

def test_detail_offers_valve_completion_entry(client, init_database):
    """阀门任务必须给出直达维护记录的完成入口（用户反馈：不知道怎么完成）"""
    db = init_database
    valve_id = _create_approved_valve(db)
    _login(client, "admin", "admin123")
    _create_plan(client, "入口计划", [_row([_valve_device(valve_id)])])
    _publish(client)

    text = client.get("/plan/1").data.decode("utf-8")
    assert "创建维护记录以完成" in text
    assert f"/maintenance/new?plan_item_id=" in text


def test_detail_offers_instrument_confirm_entry(client, init_database):
    db = init_database
    meter_id = _create_approved_instrument(db)
    _login(client, "admin", "admin123")
    _create_plan(client, "仪表计划", [
        _row([{"type": "flow_meter", "id": meter_id, "tag": "FM-001", "name": "测试流量计"}],
             category="instrument"),
    ])
    _publish(client, recipients="2")
    _logout(client)
    _login(client, "user1", "user123")
    text = client.get("/plan/1").data.decode("utf-8")
    assert "确认完成" in text


def test_maintenance_links_and_completes_plan_item(client, init_database):
    db = init_database
    valve_id = _create_approved_valve(db)
    _login(client, "admin", "admin123")
    _create_plan(client, "Link Plan", [_row([_valve_device(valve_id)])])
    _publish(client)

    _logout(client)
    _login(client, "user1", "user123")
    resp = _create_maintenance(client, valve_id, plan_item_id="1")
    assert resp.status_code == 200
    # 保存后应明确反馈计划进度（用户反馈：发布后没有进度追踪）
    assert "本计划进度 1/1" in resp.data.decode("utf-8")

    from app.models import MaintenanceRecord, MaintenancePlanItem
    record = MaintenanceRecord.query.first()
    item = MaintenancePlanItem.query.get(1)
    assert record is not None
    assert item.maintenance_id == record.id
    assert item.status == "completed"


def test_confirm_item_completes_instrument_with_timestamp(client, init_database):
    db = init_database
    meter_id = _create_approved_instrument(db)
    _login(client, "admin", "admin123")
    _create_plan(client, "Non-Valve Plan", [
        _row([{"type": "flow_meter", "id": meter_id, "tag": "FM-001", "name": "测试流量计"}],
             category="instrument"),
    ])
    _publish(client, recipients="2")

    _logout(client)
    _login(client, "user1", "user123")
    resp = client.post("/plan/1/confirm-item/1", follow_redirects=True)
    assert resp.status_code == 200
    assert "完成时间" in resp.data.decode("utf-8")

    from app.models import MaintenancePlanItem
    item = MaintenancePlanItem.query.get(1)
    assert item.status == "completed"
    assert item.maintenance_id is None
    assert item.completed_at is not None
    assert item.completed_by == 2


def test_confirm_item_rejected_for_valve(client, init_database):
    db = init_database
    valve_id = _create_approved_valve(db, tag="FV-003")
    _login(client, "admin", "admin123")
    _create_plan(client, "Valve Plan", [_row([_valve_device(valve_id, "FV-003")])])
    _publish(client, recipients="2")

    _logout(client)
    _login(client, "user1", "user123")
    resp = client.post("/plan/1/confirm-item/1", follow_redirects=True)
    assert resp.status_code == 200
    assert "阀门类任务需通过创建维护记录完成" in resp.data.decode("utf-8")

    from app.models import MaintenancePlanItem
    assert MaintenancePlanItem.query.get(1).status == "pending"


def test_confirm_item_requires_recipient(client, init_database):
    """未指派给当前用户的计划不允许确认，避免越权操作"""
    db = init_database
    meter_id = _create_approved_instrument(db)
    _login(client, "admin", "admin123")
    _create_plan(client, "指派计划", [
        _row([{"type": "flow_meter", "id": meter_id, "tag": "FM-001", "name": "测试流量计"}],
             category="instrument"),
    ])
    # 只指派给另一个新建员工，user1 不在接收人之列
    from app.models import User, db as _db
    other = User(username="user2", role="employee", real_name="李四")
    other.set_password("user123")
    _db.session.add(other)
    _db.session.commit()
    client.post("/plan/1/publish", data={"recipient_ids": [str(other.id)]}, follow_redirects=True)

    _logout(client)
    _login(client, "user1", "user123")
    resp = client.post("/plan/1/confirm-item/1", follow_redirects=True)
    assert "无权操作此计划" in resp.data.decode("utf-8")

    from app.models import MaintenancePlanItem
    assert MaintenancePlanItem.query.get(1).status == "pending"


# ========== 我的检修任务 / 预警 ==========

def test_my_tasks_lists_and_filters_by_recipient(client, init_database):
    db = init_database
    valve_id = _create_approved_valve(db)
    _login(client, "admin", "admin123")
    _create_plan(client, "预警计划", [_row([_valve_device(valve_id)], end="2026-12-31")])
    _publish(client, recipients="2")

    _logout(client)
    _login(client, "user1", "user123")
    resp = client.get("/my/plan-tasks")
    assert resp.status_code == 200
    text = resp.data.decode("utf-8")
    assert "FV-001" in text
    assert "创建维护记录以完成" in text


def test_my_tasks_empty_for_non_recipient(client, init_database):
    db = init_database
    valve_id = _create_approved_valve(db)
    _login(client, "admin", "admin123")
    _create_plan(client, "他人的计划", [_row([_valve_device(valve_id)])])

    from app.models import User, db as _db
    other = User(username="user2", role="employee", real_name="李四")
    other.set_password("user123")
    _db.session.add(other)
    _db.session.commit()
    client.post("/plan/1/publish", data={"recipient_ids": [str(other.id)]}, follow_redirects=True)

    _logout(client)
    _login(client, "user1", "user123")
    text = client.get("/my/plan-tasks").data.decode("utf-8")
    assert "当前没有待完成的检修任务" in text
    assert "FV-001" not in text


def test_my_tasks_scope_overdue_filter(client, init_database):
    db = init_database
    valve_id = _create_approved_valve(db)
    _login(client, "admin", "admin123")
    # 已过期的计划（相对当前日期）
    _create_plan(client, "逾期计划", [_row([_valve_device(valve_id)], start="2020-01-01", end="2020-01-31")])
    _publish(client, recipients="2")

    _logout(client)
    _login(client, "user1", "user123")
    text = client.get("/my/plan-tasks?scope=overdue").data.decode("utf-8")
    assert "FV-001" in text
    assert "已逾期" in text


# ========== 编辑：增量更新不破坏关联 ==========

def test_edit_plan_updates_rows(client, init_database):
    _login(client, "admin", "admin123")
    _create_plan(client, "Edit Test")
    rows = [_row([_valve_device(3, "PV-003", "新阀")], end="2026-11-11",
                 maintenance_project="更换膜片")]
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


def test_edit_preserves_maintenance_link(client, init_database):
    """编辑草稿不得重建计划项：已关联的维护记录必须保留（原全删重建会错位）"""
    db = init_database
    valve_id = _create_approved_valve(db)
    _login(client, "admin", "admin123")
    _create_plan(client, "保留关联", [_row([_valve_device(valve_id)])])
    _publish(client)

    _logout(client)
    _login(client, "user1", "user123")
    _create_maintenance(client, valve_id, plan_item_id="1")

    from app.models import MaintenancePlanItem, MaintenancePlanGroup
    item = MaintenancePlanItem.query.get(1)
    record_id = item.maintenance_id
    group_id = item.group_id
    assert record_id is not None

    # 编辑该计划（需先退回草稿以允许编辑）
    from app.models import MaintenancePlan, db as _db
    plan = MaintenancePlan.query.get(1)
    plan.status = "draft"
    _db.session.commit()

    rows = [_row([_valve_device(valve_id)], end="2026-11-11", group_id=group_id)]
    client.post("/plan/1/edit", data={
        "title": "保留关联", "description": "desc", "rows_json": json.dumps(rows),
    }, follow_redirects=True)

    kept = MaintenancePlanItem.query.get(1)
    assert kept is not None, "计划项不应被删除重建"
    assert kept.maintenance_id == record_id, "维护记录关联必须保留"
    assert kept.status == "completed"
    assert MaintenancePlanGroup.query.count() == 1


def test_edit_keeps_group_linked_to_maintenance_when_removed(client, init_database):
    """本次提交未包含的任务组若已关联维护记录，应保留并提示，而不是连同记录一起删掉"""
    db = init_database
    valve_id = _create_approved_valve(db)
    _login(client, "admin", "admin123")
    _create_plan(client, "保留组", [_row([_valve_device(valve_id)])])
    _publish(client)

    _logout(client)
    _login(client, "user1", "user123")
    _create_maintenance(client, valve_id, plan_item_id="1")

    from app.models import MaintenancePlan, MaintenancePlanItem, MaintenancePlanGroup, db as _db
    linked = MaintenancePlanItem.query.get(1)
    assert linked.maintenance_id is not None
    original_group_id = linked.group_id
    MaintenancePlan.query.get(1).status = "draft"
    _db.session.commit()

    # 编辑计划需领导/管理员权限，切回管理员再提交
    _logout(client)
    _login(client, "admin", "admin123")

    # 提交一个不含原组的行——原组已关联维护记录，应保留并提示
    rows = [_row([_valve_device(valve_id, "FV-999", "另一个阀")], end="2026-11-11")]
    resp = client.post("/plan/1/edit", data={
        "title": "保留组", "description": "desc", "rows_json": json.dumps(rows),
    }, follow_redirects=True)
    assert "保留未删除" in resp.data.decode("utf-8")
    assert MaintenancePlanGroup.query.get(original_group_id) is not None
    assert MaintenancePlanItem.query.get(1).maintenance_id is not None


def test_edit_form_prefills_existing_rows(client, init_database):
    _login(client, "admin", "admin123")
    rows = [_row([_valve_device()], start="2026-05-01", end="2026-12-31")]
    _create_plan(client, "Prefill Test", rows)
    resp = client.get("/plan/1/edit")
    assert resp.status_code == 200
    text = resp.data.decode("utf-8")
    assert "initRows" in text
    assert '"2026-05-01"' in text
    assert '"2026-12-31"' in text
    assert '\\u9600\\u4f53\\u68c0\\u4fee' in text  # 阀体检修
    assert '\\u5f20\\u4f1f' in text  # 张伟
    assert '\\u674e\\u5f3a' in text  # 李强


# ========== 发布 / 标记完成 / 归档通知 ==========

def test_publish_requires_recipients(client, init_database):
    """未选择通知对象时不得发布，避免"以为取消了其实已发布" """
    _login(client, "admin", "admin123")
    _create_plan(client, "Test Plan")
    resp = client.post("/plan/1/publish", data={}, follow_redirects=True)
    assert "请至少选择一位通知对象" in resp.data.decode("utf-8")

    from app.models import MaintenancePlan
    assert MaintenancePlan.query.get(1).status == "draft"


def test_publish_and_notify(client, init_database):
    _login(client, "admin", "admin123")
    _create_plan(client, "Test Plan")
    resp = _publish(client)
    assert resp.status_code == 200

    from app.models import MaintenancePlan, Notification
    assert MaintenancePlan.query.get(1).status == "published"
    assert Notification.query.filter_by(type="plan_published").count() == 1


def test_archive_notification_reports_real_progress(client, init_database):
    """归档通知里的完成数必须是真实统计，不能是永远为 0 的冗余字段"""
    db = init_database
    meter_id = _create_approved_instrument(db)
    _login(client, "admin", "admin123")
    _create_plan(client, "Archive Test", [
        _row([{"type": "flow_meter", "id": meter_id, "tag": "FM-001", "name": "测试流量计"}],
             category="instrument"),
    ])
    _publish(client, recipients="2")

    _logout(client)
    _login(client, "user1", "user123")
    client.post("/plan/1/confirm-item/1", follow_redirects=True)

    _logout(client)
    _login(client, "admin", "admin123")
    resp = client.post("/plan/1/archive", follow_redirects=True)
    assert resp.status_code == 200

    from app.models import Notification
    note = Notification.query.filter_by(type="plan_archived").first()
    assert note is not None
    assert "完成 1/1 项" in note.content


def test_archive_reports_unfinished_count(client, init_database):
    db = init_database
    valve_id = _create_approved_valve(db)
    _login(client, "admin", "admin123")
    _create_plan(client, "未完成归档", [_row([_valve_device(valve_id)])])
    _publish(client)

    resp = client.post("/plan/1/archive", follow_redirects=True)
    assert "仍有 1 项未完成" in resp.data.decode("utf-8")


# ========== 逾期判定 ==========

def test_completed_maintenance_after_deadline_shows_overdue(client, init_database):
    db = init_database
    valve_id = _create_approved_valve(db)
    _login(client, "admin", "admin123")
    _create_plan(client, "Overdue Plan", [_row([_valve_device(valve_id)], start="2026-01-01", end="2026-07-31")])
    _publish(client)

    _logout(client)
    _login(client, "user1", "user123")
    _create_maintenance(client, valve_id, plan_item_id="1")

    from app.models import MaintenancePlanItem
    item = MaintenancePlanItem.query.get(1)
    assert item.status == "completed"
    assert item.maintenance_record.检修时间.date() > item.planned_date_end


def test_instrument_overdue_keeps_status_and_flag(client, init_database):
    """已完成且逾期时应同时显示状态与逾期角标，而不是互相覆盖"""
    db = init_database
    meter_id = _create_approved_instrument(db)
    _login(client, "admin", "admin123")
    _create_plan(client, "Overdue Instrument", [
        _row([{"type": "flow_meter", "id": meter_id, "tag": "FM-001", "name": "测试流量计"}],
             category="instrument", start="2020-01-01", end="2020-01-31")
    ])
    _publish(client, recipients="2")

    _logout(client)
    _login(client, "user1", "user123")
    client.post("/plan/1/confirm-item/1", follow_redirects=True)

    _logout(client)
    _login(client, "admin", "admin123")
    text = client.get("/plan/1").data.decode("utf-8")
    assert "已完成" in text
    assert "逾期" in text


# ========== 维护记录设备范围 ==========

def test_maintenance_create_lists_instruments(client, init_database):
    """维护记录必须能选到非阀门仪表，否则计划里的仪表项无法通过维护记录完成"""
    db = init_database
    _create_approved_instrument(db, tag="FM-777")
    _login(client, "user1", "user123")
    resp = client.get("/maintenance/new")
    assert resp.status_code == 200
    text = resp.data.decode("utf-8")
    assert "FM-777" in text


def test_maintenance_create_preselects_plan_item(client, init_database):
    db = init_database
    valve_id = _create_approved_valve(db)
    _login(client, "admin", "admin123")
    _create_plan(client, "直达计划", [_row([_valve_device(valve_id)])])
    _publish(client, recipients="2")

    _logout(client)
    _login(client, "user1", "user123")
    resp = client.get("/maintenance/new?plan_item_id=1")
    assert resp.status_code == 200
    text = resp.data.decode("utf-8")
    assert "preselectedItem" in text
    # tojson 会把中文转义成 \uXXXX，这里断言计划标题的转义形式
    assert json.dumps("直达计划", ensure_ascii=True)[1:-1] in text


def test_plan_list_shows_progress_for_manager(client, init_database):
    db = init_database
    valve_id = _create_approved_valve(db)
    _login(client, "admin", "admin123")
    _create_plan(client, "列表计划", [_row([_valve_device(valve_id)])])
    text = client.get("/plans").data.decode("utf-8")
    assert "列表计划" in text
    assert "草稿待发布" in text
