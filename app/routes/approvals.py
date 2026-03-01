from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app.models import db, Ledger, Valve, ApprovalLog
from app.routes.valves.permissions import require_leader
from datetime import datetime

approvals = Blueprint("approvals", __name__)


@approvals.route("/approvals")
@login_required
@require_leader
def index():
    tab = request.args.get("tab", "pending")
    pending_count = Valve.query.filter_by(status="pending").count()

    if tab == "pending":
        ledgers = (
            Ledger.query.join(Valve)
            .filter(Valve.status == "pending")
            .distinct()
            .order_by(Ledger.created_at.desc())
            .all()
        )
    elif tab == "approved":
        ledgers = (
            Ledger.query.filter(Ledger.approved_snapshot_status == "approved")
            .order_by(Ledger.created_at.desc())
            .all()
        )
    elif tab == "rejected":
        ledgers = (
            Ledger.query.join(Valve)
            .filter(Valve.status == "rejected")
            .distinct()
            .order_by(Ledger.created_at.desc())
            .all()
        )
    else:
        ledgers = []

    for ledger in ledgers:
        ledger.valve_count = Valve.query.filter_by(ledger_id=ledger.id).count()
        ledger.pending_count = Valve.query.filter_by(
            ledger_id=ledger.id, status="pending"
        ).count()
        ledger.approved_count = Valve.query.filter_by(
            ledger_id=ledger.id, status="approved"
        ).count()
        ledger.rejected_count = Valve.query.filter_by(
            ledger_id=ledger.id, status="rejected"
        ).count()
        ledger.draft_count = Valve.query.filter_by(
            ledger_id=ledger.id, status="draft"
        ).count()

    return render_template(
        "approvals/index.html", ledgers=ledgers, tab=tab, pending_count=pending_count
    )


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

        pending_valves = Valve.query.filter_by(
            ledger_id=ledger_id, status="pending"
        ).all()

        for valve in pending_valves:
            valve.status = "approved"
            valve.approved_by = current_user.id
            valve.approved_at = datetime.utcnow()

            log = ApprovalLog(
                ledger_id=ledger.id,
                valve_id=valve.id,
                action="approve",
                user_id=current_user.id,
                comment=comment,
            )
            db.session.add(log)
            approved_count += 1

        total = Valve.query.filter_by(ledger_id=ledger_id).count()
        approved = Valve.query.filter_by(ledger_id=ledger_id, status="approved").count()

        if approved == total and total > 0:
            ledger.status = "approved"
            ledger.approved_snapshot_status = "approved"
            ledger.approved_snapshot_at = datetime.utcnow()
        elif approved > 0:
            ledger.status = "approved"

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

        pending_valves = Valve.query.filter_by(
            ledger_id=ledger_id, status="pending"
        ).all()

        for valve in pending_valves:
            valve.status = "rejected"

            log = ApprovalLog(
                ledger_id=ledger.id,
                valve_id=valve.id,
                action="reject",
                user_id=current_user.id,
                comment=comment,
            )
            db.session.add(log)
            rejected_count += 1

        ledger.status = "rejected"
        db.session.commit()

    flash(f"已驳回 {rejected_count} 项台账内容")
    return redirect(url_for("approvals.index"))


@approvals.route("/approvals/<int:id>/approve", methods=["POST"])
@login_required
@require_leader
def single_approve(id):
    ledger = Ledger.query.get_or_404(id)
    comment = request.form.get("comment", "")

    pending_valves = Valve.query.filter_by(ledger_id=id, status="pending").all()

    for valve in pending_valves:
        valve.status = "approved"
        valve.approved_by = current_user.id
        valve.approved_at = datetime.utcnow()

        log = ApprovalLog(
            ledger_id=ledger.id,
            valve_id=valve.id,
            action="approve",
            user_id=current_user.id,
            comment=comment,
        )
        db.session.add(log)

    total = Valve.query.filter_by(ledger_id=id).count()
    approved = Valve.query.filter_by(ledger_id=id, status="approved").count()

    if approved == total and total > 0:
        ledger.status = "approved"
        ledger.approved_snapshot_status = "approved"
        ledger.approved_snapshot_at = datetime.utcnow()
    elif approved > 0:
        ledger.status = "approved"

    db.session.commit()

    flash(f"已审批台账合集：{ledger.名称}")
    return redirect(url_for("approvals.index"))
