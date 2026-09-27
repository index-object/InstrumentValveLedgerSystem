from flask import (
    Blueprint, render_template, redirect, url_for, request, flash,
)
from flask_login import login_required, current_user
from app.models import (
    db, MaintenancePlan, MaintenancePlanGroup, MaintenancePlanItem, Notification, User,
)
from app.devices.valve_helper import is_valve_type
from app.devices import DeviceTypeRegistry
from datetime import datetime, date, timedelta

plans_bp = Blueprint("plans", __name__, url_prefix="")

# 计划状态机的显示名：状态值保持不变，仅统一中文文案
PLAN_STATUS_LABELS = {
    "draft": "草稿",
    "published": "进行中",
    "archived": "已完成",
}
PLAN_STATUS_ICONS = {
    "draft": "bi-pencil",
    "published": "bi-play-circle",
    "archived": "bi-check-circle-fill",
}

# 任务类别
CATEGORY_VALVE = "valve"
CATEGORY_INSTRUMENT = "instrument"
CATEGORY_LABELS = {
    CATEGORY_VALVE: "阀门",
    CATEGORY_INSTRUMENT: "其他仪表",
}


def plan_status_label(status):
    return PLAN_STATUS_LABELS.get(status, status)


def plan_status_icon(status):
    return PLAN_STATUS_ICONS.get(status, "bi-circle")


def category_of(device_type):
    """设备类型归属的计划任务类别：阀门 / 其他仪表"""
    return CATEGORY_VALVE if is_valve_type(device_type) else CATEGORY_INSTRUMENT


def category_label(category):
    return CATEGORY_LABELS.get(category, category)


def _approved_devices():
    """所有已审批的仪表（阀门 + 其他仪表），供计划明细选择位号。"""
    approved_devices = []
    for config in DeviceTypeRegistry.all():
        model = config.model_class
        if not model or not hasattr(model, '位号'):
            continue
        name_field = '名称' if is_valve_type(config.code) else '设备名称'
        for v in model.query.filter(model.status == "approved").order_by(model.位号).all():
            approved_devices.append({
                "id": v.id,
                "type": config.code,
                "tag": v.位号,
                "name": getattr(v, name_field, "") or "",
                "unit": v.装置名称 or "",
                "category": category_of(config.code),
            })
    return approved_devices


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_rows(rows_json):
    """解析表单提交的行数据。

    每行含 category（valve/instrument）、devices、计划起止日期与检修参数。
    返回 (rows, errors)。
    """
    import json
    if not rows_json:
        return [], []
    try:
        rows = json.loads(rows_json)
    except (ValueError, TypeError):
        return [], ["计划明细数据格式不正确，请重新填写"]

    parsed, errors = [], []
    for idx, row in enumerate(rows, start=1):
        devices = row.get("devices") or []
        if not devices:
            continue

        category = row.get("category") or CATEGORY_VALVE
        if category not in CATEGORY_LABELS:
            errors.append(f"第 {idx} 行的任务类别不正确")
            continue

        date_start = _parse_date(row.get("planned_date_start"))
        date_end = _parse_date(row.get("planned_date_end"))
        if not date_start or not date_end:
            errors.append(f"第 {idx} 行未填写完整的计划开始/结束日期")
            continue
        if date_end < date_start:
            errors.append(f"第 {idx} 行的计划结束日期早于开始日期")
            continue

        normalized = []
        for d in devices:
            dtype = d.get("type")
            # 类别与设备类型必须一致：阀门行只放阀门，仪表行只放仪表
            if category_of(dtype) != category:
                errors.append(
                    f"第 {idx} 行的「{d.get('tag', '')}」应属于"
                    f"「{category_label(category_of(dtype))}」明细，请分开放置"
                )
                continue
            normalized.append({
                "type": dtype,
                "id": int(d.get("id")),
                "tag": d.get("tag", ""),
                "name": d.get("name", ""),
            })
        if not normalized:
            continue

        parsed.append({
            "category": category,
            "devices": normalized,
            "planned_date_start": date_start,
            "planned_date_end": date_end,
            "maintenance_project": (row.get("maintenance_project") or "").strip(),
            "maintenance_scheme": (row.get("maintenance_scheme") or "").strip(),
            "safety_measures": (row.get("safety_measures") or "").strip(),
            "project_leader": (row.get("project_leader") or "").strip(),
            "maintenance_leader": (row.get("maintenance_leader") or "").strip(),
            "quality_acceptance": (row.get("quality_acceptance") or "").strip(),
            "remark": (row.get("remark") or "").strip(),
            "group_id": row.get("group_id"),
        })
    return parsed, errors


def _apply_group_fields(group, row):
    group.category = row["category"]
    group.planned_date_start = row["planned_date_start"]
    group.planned_date_end = row["planned_date_end"]
    group.maintenance_project = row["maintenance_project"]
    group.maintenance_scheme = row["maintenance_scheme"]
    group.safety_measures = row["safety_measures"]
    group.project_leader = row["project_leader"]
    group.maintenance_leader = row["maintenance_leader"]
    group.quality_acceptance = row["quality_acceptance"]
    group.remark = row["remark"]


def _group_is_linked(group):
    """任务组内是否已有计划项关联了维护记录（此时不允许整组删除）"""
    return any(item.maintenance_id for item in group.items)


def _save_rows(plan, rows):
    """增量保存计划明细。

    * 行携带 group_id 时更新既有任务组，保留计划项 id 与维护记录关联；
    * 未携带时新建任务组；
    * 未被本次提交引用的任务组删除（已关联维护记录的整组保留并返回提示）。

    返回 (deleted_groups, skipped_groups)。
    """
    existing = {g.id: g for g in plan.groups.all()}
    kept_ids = set()
    # 行内发现、但需等任务组去留判定之后再决定是否删除的孤儿计划项
    pending_orphans = {}

    for order, row in enumerate(rows, start=1):
        group = None
        raw_gid = row.get("group_id")
        if raw_gid:
            try:
                gid = int(raw_gid)
            except (TypeError, ValueError):
                gid = None
            if gid and gid in existing:
                group = existing[gid]
        if group is None:
            group = MaintenancePlanGroup(plan_id=plan.id)
            # 先赋值再 flush：planned_date_start/end 为非空列，
            # 若先 flush 会因字段仍为 NULL 触发 NOT NULL 约束错误。
            _apply_group_fields(group, row)
            db.session.add(group)
            db.session.flush()
        else:
            _apply_group_fields(group, row)

        group.sort_order = order
        kept_ids.add(group.id)

        # 计划项：已存在则原地更新（保留 id/maintenance_id/status），新增则插入
        current = {item.device_type + ":" + str(item.device_id): item for item in group.items}
        incoming_keys = set()
        for dev in row["devices"]:
            key = dev["type"] + ":" + str(dev["id"])
            incoming_keys.add(key)
            item = current.get(key)
            if item is None:
                item = MaintenancePlanItem(plan_id=plan.id, group_id=group.id)
                db.session.add(item)
            item.device_type = dev["type"]
            item.device_id = dev["id"]
            item.tag = dev["tag"]
            item.device_name = dev["name"]
            item.planned_date_start = row["planned_date_start"]
            item.planned_date_end = row["planned_date_end"]
        for key, item in current.items():
            if key not in incoming_keys and not item.maintenance_id:
                pending_orphans.setdefault(group.id, []).append(item)

    # 清理本次提交未引用的任务组。
    # 注意：必须在删除计划项"之前"判断组是否已关联维护记录——若先删项，
    # 组会被清空，_group_is_linked 永远为假，关联记录就会随组一起丢失。
    # 因此行内发现的孤儿计划项统一延后到这里处理。
    deleted, skipped = [], []
    for gid, group in existing.items():
        if gid in kept_ids:
            continue
        if _group_is_linked(group):
            # 组内已有维护记录：整组保留，其计划项也不能删
            skipped.append(group)
            continue
        deleted.append(group)
        db.session.delete(group)
        for item in pending_orphans.pop(gid, []):
            db.session.delete(item)

    # 被保留（skipped）的组，其行内孤儿项不删除；其余未处理项按需清理
    for gid, orphans in pending_orphans.items():
        if gid in kept_ids:
            for item in orphans:
                db.session.delete(item)
    return deleted, skipped


def _recalc_plan_progress(plan):
    """同步计划的总项数与接收人通知口径（完成数一律实时统计，不再落冗余字段）"""
    total = MaintenancePlanItem.query.filter_by(plan_id=plan.id).count()
    plan.total_items = total
    return total


def _is_overdue(item, now):
    """逾期：待办且已过计划结束日期；或已完成但实际完成时间晚于计划结束日期"""
    if item.status == "pending":
        return item.planned_date_end is not None and item.planned_date_end < now
    if item.status == "completed":
        if item.maintenance_record and item.maintenance_record.检修时间 and item.planned_date_end:
            return item.maintenance_record.检修时间.date() > item.planned_date_end
        if item.completed_at and item.planned_date_end:
            return item.completed_at.date() > item.planned_date_end
    return False


def _is_expiring(item, now, days=7):
    """即将到期：待办且计划结束日期在 days 天内"""
    return (
        item.status == "pending"
        and item.planned_date_end is not None
        and now <= item.planned_date_end <= now + timedelta(days=days)
    )


def _days_left(item, now):
    """剩余天数：负数表示已逾期天数"""
    if item.planned_date_end is None:
        return None
    return (item.planned_date_end - now).days


def _load_groups(plan, now=None, include_items=True):
    """加载任务组，按类别分组。仪表组按计划结束日期升序，阀门组按 sort_order。"""
    now = now or date.today()
    groups = MaintenancePlanGroup.query.filter_by(plan_id=plan.id).order_by(
        MaintenancePlanGroup.sort_order, MaintenancePlanGroup.id
    ).all()

    result = {CATEGORY_VALVE: [], CATEGORY_INSTRUMENT: []}
    for group in groups:
        entry = {
            "group": group,
            "category": group.category,
            "category_label": category_label(group.category),
            "planned_date_start": group.planned_date_start,
            "planned_date_end": group.planned_date_end,
            "planned_range": _format_range(group.planned_date_start, group.planned_date_end),
            "maintenance_project": group.maintenance_project or "",
            "maintenance_scheme": group.maintenance_scheme or "",
            "safety_measures": group.safety_measures or "",
            "project_leader": group.project_leader or "",
            "maintenance_leader": group.maintenance_leader or "",
            "quality_acceptance": group.quality_acceptance or "",
            "remark": group.remark or "",
            "devices": [],
        }
        if include_items:
            for item in group.items:
                item._overdue = _is_overdue(item, now)
                item._days_left = _days_left(item, now)
                entry["devices"].append(item)
            entry["completed"] = sum(1 for d in entry["devices"] if d.status == "completed")
            entry["overdue"] = sum(1 for d in entry["devices"] if d._overdue)
            entry["total"] = len(entry["devices"])
        result[group.category].append(entry)
    return result


def _format_range(start, end):
    if start and end:
        if start == end:
            return start.strftime("%Y-%m-%d")
        return f"{start.strftime('%Y-%m-%d')} ~ {end.strftime('%Y-%m-%d')}"
    if end:
        return end.strftime("%Y-%m-%d")
    return "—"


def _plan_progress(plan, now=None):
    """计划的完成情况统计（全量口径）"""
    now = now or date.today()
    items = MaintenancePlanItem.query.filter_by(plan_id=plan.id).all()
    total = len(items)
    completed = sum(1 for i in items if i.status == "completed")
    overdue = sum(1 for i in items if _is_overdue(i, now))
    return {
        "total": total,
        "completed": completed,
        "overdue": overdue,
        "pending": total - completed,
        "percent": round(completed / total * 100) if total else 0,
    }


def _my_task_items(user, now=None):
    """当前用户作为接收人的所有进行中计划下的待办项，按计划结束日期升序。"""
    now = now or date.today()
    items = (
        MaintenancePlanItem.query
        .join(MaintenancePlan, MaintenancePlanItem.plan_id == MaintenancePlan.id)
        .join(MaintenancePlanGroup, MaintenancePlanItem.group_id == MaintenancePlanGroup.id)
        .filter(
            MaintenancePlan.status == "published",
            MaintenancePlanItem.status == "pending",
            MaintenancePlan.recipients.any(id=user.id),
        )
        .order_by(MaintenancePlanItem.planned_date_end, MaintenancePlanItem.id)
        .all()
    )
    for item in items:
        item._overdue = _is_overdue(item, now)
        item._days_left = _days_left(item, now)
        item._group = item.group
    return items


def _task_warning_stats(items, now):
    return {
        "overdue": sum(1 for i in items if i._days_left is not None and i._days_left < 0),
        "within7": sum(1 for i in items if i._days_left is not None and 0 <= i._days_left <= 7),
        "within30": sum(1 for i in items if i._days_left is not None and 0 <= i._days_left <= 30),
        "total": len(items),
    }


@plans_bp.route("/plans")
@login_required
def index():
    query = MaintenancePlan.query
    is_manager = current_user.role in ("leader", "admin")
    if not is_manager:
        query = query.filter(
            MaintenancePlan.status.in_(["published", "archived"]),
            MaintenancePlan.recipients.any(id=current_user.id),
        )
    search = request.args.get("search")
    status_filter = request.args.get("status")
    if search:
        query = query.filter(MaintenancePlan.title.contains(search))
    if status_filter:
        query = query.filter(MaintenancePlan.status == status_filter)
    plans = query.order_by(MaintenancePlan.created_at.desc()).all()

    now = date.today()
    # 一次性取回所有相关计划项，避免按计划逐个查询（N+1）
    plan_ids = [p.id for p in plans]
    all_items = []
    if plan_ids:
        all_items = (
            MaintenancePlanItem.query
            .filter(MaintenancePlanItem.plan_id.in_(plan_ids))
            .all()
        )
    items_by_plan = {}
    for item in all_items:
        items_by_plan.setdefault(item.plan_id, []).append(item)

    my_items = _my_task_items(current_user, now) if not is_manager else []
    my_by_plan = {}
    for item in my_items:
        my_by_plan.setdefault(item.plan_id, []).append(item)

    for p in plans:
        items = items_by_plan.get(p.id, [])
        mine = my_by_plan.get(p.id, [])
        p._total = len(items)
        p._completed = sum(1 for i in items if i.status == "completed")
        p._overdue = sum(1 for i in items if _is_overdue(i, now))
        p._percent = round(p._completed / p._total * 100) if p._total else 0
        p._my_total = len(mine)
        p._my_completed = sum(1 for i in mine if i.status == "completed")
        p._my_percent = round(p._my_completed / p._my_total * 100) if p._my_total else 0

    stats = {
        "total": len(plans),
        "draft": sum(1 for p in plans if p.status == "draft"),
        "published": sum(1 for p in plans if p.status == "published"),
        "archived": sum(1 for p in plans if p.status == "archived"),
    }
    warning = _task_warning_stats(my_items, now) if not is_manager else None
    employees = (
        User.query.filter(User.role == "employee", User.status == "active")
        .order_by(User.real_name).all()
        if is_manager else []
    )
    return render_template(
        "plans/list.html", plans=plans, stats=stats, employees=employees,
        is_manager=is_manager, warning=warning,
        plan_status_label=plan_status_label, plan_status_icon=plan_status_icon,
    )


@plans_bp.route("/my/plan-tasks")
@login_required
def my_tasks():
    """我的检修任务：按紧急度列出当前用户待完成的计划项"""
    now = date.today()
    items = _my_task_items(current_user, now)
    stats = _task_warning_stats(items, now)

    scope = request.args.get("scope") or "all"
    plan_id = request.args.get("plan_id", type=int)

    filtered = items
    if scope == "overdue":
        filtered = [i for i in items if i._days_left is not None and i._days_left < 0]
    elif scope == "7":
        filtered = [i for i in items if i._days_left is not None and i._days_left <= 7]
    elif scope == "30":
        filtered = [i for i in items if i._days_left is not None and i._days_left <= 30]
    if plan_id:
        filtered = [i for i in filtered if i.plan_id == plan_id]

    plan_options = (
        MaintenancePlan.query
        .filter(
            MaintenancePlan.status == "published",
            MaintenancePlan.recipients.any(id=current_user.id),
        )
        .order_by(MaintenancePlan.created_at.desc()).all()
    )
    return render_template(
        "plans/my_tasks.html", items=filtered, stats=stats, scope=scope,
        plan_id=plan_id, plan_options=plan_options, now=now,
        is_valve_type=is_valve_type, category_label=category_label,
    )


@plans_bp.route("/plan/<int:id>")
@login_required
def detail(id):
    plan = MaintenancePlan.query.get_or_404(id)
    if current_user.role == "employee":
        if plan.status not in ("published", "archived") or current_user not in plan.recipients:
            flash("无权查看此计划")
            return redirect(url_for("plans.index"))

    now = date.today()
    groups = _load_groups(plan, now)
    is_manager = current_user.role in ("leader", "admin")
    progress = _plan_progress(plan, now)

    my_items = [] if is_manager else _my_task_items(current_user, now)
    my_items = [i for i in my_items if i.plan_id == plan.id]
    my_progress = {
        "total": len(my_items),
        "completed": 0,
        "overdue": sum(1 for i in my_items if i._overdue),
        "pending": len(my_items),
    }

    employees = (
        User.query.filter(User.role == "employee", User.status == "active")
        .order_by(User.real_name).all()
        if is_manager else []
    )
    return render_template(
        "plans/detail.html", plan=plan, groups=groups, employees=employees,
        progress=progress, my_items=my_items, my_progress=my_progress,
        now=now, is_manager=is_manager, is_valve_type=is_valve_type,
        category_label=category_label, plan_status_label=plan_status_label,
        plan_status_icon=plan_status_icon,
    )


@plans_bp.route("/plan/new", methods=["GET", "POST"])
@login_required
def create():
    if current_user.role not in ("leader", "admin"):
        flash("无权创建检修计划")
        return redirect(url_for("plans.index"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        rows, errors = _parse_rows(request.form.get("rows_json"))
        if not title:
            errors.insert(0, "请输入计划标题")
        if not rows:
            errors.append("请至少添加一行计划明细")

        if errors:
            for msg in errors:
                flash(msg)
            return render_template(
                "plans/form.html", approved_devices=_approved_devices(),
                rows=rows, form_title=title,
                description=request.form.get("description", "").strip(),
            )

        plan = MaintenancePlan(
            title=title,
            description=request.form.get("description", "").strip(),
            created_by=current_user.id,
        )
        db.session.add(plan)
        db.session.flush()
        _save_rows(plan, rows)
        _recalc_plan_progress(plan)
        db.session.commit()
        flash("计划已保存为草稿")
        return redirect(url_for("plans.detail", id=plan.id))

    return render_template("plans/form.html", approved_devices=_approved_devices(), rows=[])


@plans_bp.route("/plan/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit(id):
    plan = MaintenancePlan.query.get_or_404(id)
    if current_user.role not in ("leader", "admin"):
        flash("无权编辑")
        return redirect(url_for("plans.detail", id=id))
    if plan.status != "draft":
        flash("只能编辑草稿状态的计划")
        return redirect(url_for("plans.detail", id=id))

    if request.method == "POST":
        title = request.form.get("title", "").strip() or plan.title
        rows, errors = _parse_rows(request.form.get("rows_json"))
        if not rows:
            errors.append("请至少添加一行计划明细")

        if errors:
            for msg in errors:
                flash(msg)
            return render_template(
                "plans/form.html", plan=plan, approved_devices=_approved_devices(),
                rows=rows, form_title=title,
                description=request.form.get("description", "").strip(),
            )

        plan.title = title
        plan.description = request.form.get("description", "").strip()
        _, skipped = _save_rows(plan, rows)
        _recalc_plan_progress(plan)
        db.session.commit()
        if skipped:
            names = "、".join(g.items[0].tag for g in skipped if g.items)
            flash(f"以下任务组已关联维护记录，保留未删除：{names}")
        flash("计划已更新")
        return redirect(url_for("plans.detail", id=id))

    groups = _load_groups(plan, include_items=False)
    rows = []
    for category in (CATEGORY_VALVE, CATEGORY_INSTRUMENT):
        for entry in groups[category]:
            rows.append({
                "group_id": entry["group"].id,
                "category": entry["category"],
                "planned_date_start": entry["planned_date_start"].strftime("%Y-%m-%d"),
                "planned_date_end": entry["planned_date_end"].strftime("%Y-%m-%d"),
                "maintenance_project": entry["maintenance_project"],
                "maintenance_scheme": entry["maintenance_scheme"],
                "safety_measures": entry["safety_measures"],
                "project_leader": entry["project_leader"],
                "maintenance_leader": entry["maintenance_leader"],
                "quality_acceptance": entry["quality_acceptance"],
                "remark": entry["remark"],
                "devices": [
                    {"type": i.device_type, "id": i.device_id, "tag": i.tag, "name": i.device_name or ""}
                    for i in entry["group"].items
                ],
            })
    return render_template(
        "plans/form.html", plan=plan, approved_devices=_approved_devices(), rows=rows,
        form_title=plan.title, description=plan.description or "",
    )


@plans_bp.route("/plan/<int:id>/publish", methods=["POST"])
@login_required
def publish(id):
    plan = MaintenancePlan.query.get_or_404(id)
    if current_user.role not in ("leader", "admin"):
        flash("无权发布")
        return redirect(url_for("plans.detail", id=id))
    if plan.status != "draft":
        flash("只能发布草稿状态的计划")
        return redirect(url_for("plans.detail", id=id))

    total = _recalc_plan_progress(plan)
    if total == 0:
        flash("请先添加计划明细后再发布")
        return redirect(url_for("plans.detail", id=id))

    recipient_ids = request.form.getlist("recipient_ids")
    if not recipient_ids:
        # 未选择通知对象时明确拒绝，避免"以为取消了其实已发布"
        flash("请至少选择一位通知对象；若确实无人需要执行，请先保留为草稿")
        return redirect(url_for("plans.detail", id=id))

    plan.status = "published"
    plan.published_by = current_user.id
    plan.published_at = datetime.utcnow()

    selected = User.query.filter(User.id.in_(recipient_ids)).all()
    valve_count = MaintenancePlanItem.query.join(
        MaintenancePlanGroup, MaintenancePlanItem.group_id == MaintenancePlanGroup.id
    ).filter(
        MaintenancePlanItem.plan_id == plan.id,
        MaintenancePlanGroup.category == CATEGORY_VALVE,
    ).count()
    instrument_count = total - valve_count
    for user in selected:
        plan.recipients.append(user)
        db.session.add(Notification(
            user_id=user.id,
            type="plan_published",
            title=f"新检修计划发布：{plan.title}",
            content=(
                f"计划共 {total} 项任务（阀门 {valve_count} 项，其他仪表 {instrument_count} 项）。"
                "阀门任务需创建维护记录完成，仪表任务确认完成即可。请在「检修预警」中查看待办。"
            ),
            ref_type="plan",
            ref_id=plan.id,
        ))
    db.session.commit()
    flash(f"计划已发布，已通知 {len(selected)} 位用户")
    return redirect(url_for("plans.detail", id=plan.id))


@plans_bp.route("/plan/<int:id>/archive", methods=["POST"])
@login_required
def archive(id):
    plan = MaintenancePlan.query.get_or_404(id)
    if current_user.role not in ("leader", "admin"):
        flash("无权标记完成")
        return redirect(url_for("plans.detail", id=id))
    if plan.status != "published":
        flash("只能将进行中的计划标记为完成")
        return redirect(url_for("plans.detail", id=id))

    progress = _plan_progress(plan)
    plan.status = "archived"

    for user in plan.recipients:
        db.session.add(Notification(
            user_id=user.id,
            type="plan_archived",
            title=f"检修计划已完成：{plan.title}",
            content=(
                f"计划已结束，完成 {progress['completed']}/{progress['total']} 项"
                + (f"，其中 {progress['overdue']} 项逾期完成" if progress["overdue"] else "")
                + "。"
            ),
            ref_type="plan",
            ref_id=plan.id,
        ))

    db.session.commit()
    if progress["pending"] > 0:
        flash(f"计划已标记完成；仍有 {progress['pending']} 项未完成，已随计划结束")
    else:
        flash("计划已全部完成并结束")
    return redirect(url_for("plans.detail", id=plan.id))


@plans_bp.route("/plan/<int:id>/delete", methods=["POST"])
@login_required
def delete(id):
    plan = MaintenancePlan.query.get_or_404(id)
    if current_user.role not in ("leader", "admin"):
        flash("无权删除")
        return redirect(url_for("plans.detail", id=id))
    if plan.status not in ("draft", "archived"):
        flash("只能删除草稿或已完成的计划")
        return redirect(url_for("plans.detail", id=id))
    db.session.delete(plan)
    db.session.commit()
    flash("计划已删除")
    return redirect(url_for("plans.index"))


@plans_bp.route("/plan/<int:id>/confirm-item/<int:item_id>", methods=["POST"])
@login_required
def confirm_item(id, item_id):
    """确认完成计划项：仅限非阀门仪表（阀门须通过维护记录完成）"""
    item = MaintenancePlanItem.query.get_or_404(item_id)
    plan = MaintenancePlan.query.get_or_404(id)

    if item.plan_id != plan.id:
        flash("计划项与计划不匹配")
        return redirect(url_for("plans.detail", id=id))
    # 仪表任务由被指派的员工本人确认，以便记录真实完成人；管理员不代劳
    if current_user.role != "employee":
        flash("只有被指派的任务执行人可以确认完成")
        return redirect(url_for("plans.detail", id=id))
    if plan.status != "published" or current_user not in plan.recipients:
        flash("无权操作此计划")
        return redirect(url_for("plans.detail", id=id))
    if plan.status != "published":
        flash("计划不在进行中，无法确认完成")
        return redirect(url_for("plans.detail", id=id))
    if item.status != "pending":
        flash("该计划项不是待办状态")
        return redirect(url_for("plans.detail", id=id))
    if is_valve_type(item.device_type):
        flash("阀门类任务需通过创建维护记录完成")
        return redirect(url_for("plans.detail", id=id))

    item.status = "completed"
    item.completed_at = datetime.utcnow()
    item.completed_by = current_user.id
    db.session.commit()

    progress = _plan_progress(plan)
    flash(
        f"{item.tag} 已确认完成，完成时间 {item.completed_at.strftime('%Y-%m-%d')}"
        f"（本计划进度 {progress['completed']}/{progress['total']}）"
    )
    return redirect(request.form.get("next") or url_for("plans.detail", id=id))
