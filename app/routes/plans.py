from flask import (
    Blueprint, render_template, redirect, url_for, request, flash, jsonify,
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
