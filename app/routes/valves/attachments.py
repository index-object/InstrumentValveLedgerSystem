from flask import (
    request,
    render_template,
    redirect,
    url_for,
    flash,
    current_app,
    make_response,
)
from flask_login import login_required, current_user
from app.models import db, Valve, ValveAttachment, ValvePhoto, MaintenanceRecord
from app.routes.valves.permissions import can_edit_valve
from werkzeug.utils import secure_filename
from datetime import datetime
import os

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def photos(id):
    """照片管理"""
    valve = Valve.query.get_or_404(id)

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
                valve_id=valve.id,
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
    valve = Valve.query.get_or_404(id)

    if request.method == "POST":
        检修时间_str = request.form.get("检修时间")
        检修时间 = None
        if 检修时间_str:
            for fmt in ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"]:
                try:
                    检修时间 = datetime.strptime(检修时间_str, fmt)
                    break
                except ValueError:
                    continue

        record = MaintenanceRecord(
            valve_id=valve.id,
            所属中心=request.form.get("所属中心"),
            设备位号=request.form.get("设备位号"),
            设备名称=request.form.get("设备名称"),
            检修时间=检修时间,
            检修内容=request.form.get("检修内容"),
            检修人员=request.form.get("检修人员"),
            类型=request.form.get("类型"),
            created_by=current_user.id,
        )
        db.session.add(record)
        db.session.commit()
        flash("添加成功")
        return redirect(url_for("valves.maintenance", id=id))

    records = (
        MaintenanceRecord.query.filter_by(valve_id=id)
        .order_by(MaintenanceRecord.检修时间.desc())
        .all()
    )
    return render_template("valves/maintenance.html", valve=valve, records=records)


def maintenance_list():
    """维护记录列表"""
    query = MaintenanceRecord.query

    search = request.args.get("search")
    if search:
        query = query.filter(MaintenanceRecord.检修内容.contains(search))

    valve_id = request.args.get("valve_id")
    if valve_id:
        query = query.filter(MaintenanceRecord.valve_id == int(valve_id))

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    pagination = query.order_by(MaintenanceRecord.检修时间.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return render_template(
        "maintenance/list.html", records=pagination.items, pagination=pagination
    )


def maintenance_batch_delete():
    """批量删除维护记录"""
    ids = request.form.getlist("ids")
    if not ids:
        flash("请选择要删除的记录")
        return redirect(url_for("valves.maintenance_list"))

    count = MaintenanceRecord.query.filter(MaintenanceRecord.id.in_(ids)).delete(
        synchronize_session=False
    )
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
            "设备位号": r.设备位号,
            "设备名称": r.设备名称,
            "所属中心": r.所属中心,
            "检修时间": r.检修时间.strftime("%Y-%m-%d %H:%M") if r.检修时间 else "",
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
    valve = Valve.query.get_or_404(id)

    if request.method == "POST":
        attachment = ValveAttachment(
            valve_id=valve.id,
            名称=request.form.get("名称"),
            设备等级=request.form.get("设备等级"),
            型号规格=request.form.get("型号规格"),
            生产厂家=request.form.get("生产厂家"),
            type=request.form.get("type"),
        )
        db.session.add(attachment)
        db.session.commit()
        flash("附件添加成功")
        return redirect(url_for("valves.attachments", id=id))

    attachments_list = valve.attachments
    return render_template(
        "valves/attachments.html", valve=valve, attachments=attachments_list
    )


def delete_attachment(valve_id, att_id):
    """删除附件"""
    attachment = ValveAttachment.query.get_or_404(att_id)
    if attachment.valve_id != valve_id:
        flash("附件不存在")
        return redirect(url_for("valves.detail", id=valve_id))

    if not can_edit_valve(attachment.valve):
        flash("无权删除")
        return redirect(url_for("valves.detail", id=valve_id))

    db.session.delete(attachment)
    db.session.commit()
    flash("附件删除成功")
    return redirect(url_for("valves.detail", id=valve_id))


def my_ledgers():
    """我的台账合集列表"""
    from app.models import Ledger

    query = Ledger.query.filter_by(created_by=current_user.id)

    search = request.args.get("search")
    if search:
        query = query.filter(Ledger.名称.contains(search))

    status = request.args.get("status")
    if status:
        query = query.filter(Ledger.status == status)

    ledgers_list = query.order_by(Ledger.created_at.desc()).all()

    for ledger in ledgers_list:
        ledger.valve_count = Valve.query.filter_by(ledger_id=ledger.id).count()
        ledger.pending_count = Valve.query.filter_by(
            ledger_id=ledger.id, status="pending"
        ).count()
        ledger.rejected_count = Valve.query.filter_by(
            ledger_id=ledger.id, status="rejected"
        ).count()
        ledger.approved_count = Valve.query.filter_by(
            ledger_id=ledger.id, status="approved"
        ).count()
        ledger.draft_count = Valve.query.filter_by(
            ledger_id=ledger.id, status="draft"
        ).count()

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

    ledgers = (
        Ledger.query.join(Valve, Ledger.id == Valve.ledger_id)
        .filter(Ledger.created_by == current_user.id, Valve.status == "pending")
        .distinct()
        .all()
    )

    for ledger in ledgers:
        ledger.pending_count = Valve.query.filter_by(
            ledger_id=ledger.id, status="pending"
        ).count()
        ledger.total_count = Valve.query.filter_by(ledger_id=ledger.id).count()

    return render_template("valves/my_ledger_applications.html", ledgers=ledgers)


def register_attachment_routes(bp):
    """注册附件相关路由到蓝图"""
    bp.route("/valve/<int:id>/photos", methods=["GET", "POST"])(login_required(photos))
    bp.route("/valve/<int:id>/maintenance", methods=["GET", "POST"])(
        login_required(maintenance)
    )
    bp.route("/maintenance")(login_required(maintenance_list))
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
