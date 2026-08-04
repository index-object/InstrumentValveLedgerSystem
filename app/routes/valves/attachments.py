from flask import (
    request,
    render_template,
    redirect,
    url_for,
    flash,
    current_app,
    make_response,
    abort,
)
from flask_login import login_required, current_user
from app.models import db, ValveAttachment, ValvePhoto, ValveDocument, ValveFile, MaintenanceRecord, MaintenancePlanItem, MaintenancePlan
from app.devices.valve_helper import (
    get_valve_model,
    get_valve_by_id,
    get_valve_ledger_type,
    get_all_valve_models,
    count_valves_by_status,
)
from app.routes.valves.permissions import (
    can_edit_valve,
    can_create_maintenance,
    can_edit_maintenance,
    can_delete_maintenance,
)
from app.utils.navigation import get_from_param, url_with_params
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import hashlib
import urllib.parse

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
DOCUMENT_EXTENSIONS = {"pdf", "doc", "docx"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def photos(id):
    """照片管理"""
    device_type = request.args.get("device_type")
    if device_type:
        model = get_valve_model(device_type)
        valve = model.query.get(id) if model else None
    else:
        valve = get_valve_by_id(id)
    if not valve:
        abort(404)

    if request.method == "POST":
        if "photo" not in request.files:
            flash("请选择文件")
            return redirect(request.url)

        file = request.files["photo"]
        if file and allowed_file(file.filename):
            filename = secure_filename(
                f"{valve.位号}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
            )
            file.save(os.path.join(current_app.config["UPLOAD_FOLDER"], filename))

            photo = ValvePhoto(
                device_type=get_valve_ledger_type(valve),
                device_id=valve.id,
                filename=filename,
                description=request.form.get("description", ""),
                uploaded_by=current_user.id,
            )
            db.session.add(photo)
            db.session.commit()
            flash("上传成功")

    return render_template("valves/photos.html", valve=valve)


def maintenance(id):
    """维护记录"""
    from_param = get_from_param()
    device_type = request.args.get("device_type")
    if device_type:
        model = get_valve_model(device_type)
        valve = model.query.get(id) if model else None
    else:
        valve = get_valve_by_id(id)
    if not valve:
        abort(404)

    if request.method == "POST":
        # 草稿状态阀门不可创建维护记录
        if valve.status == "draft":
            flash("当前阀门为草稿状态，请先提交审批后再添加维护记录")
            return redirect(url_with_params(
                'ledgers.valve_detail',
                ledger_id=valve.ledger_id,
                id=id,
            ) if valve.ledger_id else url_with_params("valves.detail", id=id))

        # 权限检查：只有员工和管理员可以创建维护记录
        if not can_create_maintenance():
            flash("无权创建维护记录")
            return redirect(url_with_params(
                'ledgers.valve_detail',
                ledger_id=valve.ledger_id,
                id=id,
            ) if valve.ledger_id else url_with_params("valves.detail", id=id))

        检修时间_str = request.form.get("检修时间")
        检修时间 = None
        if 检修时间_str:
            for fmt in ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                try:
                    检修时间 = datetime.strptime(检修时间_str, fmt)
                    break
                except ValueError:
                    continue

        if not request.form.get("检修人员") or not request.form.get("检修内容"):
            flash("检修人员和检修内容不能为空")
            return redirect(url_with_params('valves.maintenance', id=id))

        record = MaintenanceRecord(
            device_type=get_valve_ledger_type(valve),
            device_id=valve.id,
            装置名称=valve.装置名称,
            设备位号=valve.位号,
            设备名称=valve.名称,
            检修时间=检修时间,
            检修内容=request.form.get("检修内容"),
            检修人员=request.form.get("检修人员"),
            类型=request.form.get("类型"),
            created_by=current_user.id,
        )
        db.session.add(record)
        db.session.commit()
        flash("添加成功")
        # 返回到阀门详情页，保持上下文
        if valve.ledger_id:
            return redirect(url_with_params(
                'ledgers.valve_detail',
                ledger_id=valve.ledger_id,
                id=id,
            ))
        return redirect(url_with_params("valves.detail", id=id))

    records_query = MaintenanceRecord.query.filter_by(device_type=get_valve_ledger_type(valve), device_id=valve.id)
    if current_user.role == "employee":
        records_query = records_query.filter(MaintenanceRecord.created_by == current_user.id)
    records = records_query.order_by(MaintenanceRecord.检修时间.desc()).all()
    return render_template("valves/maintenance.html", valve=valve, records=records, from_param=from_param)


def maintenance_list():
    """维护记录列表"""
    query = MaintenanceRecord.query

    if current_user.role == "employee":
        query = query.filter(MaintenanceRecord.created_by == current_user.id)

    search = request.args.get("search")
    if search:
        search_conditions = []
        for column_name in ["装置名称", "设备位号", "设备名称", "检修人员", "检修内容", "类型"]:
            col = getattr(MaintenanceRecord, column_name)
            search_conditions.append(col.contains(search))
        query = query.filter(db.or_(*search_conditions))

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    pagination = query.order_by(MaintenanceRecord.检修时间.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    record_ids = [r.id for r in pagination.items]
    plan_lookup = {}
    if record_ids:
        linked_items = MaintenancePlanItem.query.filter(
            MaintenancePlanItem.maintenance_id.in_(record_ids)
        ).all()
        plan_lookup = {item.maintenance_id: item.plan.title if item.plan else "未知计划" for item in linked_items}

    return render_template(
        "maintenance/list.html", records=pagination.items, pagination=pagination,
        plan_lookup=plan_lookup
    )


def _plan_item_data(item):
    return {
        "id": item.id,
        "plan_id": item.plan_id,
        "plan_title": item.plan.title if item.plan else "",
        "device_type": item.device_type,
        "device_id": item.device_id,
        "tag": item.tag,
        "device_name": item.device_name or "",
        "planned_date_start": item.planned_date_start.strftime("%Y-%m-%d") if item.planned_date_start else "",
        "planned_date_end": item.planned_date_end.strftime("%Y-%m-%d") if item.planned_date_end else "",
    }


def _load_plan_items_data():
    """加载当前用户可关联的待办计划项（领导无此列表）"""
    if current_user.role == "leader":
        return []
    pending_items = MaintenancePlanItem.query.join(MaintenancePlanItem.plan).filter(
        MaintenancePlanItem.status == "pending",
        MaintenancePlan.status == "published",
    ).all()
    return [_plan_item_data(item) for item in pending_items]


def maintenance_create():
    """新建维护记录"""
    # 权限检查：只有员工和管理员可以创建维护记录
    if not can_create_maintenance():
        flash("无权创建维护记录")
        return redirect(url_for("valves.maintenance_list"))

    valves = []
    for model in get_all_valve_models():
        valves.extend(model.query.filter(model.status != "draft").order_by(model.位号).all())

    if request.method == "POST":
        valve_id = request.form.get("valve_id")
        valve_type = request.form.get("valve_type")
        valve = None
        if valve_id and valve_type:
            model = get_valve_model(valve_type)
            if model:
                valve = model.query.get(int(valve_id))
        if not valve:
            flash("请选择设备位号")
            return redirect(url_for("valves.maintenance_create"))

        if not request.form.get("检修人员") or not request.form.get("检修内容"):
            flash("检修人员和检修内容不能为空")
            return redirect(url_for("valves.maintenance_create"))

        检修时间_str = request.form.get("检修时间")
        检修时间 = None
        if 检修时间_str:
            for fmt in ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                try:
                    检修时间 = datetime.strptime(检修时间_str, fmt)
                    break
                except ValueError:
                    continue

        record = MaintenanceRecord(
            device_type=valve_type,
            device_id=valve.id,
            设备位号=valve.位号,
            设备名称=valve.名称,
            装置名称=valve.装置名称,
            检修时间=检修时间,
            检修内容=request.form.get("检修内容"),
            检修人员=request.form.get("检修人员"),
            类型=request.form.get("类型"),
            created_by=current_user.id,
        )
        db.session.add(record)
        db.session.flush()

        plan_item_id = request.form.get("plan_item_id", type=int)
        if plan_item_id:
            plan_item = MaintenancePlanItem.query.get(plan_item_id)
            if (plan_item and plan_item.status == "pending"
                    and plan_item.device_type == valve_type
                    and plan_item.device_id == valve.id):
                plan_item.status = "completed"
                plan_item.maintenance_id = record.id
                plan_item.completed_at = datetime.utcnow()
                plan_item.completed_by = current_user.id

        db.session.commit()
        flash("添加成功")
        return redirect(url_for("valves.maintenance_list"))

    valves_data = [
        {"id": v.id, "tag": v.位号, "name": v.名称 or "", "device_unit": v.装置名称 or "", "type": get_valve_ledger_type(v)}
        for v in valves
    ]

    plan_items_data = _load_plan_items_data()
    return render_template("maintenance/create.html", valves=valves, valves_data=valves_data, plan_items_data=plan_items_data)


def maintenance_edit(id):
    """编辑维护记录"""
    record = MaintenanceRecord.query.get_or_404(id)

    # 权限检查：只有创建者和管理员可以编辑维护记录
    if not can_edit_maintenance(record):
        flash("无权编辑此维护记录")
        return redirect(url_for("valves.maintenance_list"))

    valves = []
    for model in get_all_valve_models():
        valves.extend(model.query.filter(model.status != "draft").order_by(model.位号).all())

    if request.method == "POST":
        valve_id = request.form.get("valve_id")
        valve_type = request.form.get("valve_type")

        检修时间_str = request.form.get("检修时间")
        检修时间 = None
        if 检修时间_str:
            for fmt in ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                try:
                    检修时间 = datetime.strptime(检修时间_str, fmt)
                    break
                except ValueError:
                    continue

        if record.valve_deleted:
            record.检修时间 = 检修时间
            record.检修内容 = request.form.get("检修内容")
            record.检修人员 = request.form.get("检修人员")
            record.类型 = request.form.get("类型")
            db.session.commit()
            flash("保存成功")
            return redirect(url_for("valves.maintenance_list"))

        valve = None
        if valve_id and valve_type:
            model = get_valve_model(valve_type)
            if model:
                valve = model.query.get(int(valve_id))
        if not valve:
            flash("请选择设备位号")
            return redirect(url_for("valves.maintenance_edit", id=id))

        if not request.form.get("检修人员") or not request.form.get("检修内容"):
            flash("检修人员和检修内容不能为空")
            return redirect(url_for("valves.maintenance_edit", id=id))

        record.device_type = valve_type
        record.device_id = valve.id
        record.设备位号 = valve.位号
        record.设备名称 = valve.名称
        record.装置名称 = valve.装置名称
        record.检修时间 = 检修时间
        record.检修内容 = request.form.get("检修内容")
        record.检修人员 = request.form.get("检修人员")
        record.类型 = request.form.get("类型")
        plan_item_id = request.form.get("plan_item_id", type=int)
        old_item = MaintenancePlanItem.query.filter_by(maintenance_id=record.id).first()
        if old_item and old_item.id != plan_item_id:
            old_item.maintenance_id = None
            old_item.status = "pending"
            old_item.completed_at = None
            old_item.completed_by = None
        if plan_item_id:
            plan_item = MaintenancePlanItem.query.get(plan_item_id)
            if (plan_item and plan_item.device_type == record.device_type
                    and plan_item.device_id == record.device_id):
                plan_item.maintenance_id = record.id
                if plan_item.status == "pending":
                    plan_item.status = "completed"
                    plan_item.completed_at = datetime.utcnow()
                    plan_item.completed_by = current_user.id
        db.session.commit()
        flash("保存成功")
        return redirect(url_for("valves.maintenance_list"))

    plan_items_data = _load_plan_items_data()
    plan_item = MaintenancePlanItem.query.filter_by(maintenance_id=record.id).first()
    selected_plan_item_id = None
    if plan_item:
        selected_plan_item_id = plan_item.id
        if all(i["id"] != plan_item.id for i in plan_items_data):
            plan_items_data.append(_plan_item_data(plan_item))

    valves_data = [
        {"id": v.id, "tag": v.位号, "name": v.名称 or "", "device_unit": v.装置名称 or "", "type": get_valve_ledger_type(v)}
        for v in valves
    ]
    return render_template("maintenance/edit.html", record=record, valves=valves, valves_data=valves_data, plan_items_data=plan_items_data, selected_plan_item_id=selected_plan_item_id)


def maintenance_batch_delete():
    """批量删除维护记录"""
    ids = request.form.getlist("ids")
    if not ids:
        flash("请选择要删除的记录")
        return redirect(url_for("valves.maintenance_list"))

    count = 0
    for record_id in ids:
        record = MaintenanceRecord.query.get(int(record_id))
        if record and can_delete_maintenance(record):
            db.session.delete(record)
            count += 1
    db.session.commit()
    flash(f"成功删除 {count} 条记录")
    return redirect(url_for("valves.maintenance_list"))


def maintenance_export():
    """导出维护记录"""
    import pandas as pd
    from io import BytesIO

    ids = request.args.getlist("ids")
    if ids:
        records = MaintenanceRecord.query.filter(MaintenanceRecord.id.in_(ids)).all()
    else:
        records = MaintenanceRecord.query.order_by(
            MaintenanceRecord.检修时间.desc()
        ).all()

    data = [
        {
            "装置名称": r.装置名称,
            "设备位号": r.设备位号,
            "设备名称": r.设备名称,
            "检修时间": r.检修时间.strftime("%Y-%m-%d") if r.检修时间 else "",
            "检修人员": r.检修人员,
            "检修内容": r.检修内容,
            "类型": r.类型,
        }
        for r in records
    ]

    df = pd.DataFrame(data)
    buffer = BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)

    output = make_response(buffer.read())
    output.headers["Content-Disposition"] = "attachment; filename=maintenance.xlsx"
    output.headers["Content-Type"] = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    return output


def attachments(id):
    """附件管理"""
    device_type = request.args.get("device_type")
    if device_type:
        model = get_valve_model(device_type)
        valve = model.query.get(id) if model else None
    else:
        valve = get_valve_by_id(id)
    if not valve:
        abort(404)

    if request.method == "POST":
        attachment = ValveAttachment(
            device_type=get_valve_ledger_type(valve),
            device_id=valve.id,
            名称=request.form.get("名称"),
            设备等级=request.form.get("设备等级"),
            型号规格=request.form.get("型号规格"),
            生产厂家=request.form.get("生产厂家"),
            type=request.form.get("type"),
        )
        db.session.add(attachment)
        db.session.commit()
        flash("附件添加成功")
        return redirect(url_with_params("valves.attachments", id=id))

    attachments_list = ValveAttachment.query.filter_by(device_type=get_valve_ledger_type(valve), device_id=valve.id).all()
    return render_template(
        "valves/attachments.html", valve=valve, attachments=attachments_list
    )


def delete_attachment(valve_id, att_id):
    """删除附件"""
    from_param = get_from_param()
    attachment = ValveAttachment.query.get_or_404(att_id)
    _valve_model = get_valve_model(attachment.device_type)
    _valve = _valve_model.query.get(valve_id) if _valve_model else None
    if attachment.device_id != valve_id:
        flash("附件不存在")
        if _valve and _valve.ledger_id:
            return redirect(url_with_params(
                'ledgers.valve_detail',
                ledger_id=_valve.ledger_id,
                id=valve_id,
            ))
        return redirect(url_with_params("valves.detail", id=valve_id))

    valve = _valve_model.query.get(valve_id) if _valve_model else get_valve_by_id(valve_id)
    if not valve or not can_edit_valve(valve):
        flash("无权删除")
        if valve and valve.ledger_id:
            return redirect(url_with_params(
                'ledgers.valve_detail',
                ledger_id=valve.ledger_id,
                id=valve_id,
            ))
        return redirect(url_with_params("valves.detail", id=valve_id))

    db.session.delete(attachment)
    db.session.commit()
    flash("附件删除成功")
    if valve and valve.ledger_id:
        return redirect(url_with_params(
            'ledgers.valve_detail',
            ledger_id=valve.ledger_id,
            id=valve_id,
        ))
    return redirect(url_with_params("valves.detail", id=valve_id))


def my_ledgers():
    """我的台账合集列表"""
    from app.models import Ledger
    from app.devices import DeviceTypeRegistry

    query = Ledger.query.filter_by(created_by=current_user.id)

    search = request.args.get("search")
    if search:
        query = query.filter(Ledger.名称.contains(search))

    status = request.args.get("status")
    if status:
        query = query.filter(Ledger.status == status)

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

        ledger.can_edit = True

    return render_template("valves/my_ledgers.html", ledgers=ledgers_list)


def my_ledger_applications():
    """我的审批申请 - 按合集显示"""
    from app.models import Ledger

    ledgers = Ledger.query.filter_by(created_by=current_user.id).all()

    result = []
    for ledger in ledgers:
        counts = count_valves_by_status(ledger.id)
        if counts["pending"] > 0:
            ledger.pending_count = counts["pending"]
            ledger.total_count = counts["total"]
            result.append(ledger)

    return render_template("valves/my_ledger_applications.html", ledgers=result)


def documents(id):
    """文档管理"""
    device_type = request.args.get("device_type")
    if device_type:
        model = get_valve_model(device_type)
        valve = model.query.get(id) if model else None
    else:
        valve = get_valve_by_id(id)
    if not valve:
        abort(404)

    if request.method == "POST":
        if "document" not in request.files:
            flash("请选择文件")
            return redirect(request.url)

        file = request.files["document"]
        if file and file.filename:
            ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
            if ext not in DOCUMENT_EXTENSIONS:
                flash("仅支持 PDF / Word 文档")
                return redirect(request.url)

            file.seek(0)
            file_hash = hashlib.sha256(file.read()).hexdigest()
            file.seek(0)

            existing = ValveFile.query.filter_by(file_hash=file_hash).first()
            if existing:
                saved_name = existing.filename
                existing.ref_count += 1
                flash("检测到重复文件，已关联到已有文件")
            else:
                saved_name = secure_filename(f"doc_{valve.位号}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
                file.save(os.path.join(current_app.config["UPLOAD_FOLDER"], saved_name))
                existing = ValveFile(
                    file_hash=file_hash,
                    filename=saved_name,
                    file_size=os.path.getsize(os.path.join(current_app.config["UPLOAD_FOLDER"], saved_name)),
                    ref_count=1,
                )
                db.session.add(existing)
                db.session.flush()

            doc = ValveDocument(
                file_id=existing.id,
                device_type=get_valve_ledger_type(valve),
                device_id=valve.id,
                filename=saved_name,
                original_name=file.filename,
                file_type=ext,
                file_size=existing.file_size,
                description=request.form.get("description", ""),
                uploaded_by=current_user.id,
            )
            db.session.add(doc)
            db.session.commit()

    docs = ValveDocument.query.filter_by(
        device_type=get_valve_ledger_type(valve),
        device_id=valve.id,
    ).order_by(ValveDocument.uploaded_at.desc()).all()
    return render_template("valves/documents.html", valve=valve, documents=docs)


def delete_document(valve_id, doc_id):
    """删除文档"""
    doc = ValveDocument.query.get_or_404(doc_id)

    vf = doc.valve_file
    if vf:
        vf.ref_count -= 1
        if vf.ref_count <= 0:
            try:
                os.remove(os.path.join(current_app.config["UPLOAD_FOLDER"], vf.filename))
            except OSError:
                pass
            db.session.delete(vf)

    db.session.delete(doc)
    db.session.commit()
    flash("文档删除成功")
    return redirect(request.referrer or url_with_params("valves.documents", id=valve_id))


def preview_document(doc_id):
    """文档预览——PDF返回文件流，Word返回HTML"""
    doc = ValveDocument.query.get_or_404(doc_id)
    filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], doc.filename)
    if not os.path.exists(filepath):
        abort(404)

    if doc.file_type in ("docx", "doc"):
        try:
            import mammoth
            with open(filepath, "rb") as f:
                result = mammoth.convert_to_html(f)
            html = f"""<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>
<style>body{{font-family:sans-serif;padding:24px;line-height:1.8;color:#333;max-width:960px;margin:auto}}
table{{border-collapse:collapse;width:100%;margin:12px 0}}
td,th{{border:1px solid #bbb;padding:6px 10px;text-align:left}}
th{{background:#f5f5f5;font-weight:600}}img{{max-width:100%}}</style>
</head><body>{result.value}</body></html>"""
        except Exception:
            html = "<p>文档解析失败</p>"
        response = make_response(html)
        response.headers["Content-Type"] = "text/html; charset=utf-8"
        return response

    with open(filepath, "rb") as f:
        data = f.read()
    response = make_response(data)
    mime_map = {"pdf": "application/pdf", "doc": "application/msword"}
    response.headers["Content-Type"] = mime_map.get(doc.file_type, "application/octet-stream")
    ascii_name = doc.original_name or doc.filename
    try:
        ascii_name.encode("ascii")
    except UnicodeEncodeError:
        ascii_name = "document." + (doc.file_type or "bin")
    encoded_name = urllib.parse.quote(doc.original_name or doc.filename)
    response.headers["Content-Disposition"] = f'inline; filename="{ascii_name}"; filename*=UTF-8\'\'{encoded_name}'
    return response


def register_attachment_routes(bp):
    """注册附件相关路由到蓝图"""
    bp.route("/valve/<int:id>/photos", methods=["GET", "POST"])(login_required(photos))
    bp.route("/valve/<int:id>/maintenance", methods=["GET", "POST"])(
        login_required(maintenance)
    )
    bp.route("/maintenance")(login_required(maintenance_list))
    bp.route("/maintenance/new", methods=["GET", "POST"])(login_required(maintenance_create))
    bp.route("/maintenance/edit/<int:id>", methods=["GET", "POST"])(login_required(maintenance_edit))
    bp.route("/maintenance/batch-delete", methods=["POST"])(
        login_required(maintenance_batch_delete)
    )
    bp.route("/maintenance/export")(login_required(maintenance_export))
    bp.route("/valve/<int:id>/attachments", methods=["GET", "POST"])(
        login_required(attachments)
    )
    bp.route("/valve/<int:valve_id>/attachment/<int:att_id>/delete", methods=["POST"])(
        login_required(delete_attachment)
    )
    bp.route("/my-ledgers")(login_required(my_ledgers))
    bp.route("/my-ledger-applications")(login_required(my_ledger_applications))
    bp.route("/valve/<int:id>/documents", methods=["GET", "POST"])(
        login_required(documents)
    )
    bp.route("/valve/<int:valve_id>/document/<int:doc_id>/delete", methods=["POST"])(
        login_required(delete_document)
    )
    bp.route("/document/<int:doc_id>/preview")(
        login_required(preview_document)
    )
