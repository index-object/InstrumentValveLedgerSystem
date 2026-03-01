from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    jsonify,
)
from flask_login import login_required, current_user
from app.models import db, Valve, ApprovalLog, Ledger, ValveAttachment
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import json

from app.routes.valves.permissions import (
    can_edit_valve,
    can_delete_valve,
    can_view_valve,
    require_leader,
    require_edit_permission,
    require_delete_permission,
)
from app.routes.valves.forms import (
    populate_valve_from_form,
    process_attachments_create,
    process_attachments_update,
    set_valve_status_after_submit,
    parse_attachments_data,
    create_attachment_from_data,
)

valves = Blueprint("valves", __name__)


def update_ledger_status(ledger):
    total = Valve.query.filter_by(ledger_id=ledger.id).count()
    if total == 0:
        return
    approved = Valve.query.filter_by(ledger_id=ledger.id, status="approved").count()
    if approved == total:
        ledger.status = "approved"
        ledger.approved_at = datetime.utcnow()


@valves.route("/valve/check-tag")
@login_required
def check_tag():
    tag = request.args.get("位号")
    if not tag:
        return jsonify({"valid": True})

    exclude_id = request.args.get("exclude_id", type=int)
    query = Valve.query.filter(Valve.位号 == tag, Valve.status != "draft")
    if exclude_id:
        query = query.filter(Valve.id != exclude_id)

    exists = query.first() is not None
    return jsonify({"valid": not exists, "message": "位号已存在" if exists else None})


@valves.route("/valves")
@login_required
def list():
    return redirect(url_for("ledgers.list"))


@valves.route("/valve/<int:id>")
@login_required
def detail(id):
    valve = Valve.query.get_or_404(id)
    if not can_view_valve(valve):
        flash("无权访问")
        return redirect(url_for("valves.list"))
    return render_template("valves/detail.html", valve=valve)


@valves.route("/valve/new", methods=["GET", "POST"])
@login_required
def new():
    if request.method == "POST":
        valve_id = request.form.get("valve_id")

        if valve_id:
            valve = Valve.query.get(valve_id)
            if valve and can_edit_valve(valve):
                populate_valve_from_form(valve, request.form)
                db.session.commit()
            else:
                flash("台账不存在或无权编辑")
                return redirect(url_for("valves.new"))
        else:
            位号 = request.form.get("位号")
            if 位号:
                existing = Valve.query.filter(
                    Valve.位号 == 位号, Valve.status != "draft"
                ).first()
                if existing:
                    flash("位号已存在，请使用其他位号")
                    return redirect(url_for("valves.new"))

            valve = Valve()
            populate_valve_from_form(valve, request.form)
            valve.created_by = current_user.id
            valve.status = "draft"

            try:
                db.session.add(valve)
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                draft = Valve.query.filter(
                    Valve.位号 == 位号,
                    Valve.status == "draft",
                    Valve.created_by == current_user.id,
                ).first()
                if draft:
                    db.session.delete(draft)
                    db.session.commit()
                    try:
                        db.session.add(valve)
                        db.session.commit()
                    except IntegrityError:
                        db.session.rollback()
                        flash("位号已存在，请使用其他位号")
                        return redirect(url_for("valves.new"))
                else:
                    flash("位号已存在，请使用其他位号")
                    return redirect(url_for("valves.new"))

        log = ApprovalLog(valve_id=valve.id, action="submit", user_id=current_user.id)
        db.session.add(log)

        action = set_valve_status_after_submit(valve, current_user.id)
        log.action = action
        db.session.commit()

        if valve_id:
            process_attachments_update(db, valve, request.form.get("attachments"))
        else:
            process_attachments_create(db, valve.id, request.form.get("attachments"))
        db.session.commit()

        flash("提交成功")
        return redirect(url_for("valves.list"))

    return render_template("valves/form.html", valve=None)


@valves.route("/valve/draft/save", methods=["POST"])
@login_required
def save_draft():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "无效数据"})

    valve_id = data.get("valve_id")
    ledger_id = data.get("ledger_id")

    if valve_id:
        valve = Valve.query.get(valve_id)
        if not valve:
            return jsonify({"success": False, "message": "台账不存在"})
        if not can_edit_valve(valve):
            return jsonify({"success": False, "message": "无权编辑"})
    else:
        if ledger_id:
            valve = Valve.query.filter_by(
                ledger_id=ledger_id, status="draft", created_by=current_user.id
            ).first()
            if not valve:
                valve = Valve()
                valve.created_by = current_user.id
                valve.status = "draft"
                valve.ledger_id = ledger_id
                db.session.add(valve)
                db.session.flush()
        else:
            valve = Valve()
            valve.created_by = current_user.id
            valve.status = "draft"
            db.session.add(valve)
            db.session.flush()

    for key, value in data.get("formData", {}).items():
        if key == "ledger_id":
            continue
        if hasattr(valve, key):
            setattr(valve, key, value)

    db.session.flush()

    attachments_json = data.get("attachments")
    if attachments_json:
        try:
            attachments = json.loads(attachments_json)
            existing_ids = {att.id for att in valve.attachments}
            submitted_ids = set()
            for att in attachments:
                att_type = att.get("attachment_type") or att.get("type")
                if not att_type:
                    continue
                att_id = att.get("id")
                if att_id:
                    attachment = ValveAttachment.query.filter(
                        ValveAttachment.id == att_id,
                        ValveAttachment.valve_id == valve.id,
                    ).first()
                    if attachment:
                        attachment.type = att_type
                        attachment.名称 = att.get("name") or att.get("名称", "")
                        attachment.设备等级 = att.get("device_grade") or att.get(
                            "设备等级", ""
                        )
                        attachment.型号规格 = att.get("model") or att.get(
                            "型号规格", ""
                        )
                        attachment.生产厂家 = att.get("manufacturer") or att.get(
                            "生产厂家", ""
                        )
                        submitted_ids.add(att_id)
                else:
                    att_type = att.get("attachment_type") or att.get("type")
                    att_name = att.get("name") or att.get("名称", "")
                    att_grade = att.get("device_grade") or att.get("设备等级", "")
                    att_model = att.get("model") or att.get("型号规格", "")
                    att_manufacturer = att.get("manufacturer") or att.get(
                        "生产厂家", ""
                    )
                    if att_type:
                        attachment = ValveAttachment(
                            valve_id=valve.id,
                            type=att_type,
                            名称=att_name,
                            设备等级=att_grade,
                            型号规格=att_model,
                            生产厂家=att_manufacturer,
                        )
                        db.session.add(attachment)
            for att_id in existing_ids - submitted_ids:
                attachment = ValveAttachment.query.filter(
                    ValveAttachment.id == att_id,
                    ValveAttachment.valve_id == valve.id,
                ).first()
                if attachment:
                    db.session.delete(attachment)
        except json.JSONDecodeError:
            pass

    db.session.commit()
    return jsonify({"success": True, "valve_id": valve.id})


@valves.route("/valve/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit(id):
    valve = Valve.query.get_or_404(id)

    error = require_edit_permission(valve)
    if error:
        flash(error)
        return redirect(url_for("valves.detail", id=id))

    if request.method == "POST":
        位号 = request.form.get("位号")
        if 位号:
            existing = Valve.query.filter(
                Valve.位号 == 位号, Valve.status != "draft", Valve.id != id
            ).first()
            if existing:
                flash("位号已存在，请使用其他位号")
                return redirect(url_for("valves.edit", id=id))

        populate_valve_from_form(valve, request.form)

        process_attachments_update(db, valve, request.form.get("attachments"))
        db.session.commit()

        flash("保存成功")
        return redirect(url_for("valves.detail", id=id))

    return render_template("valves/form.html", valve=valve)


@valves.route("/valve/delete/<int:id>", methods=["POST"])
@login_required
def delete(id):
    valve = Valve.query.get_or_404(id)

    error = require_delete_permission(valve)
    if error:
        flash(error)
        return redirect(url_for("valves.detail", id=id))

    db.session.delete(valve)
    db.session.commit()
    flash("删除成功")
    return redirect(url_for("valves.list"))


@valves.route("/valves/batch-delete", methods=["POST"])
@login_required
def batch_delete():
    ids = request.form.getlist("ids")
    if not ids:
        flash("请选择要删除的记录")
        return redirect(url_for("valves.list"))

    count = 0
    for id in ids:
        valve = Valve.query.get(int(id))
        if valve and valve.status in ["draft", "rejected"] and can_delete_valve(valve):
            ApprovalLog.query.filter_by(valve_id=valve.id).delete()
            db.session.delete(valve)
            count += 1

    db.session.commit()
    flash(f"成功删除 {count} 条记录")
    return redirect(url_for("valves.list"))


@valves.route("/valves/batch-approve", methods=["POST"])
@login_required
@require_leader
def batch_approve():
    return redirect(url_for("approvals.index"))


@valves.route("/valves/batch-reject", methods=["POST"])
@login_required
@require_leader
def batch_reject():
    return redirect(url_for("approvals.index"))


@valves.route("/my-applications")
@login_required
def my_applications():
    my_valves = (
        Valve.query.filter_by(created_by=current_user.id)
        .order_by(Valve.created_at.desc())
        .all()
    )
    return render_template("valves/my_applications.html", valves=my_valves)


@valves.route("/approvals")
@login_required
@require_leader
def approvals():
    return redirect(url_for("approvals.index"))


@valves.route("/valve/approve/<int:id>", methods=["POST"])
@login_required
@require_leader
def approve(id):
    return redirect(url_for("approvals.index"))


@valves.route("/valve/reject/<int:id>", methods=["POST"])
@login_required
@require_leader
def reject(id):
    return redirect(url_for("approvals.index"))


from app.routes.valves.exports import register_export_routes
from app.routes.valves.attachments import register_attachment_routes

register_export_routes(valves)
register_attachment_routes(valves)
