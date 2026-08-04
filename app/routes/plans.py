from flask import (
    Blueprint, render_template, redirect, url_for, request, flash,
)
from flask_login import login_required, current_user
from app.models import db, MaintenancePlan, MaintenancePlanItem, Notification, User
from app.devices.valve_helper import get_valve_ledger_type, get_all_valve_models
from datetime import datetime, date

plans_bp = Blueprint("plans", __name__, url_prefix="")


def _approved_devices():
    approved_devices = []
    for model in get_all_valve_models():
        for v in model.query.filter(model.status == "approved").order_by(model.位号).all():
            approved_devices.append({
                "id": v.id,
                "type": get_valve_ledger_type(v),
                "tag": v.位号,
                "name": v.名称 or "",
                "unit": v.装置名称 or "",
            })
    return approved_devices


def _parse_rows(rows_json):
    import json
    if not rows_json:
        return []
    try:
        rows = json.loads(rows_json)
    except (ValueError, TypeError):
        return []
    parsed = []
    for row in rows:
        devices = row.get("devices") or []
        if not devices:
            continue
        planned_date_end = row.get("planned_date_end") or ""
        try:
            end = datetime.strptime(planned_date_end, "%Y-%m-%d").date() if planned_date_end else date.today()
        except ValueError:
            end = date.today()
        parsed.append({
            "devices": [{"type": d.get("type"), "id": int(d.get("id")), "tag": d.get("tag", ""), "name": d.get("name", "")} for d in devices],
            "planned_date_end": end,
            "maintenance_project": row.get("maintenance_project", "").strip(),
            "maintenance_scheme": row.get("maintenance_scheme", "").strip(),
            "safety_measures": row.get("safety_measures", "").strip(),
            "project_leader": row.get("project_leader", "").strip(),
            "maintenance_leader": row.get("maintenance_leader", "").strip(),
            "quality_acceptance": row.get("quality_acceptance", "").strip(),
            "remark": row.get("remark", "").strip(),
        })
    return parsed


def _save_items(plan, rows):
    for idx, row in enumerate(rows, start=1):
        for dev in row["devices"]:
            item = MaintenancePlanItem(
                plan_id=plan.id,
                device_type=dev["type"],
                device_id=dev["id"],
                tag=dev["tag"],
                device_name=dev["name"],
                planned_date_start=row["planned_date_end"],
                planned_date_end=row["planned_date_end"],
                maintenance_project=row["maintenance_project"],
                maintenance_scheme=row["maintenance_scheme"],
                safety_measures=row["safety_measures"],
                project_leader=row["project_leader"],
                maintenance_leader=row["maintenance_leader"],
                quality_acceptance=row["quality_acceptance"],
                remark=row["remark"],
                group_id=idx,
            )
            db.session.add(item)


def _is_overdue(item, now):
    """逾期：待办且超过计划结束日期；或已完成但实际检修时间晚于计划结束日期"""
    if item.status == "pending":
        return item.planned_date_end is not None and item.planned_date_end < now
    if item.status == "completed" and item.maintenance_record:
        rec_time = item.maintenance_record.检修时间
        if rec_time and item.planned_date_end:
            return rec_time.date() > item.planned_date_end
    return False


def _load_rows(plan_id):
    items = MaintenancePlanItem.query.filter_by(plan_id=plan_id).order_by(
        MaintenancePlanItem.group_id, MaintenancePlanItem.planned_date_end
    ).all()
    groups = {}
    order = []
    for item in items:
        gid = item.group_id or (len(order) + 1)
        if gid not in groups:
            groups[gid] = {
                "planned_date_end": item.planned_date_end.strftime("%Y-%m-%d"),
                "maintenance_project": item.maintenance_project or "",
                "maintenance_scheme": item.maintenance_scheme or "",
                "safety_measures": item.safety_measures or "",
                "project_leader": item.project_leader or "",
                "maintenance_leader": item.maintenance_leader or "",
                "quality_acceptance": item.quality_acceptance or "",
                "remark": item.remark or "",
                "devices": [],
            }
            order.append(gid)
        groups[gid]["devices"].append({
            "type": item.device_type,
            "id": item.device_id,
            "tag": item.tag,
            "name": item.device_name or "",
        })
    return [groups[gid] for gid in sorted(order, key=lambda g: groups[g]["planned_date_end"])]


@plans_bp.route("/plans")
@login_required
def index():
    query = MaintenancePlan.query
    if current_user.role == "employee":
        query = query.filter(
            MaintenancePlan.status.in_(["published", "archived"]),
            MaintenancePlan.recipients.any(id=current_user.id)
        )
    search = request.args.get("search")
    status_filter = request.args.get("status")
    if search:
        query = query.filter(MaintenancePlan.title.contains(search))
    if status_filter:
        query = query.filter(MaintenancePlan.status == status_filter)
    plans = query.order_by(MaintenancePlan.created_at.desc()).all()

    now = date.today()
    for p in plans:
        items = MaintenancePlanItem.query.filter_by(plan_id=p.id).all()
        completed = sum(1 for i in items if i.status == "completed")
        overdue = sum(1 for i in items if _is_overdue(i, now))
        p._completed = completed
        p._overdue = overdue
        p._total = len(items)

    stats = {
        "total": len(plans),
        "draft": sum(1 for p in plans if p.status == "draft"),
        "published": sum(1 for p in plans if p.status == "published"),
        "archived": sum(1 for p in plans if p.status == "archived"),
    }
    employees = User.query.filter(User.role == "employee", User.status == "active").order_by(User.real_name).all() if current_user.role in ("leader", "admin") else []
    return render_template("plans/list.html", plans=plans, stats=stats, employees=employees)


@plans_bp.route("/plan/<int:id>")
@login_required
def detail(id):
    plan = MaintenancePlan.query.get_or_404(id)
    if current_user.role == "employee":
        if plan.status not in ("published", "archived") or current_user not in plan.recipients:
            flash("无权查看此计划")
            return redirect(url_for("plans.index"))

    now = date.today()
    items = MaintenancePlanItem.query.filter_by(plan_id=plan.id).order_by(
        MaintenancePlanItem.group_id, MaintenancePlanItem.planned_date_end, MaintenancePlanItem.id
    ).all()

    for item in items:
        item._overdue = _is_overdue(item, now)

    groups = {}
    order = []
    for item in items:
        gid = item.group_id or (len(order) + 1)
        if gid not in groups:
            groups[gid] = {
                "planned_date_end": item.planned_date_end,
                "maintenance_project": item.maintenance_project or "",
                "maintenance_scheme": item.maintenance_scheme or "",
                "safety_measures": item.safety_measures or "",
                "project_leader": item.project_leader or "",
                "maintenance_leader": item.maintenance_leader or "",
                "quality_acceptance": item.quality_acceptance or "",
                "remark": item.remark or "",
                "devices": [],
            }
            order.append(gid)
        groups[gid]["devices"].append(item)

    group_list = [groups[gid] for gid in order]
    for g in group_list:
        g["completed"] = sum(1 for d in g["devices"] if d.status == "completed")
        g["overdue"] = sum(1 for d in g["devices"] if d._overdue)

    employees = User.query.filter(User.role == "employee", User.status == "active").order_by(User.real_name).all()
    return render_template("plans/detail.html", plan=plan, items=items, groups=group_list, employees=employees)


@plans_bp.route("/plan/new", methods=["GET", "POST"])
@login_required
def create():
    if current_user.role not in ("leader", "admin"):
        flash("无权创建检修计划")
        return redirect(url_for("plans.index"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("请输入计划标题")
            return render_template("plans/form.html", approved_devices=_approved_devices())
        rows = _parse_rows(request.form.get("rows_json"))
        if not rows:
            flash("请至少添加一行计划明细")
            return render_template("plans/form.html", approved_devices=_approved_devices())

        plan = MaintenancePlan(
            title=title,
            description=request.form.get("description", "").strip(),
            created_by=current_user.id,
        )
        db.session.add(plan)
        db.session.flush()
        _save_items(plan, rows)
        plan.total_items = MaintenancePlanItem.query.filter_by(plan_id=plan.id).count()
        db.session.commit()
        flash("计划已保存为草稿")
        return redirect(url_for("plans.detail", id=plan.id))

    return render_template("plans/form.html", approved_devices=_approved_devices())


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
        plan.title = request.form.get("title", "").strip() or plan.title
        plan.description = request.form.get("description", "").strip()
        rows = _parse_rows(request.form.get("rows_json"))
        if not rows:
            flash("请至少添加一行计划明细")
            return render_template("plans/form.html", plan=plan, approved_devices=_approved_devices())
        MaintenancePlanItem.query.filter_by(plan_id=plan.id).delete()
        _save_items(plan, rows)
        plan.total_items = MaintenancePlanItem.query.filter_by(plan_id=plan.id).count()
        db.session.commit()
        flash("计划已更新")
        return redirect(url_for("plans.detail", id=id))

    groups = _load_rows(plan.id)
    return render_template("plans/form.html", plan=plan, groups=groups, approved_devices=_approved_devices())


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
    if plan.total_items == 0:
        flash("请先添加阀门后再发布")
        return redirect(url_for("plans.detail", id=id))

    plan.status = "published"
    plan.published_by = current_user.id
    plan.published_at = datetime.utcnow()

    recipient_ids = request.form.getlist("recipient_ids")
    if recipient_ids:
        selected = User.query.filter(User.id.in_(recipient_ids)).all()
        for user in selected:
            plan.recipients.append(user)
            notification = Notification(
                user_id=user.id,
                type="plan_published",
                title=f"新检修计划发布：{plan.title}",
                content=plan.description or f"计划包含 {plan.total_items} 项检修任务，请及时查看并执行。",
                ref_type="plan",
                ref_id=plan.id,
            )
            db.session.add(notification)
        db.session.commit()
        flash(f"计划已发布，已通知 {len(selected)} 位用户")
    else:
        db.session.commit()
        flash("计划已发布（未选择通知对象）")
    return redirect(url_for("plans.detail", id=id))


@plans_bp.route("/plan/<int:id>/archive", methods=["POST"])
@login_required
def archive(id):
    plan = MaintenancePlan.query.get_or_404(id)
    if current_user.role not in ("leader", "admin"):
        flash("无权标记完成")
        return redirect(url_for("plans.detail", id=id))
    if plan.status != "published":
        flash("只能标记已发布的计划为已完成")
        return redirect(url_for("plans.detail", id=id))
    plan.status = "archived"

    for user in plan.recipients:
        notification = Notification(
            user_id=user.id,
            type="plan_archived",
            title=f"检修计划已完成：{plan.title}",
            content=f"计划已完成，共完成 {plan.completed_items}/{plan.total_items} 项检修任务。",
            ref_type="plan",
            ref_id=plan.id,
        )
        db.session.add(notification)

    db.session.commit()
    flash("计划已标记为完成")
    return redirect(url_for("plans.detail", id=id))


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
