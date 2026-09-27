# coding=utf-8
"""检修计划模块 UI 重构的端到端流程测试。

对应设计文档 docs/plans/2026-09-19-plans-module-ux-redesign-design.md 的验收标准：
从员工「知道要做什么」到「完成并看到进度推进」的完整闭环。
"""
from __future__ import unicode_literals

import json


def _login(client, username, password):
    return client.post("/login", data={"username": username, "password": password})


def _row(devices, category, start, end, **fields):
    row = {
        "category": category,
        "devices": devices,
        "planned_date_start": start,
        "planned_date_end": end,
        "maintenance_project": fields.get("maintenance_project", "年度检修"),
        "maintenance_scheme": fields.get("maintenance_scheme", "解体检查"),
        "safety_measures": fields.get("safety_measures", "办理作业票"),
        "project_leader": fields.get("project_leader", "张伟"),
        "maintenance_leader": fields.get("maintenance_leader", "李强"),
        "quality_acceptance": fields.get("quality_acceptance", ""),
        "remark": fields.get("remark", ""),
    }
    return row


def _seed_devices(db):
    from app.devices.types.control_valve import ControlValve
    from app.devices.types.flow_meter import FlowMeter

    valve = ControlValve(位号="FV-100", 名称="进料调节阀", 装置名称="常减压", status="approved", created_by=1)
    meter = FlowMeter(位号="FT-200", 设备名称="进料流量计", 装置名称="常减压", status="approved", created_by=1)
    db.session.add_all([valve, meter])
    db.session.commit()
    return valve.id, meter.id


def test_full_flow_manager_publishes_employee_completes(client, init_database):
    """领导建计划+发布 → 员工在预警页看到任务 → 完成仪表任务 → 进度推进且领导可见"""
    db = init_database
    valve_id, meter_id = _seed_devices(db)

    # ---- 领导建计划：阀门行 + 仪表行分开 ----
    _login(client, "admin", "admin123")
    rows = [
        _row([{"type": "control_valve", "id": valve_id, "tag": "FV-100", "name": "进料调节阀"}],
             "valve", "2026-05-01", "2026-05-15", maintenance_project="阀体检修"),
        _row([{"type": "flow_meter", "id": meter_id, "tag": "FT-200", "name": "进料流量计"}],
             "instrument", "2026-06-01", "2026-06-10", maintenance_project="流量计校验"),
    ]
    resp = client.post("/plan/new", data={
        "title": "2026年度大检修", "description": "覆盖常减压装置",
        "rows_json": json.dumps(rows),
    }, follow_redirects=True)
    assert resp.status_code == 200
    text = resp.data.decode("utf-8")
    # 草稿状态明确提示未发布，且两类任务分区展示
    assert "草稿尚未发布" in text
    assert "阀门检修任务" in text
    assert "其他仪表检修任务" in text

    # ---- 发布 ----
    resp = client.post("/plan/1/publish", data={"recipient_ids": ["2"]}, follow_redirects=True)
    assert "计划已发布" in resp.data.decode("utf-8")

    # 详情页应给出两类不同的完成入口
    detail = client.get("/plan/1").data.decode("utf-8")
    assert "创建维护记录以完成" in detail
    # 领导端不应出现仪表任务的"确认完成"按钮，只提示由被指派员工完成
    assert "由被指派的班组员工确认完成" in detail
    assert "确认完成 FT-200" not in detail

    # ---- 员工视角 ----
    client.get("/logout")
    _login(client, "user1", "user123")

    tasks = client.get("/my/plan-tasks").data.decode("utf-8")
    assert "FV-100" in tasks and "FT-200" in tasks
    assert "确认完成" in tasks          # 仪表任务可直接确认
    assert "创建维护记录以完成" in tasks  # 阀门任务直达维护记录

    # 侧边栏角标应反映本人任务数
    assert "检修预警" in tasks

    # ---- 完成仪表任务 ----
    from app.models import MaintenancePlanItem
    meter_item = MaintenancePlanItem.query.filter_by(tag="FT-200").first()
    resp = client.post(f"/plan/1/confirm-item/{meter_item.id}", follow_redirects=True)
    assert "完成时间" in resp.data.decode("utf-8")

    # 完成后再看待办：该仪表项应已消失
    tasks_after = client.get("/my/plan-tasks").data.decode("utf-8")
    assert "FT-200" not in tasks_after
    assert "FV-100" in tasks_after

    # ---- 领导看进度：1/2 完成 ----
    client.get("/logout")
    _login(client, "admin", "admin123")
    detail = client.get("/plan/1").data.decode("utf-8")
    assert "1/2 项已完成" in detail
    assert "50%" in detail

    # 列表页显示进度条
    listing = client.get("/plans").data.decode("utf-8")
    assert "2026年度大检修" in listing
    assert "50%" in listing


def test_nav_badge_is_scoped_to_recipient(client, init_database):
    """角标只统计指派给本人的到期/逾期任务，不显示全厂数字"""
    db = init_database
    valve_id, _ = _seed_devices(db)

    from app.models import User, db as _db
    other = User(username="user2", role="employee", real_name="李四")
    other.set_password("user123")
    _db.session.add(other)
    _db.session.commit()

    _login(client, "admin", "admin123")
    rows = [_row([{"type": "control_valve", "id": valve_id, "tag": "FV-100", "name": "进料调节阀"}],
                 "valve", "2020-01-01", "2020-01-31")]
    client.post("/plan/new", data={
        "title": "逾期计划", "description": "", "rows_json": json.dumps(rows),
    }, follow_redirects=True)
    # 只指派给 user2
    client.post("/plan/1/publish", data={"recipient_ids": [str(other.id)]}, follow_redirects=True)

    # user1 不是接收人，角标应为 0（不显示）
    client.get("/logout")
    _login(client, "user1", "user123")
    text = client.get("/plans").data.decode("utf-8")
    assert "您有" not in text or "0 项" in text

    # user2 是接收人且任务已逾期，角标应出现
    client.get("/logout")
    _login(client, "user2", "user123")
    text = client.get("/plans").data.decode("utf-8")
    assert "已逾期" in text


# ========== 查询数量：防止 N+1 退化 ==========

def _count_queries(db, fn):
    """统计 fn() 期间执行的 SQL 语句数"""
    from sqlalchemy import event

    statements = []

    def recorder(conn, cursor, statement, params, context, executemany):
        statements.append(statement)

    event.listen(db.engine, "before_cursor_execute", recorder)
    try:
        result = fn()
    finally:
        event.remove(db.engine, "before_cursor_execute", recorder)
    return len(statements), result


def _seed_plans(db, creator, recipient, count, items_per_plan=5, category="instrument"):
    from datetime import date as _date
    from app.models import (
        MaintenancePlan, MaintenancePlanGroup, MaintenancePlanItem, PlanRecipient,
    )

    for i in range(count):
        plan = MaintenancePlan(title=f"压测计划{i}", status="published",
                               created_by=creator.id, total_items=items_per_plan)
        db.session.add(plan)
        db.session.flush()
        plan.recipients.append(recipient)
        group = MaintenancePlanGroup(
            plan_id=plan.id, category=category,
            planned_date_start=_date(2026, 1, 1), planned_date_end=_date(2026, 12, 31),
        )
        db.session.add(group)
        db.session.flush()
        for j in range(items_per_plan):
            db.session.add(MaintenancePlanItem(
                plan_id=plan.id, group_id=group.id,
                device_type="flow_meter" if category == "instrument" else "control_valve",
                device_id=j, tag=f"T-{i}-{j}",
                planned_date_start=group.planned_date_start,
                planned_date_end=group.planned_date_end,
            ))
    db.session.commit()


def test_plan_list_query_count_is_constant(client, init_database):
    """计划列表的查询数不得随计划数增长（原实现每个计划各查一次明细与创建人）"""
    db = init_database
    from app.models import MaintenancePlan, MaintenancePlanGroup, MaintenancePlanItem

    _login(client, "admin", "admin123")

    def reset():
        MaintenancePlanItem.query.delete()
        MaintenancePlanGroup.query.delete()
        MaintenancePlan.query.delete()
        db.session.commit()

    def measure(count):
        reset()
        _seed_plans(db, creator=_user(db, "admin"), recipient=_user(db, "user1"), count=count)
        return _count_queries(db, lambda: client.get("/plans"))[0]

    few = measure(5)
    many = measure(30)
    assert many - few < 10, f"查询数随计划数增长，疑似 N+1：5 个计划 {few} 条，30 个计划 {many} 条"


def test_my_tasks_query_count_is_constant(client, init_database):
    """检修预警页的查询数不得随待办项数增长"""
    db = init_database
    from app.models import MaintenancePlan, MaintenancePlanGroup, MaintenancePlanItem, PlanRecipient

    _login(client, "user1", "user123")

    def reset():
        MaintenancePlanItem.query.delete()
        MaintenancePlanGroup.query.delete()
        PlanRecipient.query.delete()
        MaintenancePlan.query.delete()
        db.session.commit()

    def measure(count):
        reset()
        _seed_plans(db, creator=_user(db, "admin"), recipient=_user(db, "user1"), count=count)
        return _count_queries(db, lambda: client.get("/my/plan-tasks"))[0]

    few = measure(5)
    many = measure(30)
    assert many - few < 10, f"查询数随待办项增长，疑似 N+1：5 个计划 {few} 条，30 个计划 {many} 条"


def _user(db, username):
    from app.models import User
    return User.query.filter_by(username=username).first()
