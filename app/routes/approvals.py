from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app.models import db, Ledger, Valve, ApprovalLog
from app.devices import DeviceTypeRegistry
from app.routes.valves.permissions import require_leader
from datetime import datetime

approvals = Blueprint("approvals", __name__)


@approvals.route("/approvals")
@login_required
@require_leader
def index():
    tab = request.args.get("tab", "pending")
    pending_count = Valve.query.filter_by(status="pending").count()
    for config in DeviceTypeRegistry.exclude_valve():
        if config.model_class:
            pending_count += config.model_class.query.filter_by(status="pending").count()

    all_ledgers = Ledger.query.order_by(Ledger.created_at.desc()).all()

    # 为每个合集统计各种设备类型的审批数量
    for ledger in all_ledgers:
        if ledger.类型 == "valve":
            total_q = Valve.query.filter_by(ledger_id=ledger.id)
            ledger.total_count = total_q.count()
            ledger.pending_count = total_q.filter_by(status="pending").count()
            ledger.approved_count = total_q.filter_by(status="approved").count()
            ledger.rejected_count = total_q.filter_by(status="rejected").count()
            ledger.draft_count = total_q.filter_by(status="draft").count()
        else:
            config = DeviceTypeRegistry.get(ledger.类型)
            if config and config.model_class:
                model = config.model_class
                total_q = model.query.filter_by(ledger_id=ledger.id)
                ledger.total_count = total_q.count()
                ledger.pending_count = total_q.filter_by(status="pending").count()
                ledger.approved_count = total_q.filter_by(status="approved").count()
                ledger.rejected_count = total_q.filter_by(status="rejected").count()
                ledger.draft_count = total_q.filter_by(status="draft").count()
            else:
                ledger.total_count = ledger.pending_count = ledger.approved_count = ledger.rejected_count = ledger.draft_count = 0

    if tab == "pending":
        ledgers = [l for l in all_ledgers if l.pending_count > 0]
    elif tab == "approved":
        ledgers = [l for l in all_ledgers if l.approved_count > 0 and l.pending_count == 0]
    elif tab == "rejected":
        ledgers = [l for l in all_ledgers if l.rejected_count > 0]
    else:
        ledgers = []

    for ledger in ledgers:
        ledger.valve_count = ledger.total_count

    return render_template(
        "approvals/index.html", ledgers=ledgers, tab=tab, pending_count=pending_count
    )


def _approve_ledger(ledger, user_id, comment=""):
    """审批通过台账合集（支持阀门和非阀门类型）"""
    approved_count = 0
    if ledger.类型 == "valve":
        pending = Valve.query.filter_by(ledger_id=ledger.id, status="pending").all()
        for device in pending:
            device.status = "approved"
            device.approved_by = user_id
            device.approved_at = datetime.utcnow()
            log = ApprovalLog(
                ledger_id=ledger.id, valve_id=device.id,
                action="approve", user_id=user_id, comment=comment,
            )
            db.session.add(log)
            approved_count += 1
    else:
        config = DeviceTypeRegistry.get(ledger.类型)
        if config and config.model_class:
            pending = config.model_class.query.filter_by(ledger_id=ledger.id, status="pending").all()
            for device in pending:
                device.status = "approved"
                device.approved_by = user_id
                device.approved_at = datetime.utcnow()
                log = ApprovalLog(
                    ledger_id=ledger.id, device_type=ledger.类型, device_id=device.id,
                    action="approve", user_id=user_id, comment=comment,
                )
                db.session.add(log)
                approved_count += 1
    if approved_count > 0:
        total = _count_ledger_devices(ledger)
        approved = _count_ledger_devices(ledger, "approved")
        if approved == total and total > 0:
            ledger.status = "approved"
            ledger.approved_snapshot_status = "approved"
            ledger.approved_snapshot_at = datetime.utcnow()
        elif approved > 0:
            ledger.status = "approved"
    return approved_count


def _reject_ledger(ledger, user_id, comment=""):
    """驳回台账合集（支持阀门和非阀门类型）"""
    rejected_count = 0
    if ledger.类型 == "valve":
        pending = Valve.query.filter_by(ledger_id=ledger.id, status="pending").all()
        for device in pending:
            device.status = "rejected"
            log = ApprovalLog(
                ledger_id=ledger.id, valve_id=device.id,
                action="reject", user_id=user_id, comment=comment,
            )
            db.session.add(log)
            rejected_count += 1
    else:
        config = DeviceTypeRegistry.get(ledger.类型)
        if config and config.model_class:
            pending = config.model_class.query.filter_by(ledger_id=ledger.id, status="pending").all()
            for device in pending:
                device.status = "rejected"
                log = ApprovalLog(
                    ledger_id=ledger.id, device_type=ledger.类型, device_id=device.id,
                    action="reject", user_id=user_id, comment=comment,
                )
                db.session.add(log)
                rejected_count += 1
    if rejected_count > 0:
        ledger.status = "rejected"
    return rejected_count


def _count_ledger_devices(ledger, status=None):
    """统计台账合集中的设备数量（支持阀门和非阀门类型）"""
    if ledger.类型 == "valve":
        q = Valve.query.filter_by(ledger_id=ledger.id)
    else:
        config = DeviceTypeRegistry.get(ledger.类型)
        if not config or not config.model_class:
            return 0
        q = config.model_class.query.filter_by(ledger_id=ledger.id)
    if status:
        q = q.filter_by(status=status)
    return q.count()


@approvals.route("/approvals/batch-approve", methods=["POST"])
@login_required
@require_leader
def batch_approve():
    ledger_ids = request.form.getlist("ledger_ids")
    comment = request.form.get("comment", "")
    approved_count = 0
    for ledger_id in ledger_ids:
        ledger = Ledger.query.get(ledger_id)
        if not ledger:
            continue
        approved_count += _approve_ledger(ledger, current_user.id, comment)
        db.session.commit()
    flash(f"已审批 {approved_count} 项台账内容")
    return redirect(url_for("approvals.index"))


@approvals.route("/approvals/batch-reject", methods=["POST"])
@login_required
@require_leader
def batch_reject():
    ledger_ids = request.form.getlist("ledger_ids")
    comment = request.form.get("comment", "")
    rejected_count = 0
    for ledger_id in ledger_ids:
        ledger = Ledger.query.get(ledger_id)
        if not ledger:
            continue
        rejected_count += _reject_ledger(ledger, current_user.id, comment)
        db.session.commit()
    flash(f"已驳回 {rejected_count} 项台账内容")
    return redirect(url_for("approvals.index"))


@approvals.route("/approvals/<int:id>/approve", methods=["POST"])
@login_required
@require_leader
def single_approve(id):
    ledger = Ledger.query.get_or_404(id)
    comment = request.form.get("comment", "")
    approved_count = _approve_ledger(ledger, current_user.id, comment)
    db.session.commit()
    flash(f"已审批台账合集：{ledger.名称}")
    return redirect(url_for("approvals.index"))
