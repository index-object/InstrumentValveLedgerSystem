from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, make_response, abort
from flask_login import login_required, current_user
from app.models import db, Ledger, ApprovalLog
from app.devices import DeviceTypeRegistry
from datetime import datetime
from io import BytesIO
# 延迟导入 pandas（避免在应用启动时立即加载可能含有本机指令的二进制扩展）

devices_bp = Blueprint("devices", __name__, url_prefix="/device")


def get_config_or_404(type_code):
    config = DeviceTypeRegistry.get(type_code)
    if not config or config.code == "valve":
        abort(404)
    return config


@devices_bp.route("/<type_code>")
@login_required
def list(type_code):
    config = get_config_or_404(type_code)
    model = config.model_class

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = model.query

    if current_user.role == "employee":
        query = query.filter(model.created_by == current_user.id)

    if status_filter:
        query = query.filter(model.status == status_filter)

    if search:
        keyword = f"%{search}%"
        filters = []
        if hasattr(model, "位号"):
            filters.append(model.位号.like(keyword))
        if hasattr(model, "设备名称"):
            filters.append(model.设备名称.like(keyword))
        if hasattr(model, "装置名称"):
            filters.append(model.装置名称.like(keyword))
        if hasattr(model, "名称"):
            filters.append(model.名称.like(keyword))
        if filters:
            from sqlalchemy import or_
            query = query.filter(or_(*filters))

    filterable_fields = config.get_fields_flat()
    filter_options = {}
    for field in filterable_fields:
        if hasattr(model, field):
            values = (
                db.session.query(getattr(model, field))
                .distinct()
                .filter(
                    getattr(model, field).isnot(None),
                    getattr(model, field) != "",
                )
                .all()
            )
            filter_options[field] = sorted([v[0] for v in values if v[0]], key=str)

    active_filters = {}
    for field in filterable_fields:
        values = request.args.getlist(field)
        if values and hasattr(model, field):
            field_filter = getattr(model, field).in_(values)
            query = query.filter(field_filter)
            active_filters[field] = values

    query = query.order_by(model.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    devices = pagination.items

    return render_template(
        "devices/list.html",
        config=config,
        devices=devices,
        pagination=pagination,
        search=search,
        status_filter=status_filter,
        filter_options=filter_options,
        active_filters=active_filters,
    )


@devices_bp.route("/<type_code>/<int:id>")
@login_required
def detail(type_code, id):
    config = get_config_or_404(type_code)
    device = config.model_class.query.get_or_404(id)
    from_param = request.args.get("from", "")

    return render_template(
        "devices/detail.html",
        config=config,
        device=device,
        from_param=from_param,
    )


@devices_bp.route("/<type_code>/new", methods=["GET", "POST"])
@login_required
def new(type_code):
    config = get_config_or_404(type_code)
    from_param = request.args.get("from", request.args.get("from_param", ""))
    ledger_id = request.args.get("ledger_id", type=int)
    ledger = None
    if ledger_id:
        ledger = Ledger.query.get(ledger_id)

    if request.method == "POST":
        device = config.model_class()
        device.created_by = current_user.id
        device.status = "draft"

        if ledger_id:
            device.ledger_id = ledger_id

        for key, value in request.form.items():
            if hasattr(device, key):
                setattr(device, key, value)

        db.session.add(device)
        db.session.commit()

        flash("保存成功，内容已保存为草稿")
        if ledger_id:
            return redirect(url_for("ledgers.detail", id=ledger_id, **{"from": from_param}))
        return redirect(url_for("devices.list", type_code=type_code))

    return render_template(
        "devices/form.html",
        config=config,
        device=None,
        ledger=ledger,
        from_param=from_param,
    )


@devices_bp.route("/<type_code>/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit(type_code, id):
    config = get_config_or_404(type_code)
    device = config.model_class.query.get_or_404(id)
    from_param = request.args.get("from", "")

    if current_user.role == "employee" and device.created_by != current_user.id:
        flash("无权编辑")
        return redirect(url_for("devices.detail", type_code=type_code, id=id, **{"from": from_param}))

    if device.status not in ["draft", "rejected"]:
        flash("当前状态无法编辑")
        return redirect(url_for("devices.detail", type_code=type_code, id=id, **{"from": from_param}))

    if request.method == "POST":
        for key, value in request.form.items():
            if hasattr(device, key):
                setattr(device, key, value)
        if device.status == "rejected":
            device.status = "draft"
        device.updated_at = datetime.utcnow()
        db.session.commit()
        flash("保存成功")
        return redirect(url_for("devices.detail", type_code=type_code, id=id, **{"from": from_param}))

    return render_template(
        "devices/form.html",
        config=config,
        device=device,
        from_param=from_param,
    )


@devices_bp.route("/<type_code>/<int:id>/delete", methods=["POST"])
@login_required
def delete(type_code, id):
    config = get_config_or_404(type_code)
    device = config.model_class.query.get_or_404(id)
    ledger_id = device.ledger_id

    db.session.delete(device)
    db.session.commit()
    flash("删除成功")

    if ledger_id:
        return redirect(url_for("ledgers.detail", id=ledger_id))
    return redirect(url_for("devices.list", type_code=type_code))


@devices_bp.route("/<type_code>/<int:id>/submit", methods=["POST"])
@login_required
def submit(type_code, id):
    config = get_config_or_404(type_code)
    device = config.model_class.query.get_or_404(id)

    if current_user.role == "employee" and device.created_by != current_user.id:
        flash("无权提交")
        return redirect(url_for("devices.detail", type_code=type_code, id=id))

    if device.status != "draft":
        flash("仅草稿状态可提交")
        return redirect(url_for("devices.detail", type_code=type_code, id=id))

    device.status = "pending"
    log = ApprovalLog(
        valve_id=None,
        device_type=type_code,
        device_id=device.id,
        action="submit",
        user_id=current_user.id,
    )
    db.session.add(log)
    db.session.commit()
    flash("提交审批成功")
    return redirect(url_for("devices.detail", type_code=type_code, id=id))


@devices_bp.route("/<type_code>/<int:id>/approve", methods=["POST"])
@login_required
def approve(type_code, id):
    if current_user.role not in ["leader", "admin"]:
        flash("需要领导权限")
        return redirect(url_for("devices.detail", type_code=type_code, id=id))

    config = get_config_or_404(type_code)
    device = config.model_class.query.get_or_404(id)

    if device.status != "pending":
        flash("仅待审批状态可审批")
        return redirect(url_for("devices.detail", type_code=type_code, id=id))

    device.status = "approved"
    device.approved_by = current_user.id
    device.approved_at = datetime.utcnow()
    log = ApprovalLog(
        valve_id=None,
        device_type=type_code,
        device_id=device.id,
        action="approve",
        user_id=current_user.id,
        comment=request.form.get("comment", ""),
    )
    db.session.add(log)
    db.session.commit()
    flash("审批通过")
    return redirect(url_for("devices.detail", type_code=type_code, id=id))


@devices_bp.route("/<type_code>/<int:id>/reject", methods=["POST"])
@login_required
def reject(type_code, id):
    if current_user.role not in ["leader", "admin"]:
        flash("需要领导权限")
        return redirect(url_for("devices.detail", type_code=type_code, id=id))

    config = get_config_or_404(type_code)
    device = config.model_class.query.get_or_404(id)

    if device.status != "pending":
        flash("仅待审批状态可驳回")
        return redirect(url_for("devices.detail", type_code=type_code, id=id))

    device.status = "rejected"
    log = ApprovalLog(
        valve_id=None,
        device_type=type_code,
        device_id=device.id,
        action="reject",
        user_id=current_user.id,
        comment=request.form.get("comment", ""),
    )
    db.session.add(log)
    db.session.commit()
    flash("已驳回")
    return redirect(url_for("devices.detail", type_code=type_code, id=id))


@devices_bp.route("/<type_code>/export")
@login_required
def export(type_code):
    config = get_config_or_404(type_code)
    model = config.model_class
    fields = config.get_fields_flat()

    ids = request.args.getlist("ids")
    if ids:
        records = model.query.filter(model.id.in_(ids)).all()
    else:
        records = model.query.filter_by(status="approved").all()

    data = []
    for r in records:
        row = {}
        for f in fields:
            row[f] = getattr(r, f, "") or ""
        data.append(row)

    import pandas as pd
    df = pd.DataFrame(data)
    buffer = BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)

    output = make_response(buffer.read())
    output.headers["Content-Disposition"] = f"attachment; filename={config.code}.xlsx"
    output.headers["Content-Type"] = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    return output


@devices_bp.route("/<type_code>/check-tag")
@login_required
def check_tag(type_code):
    config = get_config_or_404(type_code)
    model = config.model_class

    if not hasattr(model, "位号"):
        return jsonify({"valid": True})

    tag = request.args.get("位号")
    if not tag:
        return jsonify({"valid": True})

    exclude_id = request.args.get("exclude_id", type=int)
    query = model.query.filter(model.位号 == tag, model.status != "draft")
    if exclude_id:
        query = query.filter(model.id != exclude_id)

    exists = query.first() is not None
    return jsonify({"valid": not exists, "message": "位号已存在" if exists else None})


@devices_bp.route("/<type_code>/batch-delete", methods=["POST"])
@login_required
def batch_delete(type_code):
    config = get_config_or_404(type_code)
    model = config.model_class
    ids = request.form.getlist("ids")
    if not ids:
        flash("请选择要删除的记录")
        return redirect(url_for("devices.list", type_code=type_code))

    count = 0
    for id_str in ids:
        device = model.query.get(int(id_str))
        if device:
            db.session.delete(device)
            count += 1

    db.session.commit()
    flash(f"成功删除 {count} 条记录")
    return redirect(url_for("devices.list", type_code=type_code))


@devices_bp.route("/<type_code>/import", methods=["GET", "POST"])
@login_required
def import_data(type_code):
    config = get_config_or_404(type_code)
    flash(f"导入功能已统一迁移到「导入数据」页面")
    return redirect(url_for("imports.index"))
