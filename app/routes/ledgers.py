from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    jsonify,
    abort,
)
from flask_login import login_required, current_user
from app.models import db, Ledger, ApprovalLog, Setting, ValveAttachment
from app.devices.valve_helper import VALVE_TYPES, get_valve_model, get_valve_by_id, get_valve_ledger_type, has_duplicate_tag, get_all_valve_models, count_valves_by_status, query_valves
from app.devices import DeviceTypeRegistry
from app.routes.valves.permissions import (
    can_edit_ledger,
    can_delete_ledger,
    can_create_valve,
    can_edit_valve,
    can_delete_valve,
    can_view_ledger,
    can_view_valve,
)
from app.utils.navigation import (
    get_from_param,
    get_context,
    get_back_url,
    redirect_to_list,
)
from sqlalchemy import or_
from datetime import datetime
import json

ledgers = Blueprint("ledgers", __name__)


def update_ledger_status(ledger):
    config = DeviceTypeRegistry.get(ledger.类型)
    if not config or not config.model_class:
        return
    model = config.model_class
    total = model.query.filter_by(ledger_id=ledger.id).count()
    if total == 0:
        return
    approved = model.query.filter_by(ledger_id=ledger.id, status="approved").count()
    pending = model.query.filter_by(ledger_id=ledger.id, status="pending").count()
    rejected = model.query.filter_by(ledger_id=ledger.id, status="rejected").count()
    draft = model.query.filter_by(ledger_id=ledger.id, status="draft").count()
    if pending > 0:
        ledger.status = "pending"
    elif rejected > 0:
        ledger.status = "rejected"
    elif draft > 0:
        ledger.status = "draft"
    elif approved == total:
        ledger.status = "approved"
        ledger.approved_at = datetime.utcnow()
        ledger.approved_snapshot_status = "approved"
        ledger.approved_snapshot_at = datetime.utcnow()




@ledgers.route("/ledgers")
@login_required
def list():
    query = Ledger.query

    search = request.args.get("search")
    if search:
        query = query.filter(Ledger.名称.contains(search))

    status = request.args.get("status")
    if status:
        query = query.filter(Ledger.approved_snapshot_status == status)
    else:
        query = query.filter(Ledger.approved_snapshot_status == "approved")

    ledgers_list = query.order_by(Ledger.created_at.desc()).all()

    for ledger in ledgers_list:
        config = DeviceTypeRegistry.get(ledger.类型)
        if config and config.model_class:
            model = config.model_class
            total_q = model.query.filter_by(ledger_id=ledger.id)
            ledger.valve_count = total_q.count()
            ledger.pending_count = total_q.filter_by(status="pending").count()
            ledger.rejected_count = total_q.filter_by(status="rejected").count()
            ledger.approved_count = total_q.filter_by(status="approved").count()
            ledger.draft_count = total_q.filter_by(status="draft").count()
        else:
            ledger.valve_count = ledger.pending_count = ledger.rejected_count = ledger.approved_count = ledger.draft_count = 0

        if ledger.approved_snapshot_status:
            ledger.display_status = ledger.approved_snapshot_status
        else:
            ledger.display_status = ledger.status

    return render_template("ledgers/list.html", ledgers=ledgers_list)


@ledgers.route("/ledger/new", methods=["GET", "POST"])
@login_required
def new():
    from_param = request.args.get("from", "all")
    all_types = DeviceTypeRegistry.all()

    if request.method == "POST":
        名称 = request.form.get("名称")
        描述 = request.form.get("描述")
        type_code = request.form.get("类型")

        if not 名称:
            flash("请填写台账合集名称")
            return render_template("ledgers/create.html", all_types=all_types, from_param=from_param)

        if not type_code:
            flash("请选择设备类型")
            return render_template("ledgers/create.html", all_types=all_types, from_param=from_param)

        ledger = Ledger()
        ledger.名称 = 名称
        ledger.描述 = 描述
        ledger.类型 = type_code
        ledger.created_by = current_user.id
        ledger.status = "draft"

        db.session.add(ledger)
        db.session.commit()

        flash("台账合集创建成功")
        return redirect(url_for("ledgers.detail", id=ledger.id, from_param=from_param))

    return render_template("ledgers/create.html", all_types=all_types, from_param=from_param)


@ledgers.route("/ledger/<int:id>", methods=["GET", "POST"])
@login_required
def detail(id):
    from_param = request.args.get("from", "all")
    ledger = Ledger.query.get_or_404(id)

    if not can_view_ledger(ledger):
        flash("无权访问")
        return redirect(url_for("ledgers.list"))

    is_owner = ledger.created_by == current_user.id or current_user.role in [
        "leader",
        "admin",
    ]

    if from_param != "mine" and not is_owner:
        flash("无权访问")
        return redirect(url_for("ledgers.list"))

    config = DeviceTypeRegistry.get(ledger.类型)
    if not config or not config.model_class:
        abort(404)
    model = config.model_class

    ledger.valve_count = model.query.filter_by(ledger_id=id).count()
    ledger.pending_count = model.query.filter_by(ledger_id=id, status="pending").count()
    ledger.rejected_count = model.query.filter_by(
        ledger_id=id, status="rejected"
    ).count()
    ledger.approved_count = model.query.filter_by(
        ledger_id=id, status="approved"
    ).count()
    ledger.draft_count = model.query.filter_by(ledger_id=id, status="draft").count()

    ledger.is_owner = is_owner

    if from_param == "mine" or ledger.approved_snapshot_status == "approved":
        if ledger.pending_count > 0:
            ledger.display_status = "pending"
        elif ledger.rejected_count > 0:
            ledger.display_status = "rejected"
        elif ledger.approved_count > 0 and ledger.approved_count == ledger.valve_count:
            ledger.display_status = "approved"
        elif ledger.valve_count > 0:
            ledger.display_status = "draft"
        else:
            ledger.display_status = "draft"
    else:
        ledger.display_status = ledger.approved_snapshot_status or "draft"

    db.session.commit()

    if request.method == "POST":
        if not can_edit_ledger(ledger):
            flash("无权操作")
            return redirect(url_for("ledgers.detail", id=id, **{"from": from_param}))

        action = request.form.get("action")
        valve_ids = request.form.getlist("valve_ids")

        if action == "submit":
            draft_devices = model.query.filter_by(
                ledger_id=ledger.id, status="draft"
            ).all()
            for device in draft_devices:
                device.status = "pending"
                log = ApprovalLog(
                    ledger_id=ledger.id,
                    device_type=ledger.类型,
                    device_id=device.id,
                    action="submit",
                    user_id=current_user.id,
                )
                db.session.add(log)
            db.session.commit()
            update_ledger_status(ledger)
            db.session.commit()
            flash(f"已提交 {len(draft_devices)} 项台账内容审批")
            return redirect(url_for("ledgers.detail", id=id, **{"from": from_param}))

        elif action == "batch_approve":
            if current_user.role not in ["leader", "admin"]:
                flash("需要领导权限")
                return redirect(
                    url_for("ledgers.detail", id=id, **{"from": from_param})
                )

            approved_count = 0
            for valve_id in valve_ids:
                device = model.query.get(int(valve_id))
                if device and device.ledger_id == ledger.id and device.status == "pending":
                    device.status = "approved"
                    device.approved_by = current_user.id
                    device.approved_at = datetime.utcnow()
                    log = ApprovalLog(
                        ledger_id=ledger.id,
                        device_type=ledger.类型,
                        device_id=device.id,
                        action="approve",
                        user_id=current_user.id,
                        comment=request.form.get("comment", ""),
                    )
                    db.session.add(log)
                    approved_count += 1
            update_ledger_status(ledger)
            db.session.commit()
            flash(f"已审批 {approved_count} 项台账内容")
            return redirect(url_for("ledgers.detail", id=id, **{"from": from_param}))

        elif action == "batch_reject":
            if current_user.role not in ["leader", "admin"]:
                flash("需要领导权限")
                return redirect(
                    url_for("ledgers.detail", id=id, **{"from": from_param})
                )

            rejected_count = 0
            for valve_id in valve_ids:
                device = model.query.get(int(valve_id))
                if device and device.ledger_id == ledger.id and device.status == "pending":
                    device.status = "rejected"
                    log = ApprovalLog(
                        ledger_id=ledger.id,
                        device_type=ledger.类型,
                        device_id=device.id,
                        action="reject",
                        user_id=current_user.id,
                        comment=request.form.get("comment", ""),
                    )
                    db.session.add(log)
                    rejected_count += 1
            db.session.commit()
            flash(f"已驳回 {rejected_count} 项台账内容")
            return redirect(url_for("ledgers.detail", id=id, **{"from": from_param}))

    query = model.query.filter_by(ledger_id=id)

    status_filter = request.args.get("status")

    if from_param != "mine" and not status_filter:
        if ledger.approved_snapshot_at:
            query = query.filter(
                model.status == "approved",
                model.approved_at <= ledger.approved_snapshot_at,
            )
        else:
            query = query.filter(model.status == "approved")

    search = request.args.get("search")
    if search:
        search_conditions = []
        for column in model.__table__.columns:
            if column.name not in [
                "id",
                "ledger_id",
                "created_by",
                "approved_by",
                "approved_at",
                "created_at",
                "updated_at",
                "status",
            ]:
                col = getattr(model, column.name)
                search_conditions.append(col.contains(search))
        if search_conditions:
            query = query.filter(or_(*search_conditions))

    status = request.args.get("status")
    if status:
        query = query.filter(model.status == status)

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    filterable_fields = [
        ("位号", "位号"),
        ("名称", "名称"),
        ("装置名称", "装置名称"),
        ("设备等级", "设备等级"),
        ("型号规格", "型号规格"),
        ("生产厂家", "生产厂家"),
        ("安装位置及用途", "安装位置及用途"),
        ("设备编号", "设备编号"),
        ("是否联锁", "是否联锁"),
    ]

    filter_options = {}
    for label, field in filterable_fields:
        if hasattr(model, field):
            values = (
                db.session.query(getattr(model, field))
                .distinct()
                .filter(
                    getattr(model, field).isnot(None),
                    getattr(model, field) != "",
                    model.ledger_id == id,
                )
                .all()
            )
            filter_options[field] = sorted([v[0] for v in values if v[0]], key=str)

    active_filters = {}
    for label, field in filterable_fields:
        values = request.args.getlist(field)
        if values and hasattr(model, field):
            field_filter = getattr(model, field).in_(values)
            query = query.filter(field_filter)
            active_filters[field] = values

    pagination = query.order_by(model.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    valves_list = pagination.items

    装置列表 = (
        db.session.query(model.装置名称)
        .distinct()
        .filter(model.装置名称.isnot(None), model.ledger_id == id)
        .all()
    )
    装置列表 = [r[0] for r in 装置列表 if r[0]]

    return render_template(
        "valves/list.html",
        ledger=ledger,
        valves=valves_list,
        pagination=pagination,
        装置列表=装置列表,
        active_filters=active_filters,
        filter_options=filter_options,
        from_param=from_param,
    )


@ledgers.route("/ledger/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit(id):
    from_param = request.args.get("from", "all")
    ledger = Ledger.query.get_or_404(id)

    if not can_edit_ledger(ledger):
        flash("无权编辑")
        return redirect(get_back_url(from_param))

    if request.method == "POST":
        ledger.名称 = request.form.get("名称")
        ledger.描述 = request.form.get("描述")
        db.session.commit()
        flash("更新成功")
        return redirect(url_for("ledgers.detail", id=id, **{"from": from_param}))

    return render_template("ledgers/form.html", ledger=ledger)


@ledgers.route("/ledger/<int:id>/delete", methods=["POST"])
@login_required
def delete(id):
    from_param = request.args.get("from", "all")
    ledger = Ledger.query.get_or_404(id)

    if not can_edit_ledger(ledger):
        flash("无权删除")
        return redirect(get_back_url(from_param))

    config = DeviceTypeRegistry.get(ledger.类型)
    if not config or not config.model_class:
        flash("类型配置错误")
        return redirect(get_back_url(from_param))
    model = config.model_class
    device_type = config.code

    pending_count = model.query.filter_by(ledger_id=id, status="pending").count()
    if pending_count > 0:
        flash(f"当前有 {pending_count} 条待审批记录，无法删除")
        return redirect(get_back_url(from_param))

    valve_ids = [
        v[0] for v in model.query.with_entities(model.id).filter_by(ledger_id=id).all()
    ]
    if valve_ids:
        ValveAttachment.query.filter(
            ValveAttachment.device_type == device_type,
            ValveAttachment.device_id.in_(valve_ids),
        ).delete(synchronize_session=False)

    model.query.filter_by(ledger_id=id).delete()
    db.session.delete(ledger)
    db.session.commit()
    flash("删除成功")
    return redirect(get_back_url(from_param))


@ledgers.route("/ledger/<int:id>/submit", methods=["POST"])
@login_required
def submit(id):
    from_param = request.args.get("from", "all")
    ledger = Ledger.query.get_or_404(id)

    if not can_edit_ledger(ledger):
        flash("无权操作")
        return redirect(get_back_url(from_param))

    config = DeviceTypeRegistry.get(ledger.类型)
    if not config or not config.model_class:
        flash("类型配置错误")
        return redirect(get_back_url(from_param))
    model = config.model_class

    device_ids = request.form.getlist("valve_ids")

    if device_ids:
        submit_devices = model.query.filter(
            model.id.in_(device_ids), model.ledger_id == id, model.status == "draft"
        ).all()
    else:
        submit_devices = model.query.filter_by(ledger_id=id, status="draft").all()

    if not submit_devices:
        flash("没有可提交的台账")
        return redirect(url_for("ledgers.detail", id=id, **{"from": from_param}))

    for device in submit_devices:
        device.status = "pending"
        log = ApprovalLog(
            ledger_id=ledger.id,
            device_type=ledger.类型,
            device_id=device.id,
            action="submit",
            user_id=current_user.id,
        )
        db.session.add(log)

    db.session.commit()
    update_ledger_status(ledger)
    db.session.commit()

    flash(f"已提交 {len(submit_devices)} 项台账内容审批")
    return redirect(get_back_url(from_param))


@ledgers.route("/ledger/<int:id>/approve", methods=["POST"])
@login_required
def approve(id):
    from_param = request.args.get("from", "all")
    if current_user.role not in ["leader", "admin"]:
        flash("需要领导权限")
        return redirect(get_back_url(from_param))

    ledger = Ledger.query.get_or_404(id)

    config = DeviceTypeRegistry.get(ledger.类型)
    if config and config.model_class:
        model = config.model_class
        pending_devices = model.query.filter_by(ledger_id=id, status="pending").all()
        for device in pending_devices:
            device.status = "approved"
            device.approved_by = current_user.id
            device.approved_at = datetime.utcnow()
            log = ApprovalLog(
                ledger_id=ledger.id,
                device_type=ledger.类型,
                device_id=device.id,
                action="approve",
                user_id=current_user.id,
                comment=request.form.get("comment", ""),
            )
            db.session.add(log)

        update_ledger_status(ledger)
        db.session.commit()

        flash(f"已审批通过，共 {len(pending_devices)} 项台账内容")
        return redirect(get_back_url(from_param))

    flash("类型配置错误")
    return redirect(get_back_url(from_param))


@ledgers.route("/ledger/<int:id>/reject", methods=["POST"])
@login_required
def reject(id):
    from_param = request.args.get("from", "all")
    if current_user.role not in ["leader", "admin"]:
        flash("需要领导权限")
        return redirect(get_back_url(from_param))

    ledger = Ledger.query.get_or_404(id)

    config = DeviceTypeRegistry.get(ledger.类型)
    if config and config.model_class:
        model = config.model_class
        pending_devices = model.query.filter_by(ledger_id=id, status="pending").all()
        for device in pending_devices:
            device.status = "rejected"
            log = ApprovalLog(
                ledger_id=ledger.id,
                device_type=ledger.类型,
                device_id=device.id,
                action="reject",
                user_id=current_user.id,
                comment=request.form.get("comment", ""),
            )
            db.session.add(log)
        db.session.commit()
        flash(f"已驳回，共 {len(pending_devices)} 项台账内容")
        return redirect(url_for("ledgers.detail", id=id, **{"from": from_param}))

    flash("类型配置错误")
    return redirect(url_for("ledgers.detail", id=id, **{"from": from_param}))


@ledgers.route("/ledger/<int:id>/valve/new", methods=["GET", "POST"])
@login_required
def new_valve(id):
    from_param = request.args.get("from", "all")
    ledger = Ledger.query.get_or_404(id)
    model = get_valve_model(ledger)
    if not model:
        flash("不支持的设备类型")
        return redirect(url_for("ledgers.detail", id=id, **{"from": from_param}))

    if not can_create_valve(ledger):
        flash("无权在此台账中创建阀门")
        return redirect(url_for("ledgers.detail", id=id, **{"from": from_param}))

    if request.method == "POST":
        位号 = request.form.get("位号")
        if 位号 and has_duplicate_tag(位号):
            flash("位号已存在，请使用其他位号")
            return redirect(
                url_for("ledgers.new_valve", id=id, **{"from": from_param})
            )

        valve = model()
        for key in request.form:
            if key == "attachments":
                continue
            if hasattr(valve, key):
                setattr(valve, key, request.form.get(key))

        valve.ledger_id = id
        valve.created_by = current_user.id
        valve.status = "draft"

        try:
            db.session.add(valve)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash(f"保存失败: {str(e)}")
            return redirect(url_for("ledgers.new_valve", id=id, **{"from": from_param}))

        attachments_json = request.form.get("attachments")
        if attachments_json:
            try:
                attachments = json.loads(attachments_json)
                for att in attachments:
                    att_type = att.get("attachment_type") or att.get("type")
                    if att_type:
                        attachment = ValveAttachment(
                            device_type=ledger.类型,
                            device_id=valve.id,
                            type=att_type,
                            名称=att.get("name") or att.get("名称", ""),
                            设备等级=att.get("device_grade") or att.get("设备等级", ""),
                            型号规格=att.get("model") or att.get("型号规格", ""),
                            生产厂家=att.get("manufacturer") or att.get("生产厂家", ""),
                        )
                        db.session.add(attachment)
                db.session.commit()
            except json.JSONDecodeError:
                pass

        config = DeviceTypeRegistry.get(ledger.类型)
        if config and config.model_class:
            ledger.valve_count = config.model_class.query.filter_by(ledger_id=id).count()
        db.session.commit()
        flash("添加成功，内容已保存为草稿，请在台账集合详情页提交审批")
        return redirect(url_for("ledgers.detail", id=id, **{"from": from_param}))

    return render_template(
        "valves/form.html", valve=None, ledger=ledger, from_param=from_param
    )


@ledgers.route("/ledger/<int:ledger_id>/valve/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_valve(ledger_id, id):
    from_param = request.args.get("from", "all")
    ledger = Ledger.query.get_or_404(ledger_id)
    model = get_valve_model(ledger)
    if not model:
        abort(404)
    valve = model.query.get_or_404(id)

    if not can_edit_valve(valve):
        flash("无权编辑")
        return redirect(url_for("ledgers.detail", id=ledger_id, **{"from": from_param}))

    if valve.status not in ["draft", "rejected", "approved"]:
        flash("当前状态无法编辑")
        return redirect(url_for("ledgers.detail", id=ledger_id, **{"from": from_param}))

    if request.method == "POST":
        for key in request.form:
            if key == "attachments":
                continue
            if hasattr(valve, key):
                setattr(valve, key, request.form.get(key))

        if valve.status == "approved":
            valve.status = "draft"
            update_ledger_status(ledger)
        elif valve.status == "rejected":
            valve.status = "draft"
            update_ledger_status(ledger)

        device_type = ledger.类型
        attachments_json = request.form.get("attachments")
        if attachments_json:
            try:
                attachments = json.loads(attachments_json)
                existing_attachments = ValveAttachment.query.filter_by(
                    device_type=device_type, device_id=valve.id
                ).all()
                existing_ids = {att.id for att in existing_attachments}
                submitted_ids = set()
                for att in attachments:
                    att_type = att.get("attachment_type") or att.get("type")
                    if not att_type:
                        continue
                    att_id = att.get("id")
                    if att_id:
                        attachment = ValveAttachment.query.filter(
                            ValveAttachment.id == att_id,
                            ValveAttachment.device_id == valve.id,
                            ValveAttachment.device_type == device_type,
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
                        attachment = ValveAttachment(
                            device_type=device_type,
                            device_id=valve.id,
                            type=att_type,
                            名称=att.get("name") or att.get("名称", ""),
                            设备等级=att.get("device_grade") or att.get("设备等级", ""),
                            型号规格=att.get("model") or att.get("型号规格", ""),
                            生产厂家=att.get("manufacturer") or att.get("生产厂家", ""),
                        )
                        db.session.add(attachment)
                for att_id in existing_ids - submitted_ids:
                    attachment = ValveAttachment.query.filter(
                        ValveAttachment.id == att_id,
                        ValveAttachment.device_id == valve.id,
                        ValveAttachment.device_type == device_type,
                    ).first()
                    if attachment:
                        db.session.delete(attachment)
            except json.JSONDecodeError:
                pass

        db.session.commit()
        flash("更新成功")
        return redirect(url_for("ledgers.detail", id=ledger_id, **{"from": from_param}))

    return render_template(
        "valves/form.html", valve=valve, ledger=ledger, from_param=from_param
    )


@ledgers.route("/ledger/<int:ledger_id>/valve/<int:id>")
@login_required
def valve_detail(ledger_id, id):
    from_param = request.args.get("from", "all")
    ledger = Ledger.query.get_or_404(ledger_id)

    if ledger.类型 not in VALVE_TYPES:
        return redirect(url_for("devices.detail", type_code=ledger.类型, id=id, **{"from": from_param}))

    model = get_valve_model(ledger)
    if not model:
        abort(404)
    valve = model.query.get(id)
    if not valve:
        abort(404)
    return render_template(
        "valves/detail.html", valve=valve, ledger_id=ledger_id, from_param=from_param
    )


@ledgers.route("/ledger/<int:ledger_id>/valve/delete/<int:id>", methods=["POST"])
@login_required
def delete_valve(ledger_id, id):
    from_param = request.args.get("from", "all")
    ledger = Ledger.query.get_or_404(ledger_id)
    valve = get_valve_by_id(id)
    if not valve or valve.ledger_id != ledger_id:
        abort(404)

    if not can_delete_valve(valve):
        flash("无权删除")
        return redirect(url_for("ledgers.detail", id=ledger_id, **{"from": from_param}))

    if valve.status not in ["draft", "rejected", "approved"]:
        flash("当前状态无法删除")
        return redirect(url_for("ledgers.detail", id=ledger_id, **{"from": from_param}))

    device_type = get_valve_ledger_type(valve)
    ValveAttachment.query.filter_by(
        device_type=device_type, device_id=valve.id
    ).delete()
    db.session.delete(valve)

    config = DeviceTypeRegistry.get(ledger.类型)
    if config and config.model_class:
        model = config.model_class
        ledger.valve_count = model.query.filter_by(ledger_id=ledger_id).count()
        ledger.pending_count = model.query.filter_by(
            ledger_id=ledger_id, status="pending"
        ).count()

    db.session.commit()
    flash("删除成功")
    return redirect(url_for("ledgers.detail", id=ledger_id, **{"from": from_param}))


@ledgers.route("/ledger/<int:id>/valve/batch-save", methods=["POST"])
@login_required
def batch_save_valve(id):
    """批量保存台账（JSON 格式）"""
    ledger = Ledger.query.get_or_404(id)
    model = get_valve_model(ledger)
    if not model:
        return jsonify({"success": False, "message": "不支持的设备类型"}), 400

    if not can_edit_ledger(ledger):
        return jsonify({"success": False, "message": "无权操作"}), 403

    pending_count = model.query.filter_by(ledger_id=id, status="pending").count()
    if pending_count > 0:
        return jsonify({"success": False, "message": "当前有待审批记录，无法编辑"}), 400

    data = request.get_json()
    if not data or not isinstance(data, list):
        return jsonify({"success": False, "message": "无效数据格式"})

    saved_ids = []
    errors = []

    approved_to_draft = False

    for item in data:
        valve_id = item.get("id")
        form_data = item.get("data", {})

        if valve_id:
            valve = model.query.get(valve_id)
            if not valve or valve.ledger_id != id:
                errors.append({"id": valve_id, "error": "台账不存在"})
                continue

            if valve.status not in ["draft", "rejected", "approved"]:
                errors.append({"id": valve_id, "error": "当前状态无法编辑"})
                continue

            if valve.status == "approved":
                valve.status = "draft"
                approved_to_draft = True
        else:
            valve = model()
            valve.ledger_id = id
            valve.created_by = current_user.id
            valve.status = "draft"
            db.session.add(valve)

        for key, value in form_data.items():
            if key == "ledger_id":
                continue
            if hasattr(valve, key):
                setattr(valve, key, value)

        db.session.flush()

        if valve.id:
            saved_ids.append(valve.id)

    try:
        db.session.commit()

        if approved_to_draft:
            update_ledger_status(ledger)
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

    config = DeviceTypeRegistry.get(ledger.类型)
    if config and config.model_class:
        ledger.valve_count = config.model_class.query.filter_by(ledger_id=id).count()
    db.session.commit()

    return jsonify({"success": True, "saved_ids": saved_ids, "errors": errors})


@ledgers.route("/ledger/<int:id>/valve/batch-delete", methods=["POST"])
@login_required
def batch_delete_valve(id):
    from_param = request.args.get("from", "all")
    ledger = Ledger.query.get_or_404(id)
    model = get_valve_model(ledger)
    if not model:
        flash("不支持的设备类型")
        return redirect(url_for("ledgers.detail", id=id, **{"from": from_param}))

    valve_ids = request.form.getlist("ids")
    if not valve_ids:
        flash("请选择要删除的台账")
        return redirect(url_for("ledgers.detail", id=id, **{"from": from_param}))

    valves_to_delete = []
    unauthorized_count = 0
    pending_count = 0

    for valve_id in valve_ids:
        valve = model.query.filter_by(id=valve_id, ledger_id=id).first()
        if not valve:
            continue
        if not can_delete_valve(valve):
            unauthorized_count += 1
            continue
        if valve.status == "pending":
            pending_count += 1
            continue
        valves_to_delete.append(valve.id)

    if unauthorized_count > 0:
        flash(f"有 {unauthorized_count} 项台账无权删除")
    if pending_count > 0:
        flash(f"有 {pending_count} 项待审批记录无法删除")

    if valves_to_delete:
        config = DeviceTypeRegistry.get(ledger.类型)
        device_type = config.code if config else None
        if device_type:
            ValveAttachment.query.filter(
                ValveAttachment.device_type == device_type,
                ValveAttachment.device_id.in_(valves_to_delete),
            ).delete(synchronize_session=False)

        deleted_count = model.query.filter(
            model.id.in_(valves_to_delete),
        ).delete(synchronize_session=False)

        if config and config.model_class:
            ledger.valve_count = config.model_class.query.filter_by(ledger_id=id).count()
        db.session.commit()
        flash(f"成功删除 {deleted_count} 项台账")
    elif unauthorized_count == 0 and pending_count == 0:
        flash("没有可删除的台账")

    return redirect(url_for("ledgers.detail", id=id, **{"from": from_param}))


@ledgers.route("/ledgers/batch-delete", methods=["POST"])
@login_required
def batch_delete_ledgers():
    """批量删除台账合集"""
    ledger_ids = request.form.getlist("ledger_ids")
    if not ledger_ids:
        flash("请选择要删除的合集")
        return redirect(url_for("valves.my_ledgers"))

    deleted_count = 0
    failed_ledgers = []

    for ledger_id in ledger_ids:
        ledger = Ledger.query.get(int(ledger_id))
        if not ledger:
            continue

        if not can_edit_ledger(ledger):
            failed_ledgers.append(ledger.名称)
            continue

        config = DeviceTypeRegistry.get(ledger.类型)
        if not config or not config.model_class:
            failed_ledgers.append(f"{ledger.名称}(类型配置错误)")
            continue
        model = config.model_class

        pending_count = model.query.filter_by(
            ledger_id=ledger.id, status="pending"
        ).count()
        if pending_count > 0:
            failed_ledgers.append(f"{ledger.名称}(有待审批记录)")
            continue

        device_type = config.code
        valve_ids = [
            v[0] for v in model.query.with_entities(model.id).filter_by(ledger_id=ledger.id).all()
        ]
        if valve_ids:
            ValveAttachment.query.filter(
                ValveAttachment.device_type == device_type,
                ValveAttachment.device_id.in_(valve_ids),
            ).delete(synchronize_session=False)

        model.query.filter_by(ledger_id=ledger.id).delete()
        db.session.delete(ledger)
        deleted_count += 1

    db.session.commit()

    if failed_ledgers:
        flash(f"部分合集删除失败: {', '.join(failed_ledgers)}")
    if deleted_count > 0:
        flash(f"成功删除 {deleted_count} 个合集")

    return redirect(url_for("valves.my_ledgers"))


@ledgers.route("/ledgers/batch-submit", methods=["POST"])
@login_required
def batch_submit_ledgers():
    """批量提交合集中的草稿内容审批"""
    ledger_ids = request.form.getlist("ledger_ids")
    if not ledger_ids:
        flash("请选择要提交的合集")
        return redirect(url_for("valves.my_ledgers"))

    submitted_count = 0
    failed_ledgers = []

    for ledger_id in ledger_ids:
        ledger = Ledger.query.get(int(ledger_id))
        if not ledger:
            continue

        if not can_edit_ledger(ledger):
            failed_ledgers.append(ledger.名称)
            continue

        config = DeviceTypeRegistry.get(ledger.类型)
        if not config or not config.model_class:
            failed_ledgers.append(f"{ledger.名称}(类型配置错误)")
            continue
        model = config.model_class
        draft_devices = model.query.filter_by(ledger_id=ledger.id, status="draft").all()
        for device in draft_devices:
            device.status = "pending"
            log = ApprovalLog(
                ledger_id=ledger.id,
                device_type=ledger.类型,
                device_id=device.id,
                action="submit",
                user_id=current_user.id,
            )
            db.session.add(log)

        if not draft_devices:
            continue

        update_ledger_status(ledger)
        submitted_count += 1

    db.session.commit()

    if failed_ledgers:
        flash(f"部分合集提交失败: {', '.join(failed_ledgers)}")
    if submitted_count > 0:
        flash(f"成功提交 {submitted_count} 个合集的草稿内容审批")

    return redirect(url_for("valves.my_ledgers"))
