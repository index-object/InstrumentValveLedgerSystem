# coding=utf-8
"""生成演示数据，用于在浏览器/公网隧道中查看检修计划模块的重构效果。

幂等：所有记录按位号/标题判重，重复执行不会产生重复数据，也不会修改已有计划。

包含：
* 常减压 / 催化裂化 / 重整 三个装置，共 10 台已审批设备（阀门 5、其他仪表 5）
* 一份「进行中」的年度检修计划：阀门 3 项 + 其他仪表 3 项，已指派给化工班、动力班
* 一份「草稿」计划，用于展示未发布状态与编辑入口
* 部分仪表任务预先完成，便于立刻看到进度条与完成率

用法：
    uv run python scripts/seed_demo_plan.py
"""
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import (
    MaintenancePlan, MaintenancePlanGroup, MaintenancePlanItem, Notification,
    User,
)
from app.devices.types.control_valve import ControlValve
from app.devices.types.onoff_valve import OnOffValve
from app.devices.types.electric_valve import ElectricValve
from app.devices.types.flow_meter import FlowMeter
from app.devices.types.pressure_transmitter import PressureTransmitter
from app.devices.types.local_pressure_gauge import LocalPressureGauge
from app.devices.types.temperature import Temperature
from app.devices.types.level_transmitter import LevelTransmitter

TODAY = date.today()

# (模型, 装置, 位号, 名称, 状态)
DEVICES = [
    (ControlValve, "常减压", "FV-10101", "常压塔进料调节阀", "approved"),
    (ControlValve, "常减压", "FV-10203", "减压塔侧线调节阀", "approved"),
    (ControlValve, "催化裂化", "FV-20101", "反应器进料调节阀", "approved"),
    (OnOffValve, "常减压", "XV-10105", "常压塔底紧急切断阀", "approved"),
    (ElectricValve, "催化裂化", "EV-20201", "烟道挡板电动阀", "approved"),
    (PressureTransmitter, "常减压", "PT-10101", "常压塔顶压力变送器", "approved"),
    (PressureTransmitter, "催化裂化", "PT-20101", "反应器压力变送器", "approved"),
    (FlowMeter, "常减压", "FT-10101", "常压塔进料流量计", "approved"),
    (Temperature, "重整", "TT-30101", "重整反应器温度变送器", "approved"),
    (LevelTransmitter, "重整", "LT-30101", "重整塔液位变送器", "approved"),
    (LocalPressureGauge, "常减压", "PG-10101", "常压塔顶就地压力表", "approved"),
]


def seed_devices():
    created = 0
    for model, unit, tag, name, status in DEVICES:
        field = "名称" if hasattr(model, "名称") else "设备名称"
        exists = model.query.filter(model.位号 == tag).first()
        if exists:
            continue
        obj = model(装置名称=unit, 位号=tag, status=status, created_by=1)
        setattr(obj, field, name)
        if hasattr(obj, "安装位置及用途"):
            obj.安装位置及用途 = f"{unit}装置现场"
        db.session.add(obj)
        created += 1
    db.session.commit()
    return created


def _device(model, tag):
    return model.query.filter(model.位号 == tag).first()


def seed_plans():
    admin = User.query.filter_by(username="admin").first()
    employees = User.query.filter_by(role="employee", status="active").all()
    if not admin:
        raise RuntimeError("缺少 admin 用户，请先执行 init_db.py")

    if MaintenancePlan.query.filter_by(title="2026年度仪表阀门检修计划").first():
        return "已存在，跳过"

    # ── 计划一：进行中，阀门 + 其他仪表混合 ──
    plan = MaintenancePlan(
        title="2026年度仪表阀门检修计划",
        description="覆盖常减压、催化裂化、重整三套装置的仪表阀门年度检修，"
                    "阀门需创建维护记录完成，其他仪表确认完成即可。",
        status="published",
        created_by=admin.id,
        published_by=admin.id,
    )
    db.session.add(plan)
    db.session.flush()
    plan.recipients = employees

    # 阀门任务组：区间较紧，含一项已逾期
    valve_group = MaintenancePlanGroup(
        plan_id=plan.id, category="valve",
        planned_date_start=TODAY - timedelta(days=20),
        planned_date_end=TODAY + timedelta(days=10),
        maintenance_project="阀体检修与填料更换",
        maintenance_scheme="解体检查阀芯阀座，更换填料与垫片，回装后做气密试验",
        safety_measures="办理检修作业票；隔离上下游并泄压；佩戴防护面罩；作业区设警戒",
        project_leader="张伟",
        maintenance_leader="李强",
        quality_acceptance="气密试验合格，动作行程符合要求",
        remark="需与工艺确认切出时间",
        sort_order=1,
    )
    db.session.add(valve_group)
    db.session.flush()

    # 仪表任务组：区间宽松
    inst_group = MaintenancePlanGroup(
        plan_id=plan.id, category="instrument",
        planned_date_start=TODAY - timedelta(days=5),
        planned_date_end=TODAY + timedelta(days=25),
        maintenance_project="仪表校验",
        maintenance_scheme="按 JJG 规程送检或现场比对校验，出具校验记录",
        safety_measures="办理仪表作业票；确认联锁已摘除；防止误碰引压管线",
        project_leader="王五",
        maintenance_leader="赵六",
        quality_acceptance="校验误差在允许范围内",
        remark="",
        sort_order=2,
    )
    db.session.add(inst_group)
    db.session.flush()

    valve_items = [
        (ControlValve, "FV-10101", "pending", None),
        (ControlValve, "FV-10203", "pending", None),
        (OnOffValve, "XV-10105", "pending", None),
    ]
    for model, tag, status, completed_at in valve_items:
        dev = _device(model, tag)
        if not dev:
            continue
        db.session.add(MaintenancePlanItem(
            plan_id=plan.id, group_id=valve_group.id,
            device_type=_type_code(model),
            device_id=dev.id, tag=dev.位号,
            device_name=getattr(dev, "名称", None) or getattr(dev, "设备名称", "") or "",
            planned_date_start=valve_group.planned_date_start,
            planned_date_end=valve_group.planned_date_end,
            status=status, completed_at=completed_at,
        ))

    # 仪表任务：一项已完成、一项逾期未完成、一项正常待办
    inst_items = [
        (PressureTransmitter, "PT-10101", "completed"),
        (FlowMeter, "FT-10101", "pending"),
        (Temperature, "TT-30101", "pending"),
    ]
    for model, tag, status in inst_items:
        dev = _device(model, tag)
        if not dev:
            continue
        completed_at = None
        if status == "completed":
            plan_total_span = inst_group.planned_date_end - inst_group.planned_date_start
            completed_at = _as_datetime(inst_group.planned_date_start + plan_total_span / 3)
        db.session.add(MaintenancePlanItem(
            plan_id=plan.id, group_id=inst_group.id,
            device_type=_type_code(model),
            device_id=dev.id, tag=dev.位号,
            device_name=getattr(dev, "设备名称", "") or "",
            planned_date_start=inst_group.planned_date_start,
            planned_date_end=inst_group.planned_date_end,
            status=status, completed_at=completed_at,
            completed_by=employees[0].id if status == "completed" and employees else None,
        ))

    # ── 计划二：逾期示例，用于展示预警页的"已逾期" ──
    overdue_plan = MaintenancePlan(
        title="2026年第二季度仪表校验（已逾期示例）",
        description="该计划任务已过计划结束日期，用于演示检修预警页的逾期提示。",
        status="published",
        created_by=admin.id,
        published_by=admin.id,
    )
    db.session.add(overdue_plan)
    db.session.flush()
    overdue_plan.recipients = employees

    overdue_group = MaintenancePlanGroup(
        plan_id=overdue_plan.id, category="instrument",
        planned_date_start=TODAY - timedelta(days=40),
        planned_date_end=TODAY - timedelta(days=12),
        maintenance_project="压力表校验",
        maintenance_scheme="现场比对校验",
        safety_measures="办理作业票；确认无联锁影响",
        project_leader="孙七",
        maintenance_leader="周八",
        quality_acceptance="误差在允许范围内",
        remark="已超期，需尽快安排",
        sort_order=1,
    )
    db.session.add(overdue_group)
    db.session.flush()

    for model, tag in [(LocalPressureGauge, "PG-10101"), (PressureTransmitter, "PT-20101")]:
        dev = _device(model, tag)
        if not dev:
            continue
        db.session.add(MaintenancePlanItem(
            plan_id=overdue_plan.id, group_id=overdue_group.id,
            device_type=_type_code(model),
            device_id=dev.id, tag=dev.位号,
            device_name=getattr(dev, "设备名称", "") or "",
            planned_date_start=overdue_group.planned_date_start,
            planned_date_end=overdue_group.planned_date_end,
            status="pending",
        ))

    # ── 计划三：草稿，用于展示草稿状态 ──
    draft = MaintenancePlan(
        title="2026年第三季度预防性维护（草稿）",
        description="尚未发布的草稿计划，用于演示草稿状态与编辑入口。",
        status="draft",
        created_by=admin.id,
    )
    db.session.add(draft)
    db.session.flush()

    draft_group = MaintenancePlanGroup(
        plan_id=draft.id, category="valve",
        planned_date_start=TODAY + timedelta(days=30),
        planned_date_end=TODAY + timedelta(days=60),
        maintenance_project="电动阀行程检查",
        maintenance_scheme="检查执行机构行程与限位，润滑传动部件",
        safety_measures="办理作业票；确认阀门可切出",
        project_leader="张伟",
        maintenance_leader="李强",
        quality_acceptance="行程与限位动作正常",
        remark="待工艺确认窗口期",
        sort_order=1,
    )
    db.session.add(draft_group)
    db.session.flush()

    for model, tag in [(ElectricValve, "EV-20201"), (LevelTransmitter, "LT-30101")]:
        dev = _device(model, tag)
        if not dev:
            continue
        category = "valve" if model is ElectricValve else "instrument"
        group = draft_group
        if category == "instrument":
            # 草稿计划同样按类别分开成组
            group = MaintenancePlanGroup(
                plan_id=draft.id, category="instrument",
                planned_date_start=draft_group.planned_date_start,
                planned_date_end=draft_group.planned_date_end,
                maintenance_project="液位变送器校验",
                maintenance_scheme="现场比对校验",
                safety_measures="办理作业票",
                project_leader="王五",
                maintenance_leader="赵六",
                quality_acceptance="误差在允许范围内",
                remark="",
                sort_order=2,
            )
            db.session.add(group)
            db.session.flush()
        db.session.add(MaintenancePlanItem(
            plan_id=draft.id, group_id=group.id,
            device_type=_type_code(model),
            device_id=dev.id, tag=dev.位号,
            device_name=getattr(dev, "设备名称", getattr(dev, "名称", "")) or "",
            planned_date_start=group.planned_date_start,
            planned_date_end=group.planned_date_end,
            status="pending",
        ))

    for p in (plan, overdue_plan, draft):
        p.total_items = MaintenancePlanItem.query.filter_by(plan_id=p.id).count()

    db.session.commit()

    # 发布通知，让员工端角标与预警页有内容
    for emp in employees:
        db.session.add(Notification(
            user_id=emp.id, type="plan_published",
            title=f"新检修计划发布：{plan.title}",
            content=f"计划共 {plan.total_items} 项任务，请在「检修预警」中查看待办。",
            ref_type="plan", ref_id=plan.id,
        ))
        db.session.add(Notification(
            user_id=emp.id, type="plan_published",
            title=f"新检修计划发布：{overdue_plan.title}",
            content=f"计划共 {overdue_plan.total_items} 项任务且已超期，请尽快处理。",
            ref_type="plan", ref_id=overdue_plan.id,
        ))
    db.session.commit()
    return "已创建"


_TYPE_CODE_CACHE = {}


def _type_code(model):
    """反查设备模型对应的类型编码"""
    if model in _TYPE_CODE_CACHE:
        return _TYPE_CODE_CACHE[model]
    from app.devices import DeviceTypeRegistry
    for config in DeviceTypeRegistry.all():
        if config.model_class is model:
            _TYPE_CODE_CACHE[model] = config.code
            return config.code
    raise RuntimeError(f"未注册的设备类型：{model}")


def _as_datetime(d):
    from datetime import datetime, time
    if isinstance(d, datetime):
        return d
    return datetime.combine(d, time(10, 0))


def main():
    app = create_app()
    with app.app_context():
        db.create_all()
        created_devices = seed_devices()
        plan_result = seed_plans()
        print(f"演示设备：新增 {created_devices} 台")
        print(f"演示计划：{plan_result}")
        print()
        print("计划概览：")
        for p in MaintenancePlan.query.order_by(MaintenancePlan.id).all():
            total = MaintenancePlanItem.query.filter_by(plan_id=p.id).count()
            done = MaintenancePlanItem.query.filter_by(plan_id=p.id, status="completed").count()
            groups = MaintenancePlanGroup.query.filter_by(plan_id=p.id).count()
            print(f"  [{p.status:9}] {p.title}  任务组 {groups} · {done}/{total} 完成")
        print()
        print("登录账号：")
        print("  管理员 admin / admin123")
        print("  领导   ld001 / ld001")
        print("  员工   化工班 / 111")
        print("  员工   动力班 / 222")
    return 0


if __name__ == "__main__":
    sys.exit(main())
