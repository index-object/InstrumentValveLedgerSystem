from flask import (
    abort,
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    jsonify,
)
from flask_login import login_required, current_user
from app.models import db, Ledger, ApprovalLog, ValveAttachment
from app.utils.params import expects_params
from app.devices.valve_helper import (
    get_valve_model,
    get_valve_by_id,
    has_duplicate_tag,
    get_valve_ledger_type,
    get_all_valve_models,
    count_valves_by_status,
)
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import json

from app.routes.valves.permissions import (
    can_edit_valve,
    can_delete_valve,
    can_view_valve,
    can_submit_valve,
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
from app.utils.navigation import (
    get_from_param,
    get_context,
    redirect_to_list,
    url_with_from,
)

valves = Blueprint("valves", __name__)


def update_ledger_status(ledger):
    from app.devices.valve_helper import count_valves_by_status
    counts = count_valves_by_status(ledger.id)
    total = counts["total"]
    if total == 0:
        return
    approved = counts["approved"]
    if approved == total:
        ledger.status = "approved"
        ledger.approved_at = datetime.utcnow()


@valves.route("/valve/check-tag")
@login_required
def check_tag():
    tag = request.args.get("位号")
    if not tag:
        return jsonify({"valid": True})
    装置名称 = request.args.get("装置名称")
    exclude_id = request.args.get("exclude_id", type=int)
    exists = has_duplicate_tag(tag, exclude_id, 装置名称)
    return jsonify({"valid": not exists, "message": "该装置下此位号已存在" if exists else None})


@valves.route("/valves")
@login_required
def list():
    return redirect(url_for("ledgers.list"))


@valves.route("/valve/<int:id>")
@login_required
@expects_params(optional=['from'])
def detail(id):
    from_param = get_from_param()
    valve = get_valve_by_id(id)
    if not valve:
        abort(404)
    if not can_view_valve(valve):
        flash("无权访问")
        return redirect_to_list(from_param)
    return render_template("valves/detail.html", valve=valve, from_param=from_param)


@valves.route("/valve/new", methods=["GET", "POST"])
@login_required
def new():
    if request.method == "POST":
        valve_id = request.form.get("valve_id")

        if valve_id:
            valve = get_valve_by_id(valve_id)
            if valve and can_edit_valve(valve):
                populate_valve_from_form(valve, request.form)
                db.session.commit()
            else:
                flash("台账不存在或无权编辑")
                return redirect(url_for("valves.new"))
        else:
            位号 = request.form.get("位号")
            装置名称 = request.form.get("装置名称")
            if 位号:
                if has_duplicate_tag(位号, unit_name=装置名称):
                    flash("该装置下此位号已存在，请使用其他位号")
                    return redirect(url_for("valves.new"))

            ledger_id = request.form.get("ledger_id")
            if ledger_id:
                ledger_obj = Ledger.query.get(int(ledger_id))
                model = get_valve_model(ledger_obj)
            else:
                model = None

            if model is None:
                flash("无法确定阀门类型")
                return redirect(url_for("valves.new"))

            valve = model()
            populate_valve_from_form(valve, request.form)
            valve.created_by = current_user.id
            valve.status = "draft"

            try:
                db.session.add(valve)
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                draft = model.query.filter(
                    model.位号 == 位号,
                    model.status == "draft",
                    model.created_by == current_user.id,
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

        log = ApprovalLog(
            device_type=get_valve_ledger_type(valve),
            device_id=valve.id,
            action="submit",
            user_id=current_user.id,
        )
        db.session.add(log)

        action = set_valve_status_after_submit(valve, current_user.id)
        log.action = action
        db.session.commit()

        device_type = get_valve_ledger_type(valve)
        if valve_id:
            process_attachments_update(db, device_type, valve, request.form.get("attachments"))
        else:
            process_attachments_create(db, device_type, valve.id, request.form.get("attachments"))
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
        valve = get_valve_by_id(valve_id)
        if not valve:
            return jsonify({"success": False, "message": "台账不存在"})
        if not can_edit_valve(valve):
            return jsonify({"success": False, "message": "无权编辑"})
        device_type = get_valve_ledger_type(valve)
    else:
        if ledger_id:
            ledger_obj = Ledger.query.get(ledger_id)
            model = get_valve_model(ledger_obj)
            if model is None:
                return jsonify({"success": False, "message": "无效的台账类型"})
            valve = model.query.filter_by(
                ledger_id=ledger_id, status="draft", created_by=current_user.id
            ).first()
            if not valve:
                valve = model()
                valve.created_by = current_user.id
                valve.status = "draft"
                valve.ledger_id = ledger_id
                db.session.add(valve)
                db.session.flush()
            device_type = get_valve_ledger_type(valve)
        else:
            return jsonify({"success": False, "message": "无法确定阀门类型"})

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
                        ValveAttachment.device_type == device_type,
                        ValveAttachment.device_id == valve.id,
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
                            device_type=device_type,
                            device_id=valve.id,
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
                    ValveAttachment.device_type == device_type,
                    ValveAttachment.device_id == valve.id,
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
    from_param = get_from_param()
    valve = get_valve_by_id(id)
    if not valve:
        abort(404)

    error = require_edit_permission(valve)
    if error:
        flash(error)
        if valve.ledger_id:
            return redirect(url_for(
                'ledgers.valve_detail',
                ledger_id=valve.ledger_id,
                id=id,
                **{'from': from_param}
            ))
        return redirect(url_for("valves.detail", id=id, **{'from': from_param}))

    if request.method == "POST":
        位号 = request.form.get("位号")
        装置名称 = request.form.get("装置名称")
        if 位号:
            if has_duplicate_tag(位号, id, 装置名称):
                flash("该装置下此位号已存在，请使用其他位号")
                return redirect(url_for("valves.edit", id=id, **{'from': from_param}))

        populate_valve_from_form(valve, request.form)

        device_type = get_valve_ledger_type(valve)
        process_attachments_update(db, device_type, valve, request.form.get("attachments"))
        db.session.commit()

        flash("保存成功")
        if valve.ledger_id:
            return redirect(url_for(
                'ledgers.valve_detail',
                ledger_id=valve.ledger_id,
                id=id,
                **{'from': from_param}
            ))
        return redirect(url_for("valves.detail", id=id, **{'from': from_param}))

    ledger = None
    if valve.ledger_id:
        ledger = Ledger.query.get(valve.ledger_id)
    return render_template("valves/form.html", valve=valve, ledger=ledger, from_param=from_param)


@valves.route("/valve/delete/<int:id>", methods=["POST"])
@login_required
def delete(id):
    from_param = get_from_param()
    valve = get_valve_by_id(id)
    if not valve:
        abort(404)

    error = require_delete_permission(valve)
    if error:
        flash(error)
        if valve.ledger_id:
            return redirect(url_for(
                'ledgers.valve_detail',
                ledger_id=valve.ledger_id,
                id=id,
                **{'from': from_param}
            ))
        return redirect(url_for("valves.detail", id=id, **{'from': from_param}))

    ledger_id = valve.ledger_id
    device_type = get_valve_ledger_type(valve)
    ValveAttachment.query.filter_by(
        device_type=device_type, device_id=valve.id
    ).delete()
    db.session.delete(valve)
    db.session.commit()
    flash("删除成功")

    if ledger_id:
        return redirect(url_for('ledgers.detail', id=ledger_id, **{'from': from_param}))
    return redirect_to_list(from_param)


@valves.route("/valves/batch-delete", methods=["POST"])
@login_required
def batch_delete():
    from_param = get_from_param()
    ids = request.form.getlist("ids")
    if not ids:
        flash("请选择要删除的记录")
        return redirect_to_list(from_param)

    count = 0
    for id in ids:
        valve = get_valve_by_id(int(id))
        if valve and can_delete_valve(valve):
            device_type = get_valve_ledger_type(valve)
            ApprovalLog.query.filter_by(
                device_type=device_type, device_id=valve.id
            ).delete()
            ValveAttachment.query.filter_by(
                device_type=device_type, device_id=valve.id
            ).delete()
            db.session.delete(valve)
            count += 1

    db.session.commit()
    flash(f"成功删除 {count} 条记录")
    return redirect_to_list(from_param)


@valves.route("/my-applications")
@login_required
def my_applications():
    my_valves = []
    for model in get_all_valve_models():
        my_valves.extend(
            model.query.filter_by(created_by=current_user.id)
            .order_by(model.created_at.desc())
            .all()
        )
    my_valves.sort(key=lambda v: v.created_at or datetime.min, reverse=True)
    return render_template("valves/my_applications.html", valves=my_valves)


from app.routes.valves.exports import register_export_routes
from app.routes.valves.attachments import register_attachment_routes

register_export_routes(valves)
register_attachment_routes(valves)
