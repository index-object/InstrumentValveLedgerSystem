from flask import (
    Blueprint, render_template, redirect, url_for, request, flash, jsonify, abort,
)
from flask_login import login_required, current_user
from app.models import db, MaintenancePlan, MaintenancePlanItem, Notification, User
from app.devices.valve_helper import get_valve_model, get_valve_ledger_type, get_all_valve_models
from app.devices import DeviceTypeRegistry
from datetime import datetime, date, timedelta
from sqlalchemy import or_

plans_bp = Blueprint("plans", __name__, url_prefix="")


@plans_bp.context_processor
def inject_plan_nav():
    if current_user.is_authenticated:
        now = date.today()
        warning_count = 0
        if current_user.role in ("employee", "admin"):
            published_plan_ids = db.session.query(MaintenancePlan.id).filter(
                MaintenancePlan.status == "published"
            ).subquery()
            seven_days_later = now + timedelta(days=7)
            warning_count = MaintenancePlanItem.query.filter(
                MaintenancePlanItem.plan_id.in_(published_plan_ids),
                MaintenancePlanItem.status == "pending",
                MaintenancePlanItem.planned_date_end >= now.isoformat(),
                MaintenancePlanItem.planned_date_end <= seven_days_later.isoformat(),
            ).count() + MaintenancePlanItem.query.filter(
                MaintenancePlanItem.plan_id.in_(published_plan_ids),
                MaintenancePlanItem.status == "pending",
                MaintenancePlanItem.planned_date_end < now.isoformat(),
            ).count()
        return dict(plan_warning_count=warning_count)
    return dict(plan_warning_count=0)


@plans_bp.route("/plans")
@login_required
def index():
    query = MaintenancePlan.query
    if current_user.role == "employee":
        query = query.filter(MaintenancePlan.status.in_(["published", "archived"]))
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
        overdue = sum(1 for i in items if i.status == "pending" and i.planned_date_end < now)
        p._completed = completed
        p._overdue = overdue
        p._total = len(items)

    stats = {
        "total": len(plans),
        "draft": sum(1 for p in plans if p.status == "draft"),
        "published": sum(1 for p in plans if p.status == "published"),
        "archived": sum(1 for p in plans if p.status == "archived"),
    }
    return render_template("plans/list.html", plans=plans, stats=stats)


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
            return render_template("plans/form.html")
        plan = MaintenancePlan(
            title=title,
            description=request.form.get("description", "").strip(),
            created_by=current_user.id,
        )
        db.session.add(plan)
        db.session.commit()
        flash("计划已保存为草稿")
        return redirect(url_for("plans.detail", id=plan.id))

    return render_template("plans/form.html")


@plans_bp.route("/plan/<int:id>")
@login_required
def detail(id):
    plan = MaintenancePlan.query.get_or_404(id)
    if current_user.role == "employee" and plan.status not in ("published", "archived"):
        flash("无权查看此计划")
        return redirect(url_for("plans.index"))

    now = date.today()
    items = MaintenancePlanItem.query.filter_by(plan_id=plan.id).order_by(
        MaintenancePlanItem.planned_date_start
    ).all()

    for item in items:
        if item.status == "pending" and item.planned_date_end < now:
            item._overdue = True
        else:
            item._overdue = False

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
    for config in DeviceTypeRegistry.all():
        if config.model_class and config.code not in ("control_valve", "onoff_valve", "electric_valve"):
            for d in config.model_class.query.filter(config.model_class.status == "approved").order_by(config.model_class.位号).all():
                approved_devices.append({
                    "id": d.id,
                    "type": config.code,
                    "tag": d.位号,
                    "name": getattr(d, '设备名称', '') or getattr(d, '名称', '') or '',
                    "unit": getattr(d, '装置名称', '') or '',
                })

    return render_template("plans/detail.html", plan=plan, items=items, approved_devices=approved_devices)


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
        db.session.commit()
        flash("计划已更新")
        return redirect(url_for("plans.detail", id=id))

    return render_template("plans/form.html", plan=plan)


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

    recipients = User.query.filter(User.role.in_(["employee", "admin"]), User.status == "active").all()
    for user in recipients:
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
    flash(f"计划已发布，已通知 {len(recipients)} 位用户")
    return redirect(url_for("plans.detail", id=id))


@plans_bp.route("/plan/<int:id>/archive", methods=["POST"])
@login_required
def archive(id):
    plan = MaintenancePlan.query.get_or_404(id)
    if current_user.role not in ("leader", "admin"):
        flash("无权归档")
        return redirect(url_for("plans.detail", id=id))
    if plan.status != "published":
        flash("只能归档已发布的计划")
        return redirect(url_for("plans.detail", id=id))
    plan.status = "archived"
    db.session.commit()
    flash("计划已归档")
    return redirect(url_for("plans.detail", id=id))


@plans_bp.route("/plan/<int:id>/delete", methods=["POST"])
@login_required
def delete(id):
    plan = MaintenancePlan.query.get_or_404(id)
    if current_user.role not in ("leader", "admin"):
        flash("无权删除")
        return redirect(url_for("plans.detail", id=id))
    if plan.status != "draft":
        flash("只能删除草稿状态的计划")
        return redirect(url_for("plans.detail", id=id))
    db.session.delete(plan)
    db.session.commit()
    flash("计划已删除")
    return redirect(url_for("plans.index"))


@plans_bp.route("/plan/<int:id>/items/add", methods=["POST"])
@login_required
def add_items(id):
    plan = MaintenancePlan.query.get_or_404(id)
    if current_user.role not in ("leader", "admin"):
        return jsonify({"error": "无权操作"}), 403
    if plan.status not in ("draft", "published"):
        return jsonify({"error": "当前状态无法添加阀门"}), 400

    data = request.get_json() or request.form
    devices = data.get("devices", [])
    planned_date_start = data.get("planned_date_start")
    planned_date_end = data.get("planned_date_end")

    added = 0
    for dev in devices:
        device_type = dev.get("type")
        device_id = int(dev.get("id"))
        tag = dev.get("tag", "")
        device_name = dev.get("name", "")

        exists = MaintenancePlanItem.query.filter_by(
            plan_id=plan.id, device_type=device_type, device_id=device_id
        ).first()
        if exists:
            continue

        item = MaintenancePlanItem(
            plan_id=plan.id,
            device_type=device_type,
            device_id=device_id,
            tag=tag,
            device_name=device_name,
            planned_date_start=datetime.strptime(planned_date_start, "%Y-%m-%d").date() if planned_date_start else date.today(),
            planned_date_end=datetime.strptime(planned_date_end, "%Y-%m-%d").date() if planned_date_end else date.today(),
        )
        db.session.add(item)
        added += 1

    plan.total_items = MaintenancePlanItem.query.filter_by(plan_id=plan.id).count()
    db.session.commit()
    return jsonify({"added": added, "total": plan.total_items})


@plans_bp.route("/plan/<int:plan_id>/items/<int:item_id>/remove", methods=["POST"])
@login_required
def remove_item(plan_id, item_id):
    plan = MaintenancePlan.query.get_or_404(plan_id)
    if current_user.role not in ("leader", "admin"):
        flash("无权操作")
        return redirect(url_for("plans.detail", id=plan_id))
    if plan.status not in ("draft", "published"):
        flash("当前状态无法移除阀门")
        return redirect(url_for("plans.detail", id=plan_id))

    item = MaintenancePlanItem.query.get_or_404(item_id)
    if item.plan_id != plan.id:
        abort(404)
    if item.status == "completed":
        flash("已完成项不能移除")
        return redirect(url_for("plans.detail", id=plan_id))

    db.session.delete(item)
    plan.total_items = MaintenancePlanItem.query.filter_by(plan_id=plan.id).count()
    db.session.commit()
    flash("阀门已从计划中移除")
    return redirect(url_for("plans.detail", id=plan_id))
