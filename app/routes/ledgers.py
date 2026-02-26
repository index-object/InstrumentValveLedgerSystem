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
from app.models import db, Ledger, Valve, ApprovalLog, Setting
from app.routes.valves.permissions import (
    can_edit_valve,
    can_delete_valve,
    can_view_ledger,
    can_view_valve,
)
from sqlalchemy import or_
from datetime import datetime

ledgers = Blueprint("ledgers", __name__)


def get_back_url(from_param):
    if from_param == "mine":
        return url_for("valves.my_ledgers")
    return url_for("ledgers.list")


def can_edit_ledger(ledger):
    return ledger.created_by == current_user.id or current_user.role in [
        "leader",
        "admin",
    ]


def can_edit_valve(valve):
    return valve.created_by == current_user.id or current_user.role in [
        "leader",
        "admin",
    ]


def can_delete_valve(valve):
    return can_edit_valve(valve)


@ledgers.route("/ledgers")
@login_required
def list():
    query = Ledger.query

    search = request.args.get("search")
    if search:
        query = query.filter(Ledger.名称.contains(search))

    status = request.args.get("status")
    if status:
        query = query.filter(Ledger.status == status)

    if current_user.role == "employee":
        query = query.filter(
            (Ledger.created_by == current_user.id) | (Ledger.status == "approved")
        )

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

    return render_template("ledgers/list.html", ledgers=ledgers_list)


@ledgers.route("/ledger/new", methods=["GET", "POST"])
@login_required
def new():
    from_param = request.args.get("from", "all")
    if request.method == "POST":
        ledger = Ledger()
        ledger.名称 = request.form.get("名称")
        ledger.描述 = request.form.get("描述")
        ledger.created_by = current_user.id
        ledger.status = "draft"

        db.session.add(ledger)
        db.session.commit()

        flash("台账集合创建成功")
        return redirect(get_back_url(from_param))

    return render_template("ledgers/form.html", ledger=None)


@ledgers.route("/ledger/<int:id>", methods=["GET", "POST"])
@login_required
def detail(id):
    from_param = request.args.get("from", "all")
    ledger = Ledger.query.get_or_404(id)

    if not can_view_ledger(ledger):
        flash("无权访问")
        return redirect(url_for("ledgers.list"))

    ledger.valve_count = Valve.query.filter_by(ledger_id=id).count()
    ledger.pending_count = Valve.query.filter_by(ledger_id=id, status="pending").count()
    ledger.rejected_count = Valve.query.filter_by(
        ledger_id=id, status="rejected"
    ).count()
    ledger.approved_count = Valve.query.filter_by(
        ledger_id=id, status="approved"
    ).count()
    ledger.draft_count = Valve.query.filter_by(ledger_id=id, status="draft").count()

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

    db.session.commit()

    if request.method == "POST":
        if not can_edit_ledger(ledger):
            flash("无权操作")
            return redirect(url_for("ledgers.detail", id=id, **{"from": from_param}))

        action = request.form.get("action")
        valve_ids = request.form.getlist("valve_ids")

        if action == "submit":
            draft_valves = Valve.query.filter_by(
                ledger_id=ledger.id, status="draft"
            ).all()
            for valve in draft_valves:
                valve.status = "pending"
                log = ApprovalLog(
                    ledger_id=ledger.id,
                    valve_id=valve.id,
                    action="submit",
                    user_id=current_user.id,
                )
                db.session.add(log)
            db.session.commit()
            flash(f"已提交 {len(draft_valves)} 项台账内容审批")
            return redirect(url_for("ledgers.detail", id=id, **{"from": from_param}))

        elif action == "batch_approve":
            if current_user.role not in ["leader", "admin"]:
                flash("需要领导权限")
                return redirect(
                    url_for("ledgers.detail", id=id, **{"from": from_param})
                )

            approved_count = 0
            for valve_id in valve_ids:
                valve = Valve.query.get(int(valve_id))
                if valve and valve.ledger_id == ledger.id and valve.status == "pending":
                    valve.status = "approved"
                    valve.approved_by = current_user.id
                    valve.approved_at = datetime.utcnow()
                    log = ApprovalLog(
                        ledger_id=ledger.id,
                        valve_id=valve.id,
                        action="approve",
                        user_id=current_user.id,
                        comment=request.form.get("comment", ""),
                    )
                    db.session.add(log)
                    approved_count += 1
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
                valve = Valve.query.get(int(valve_id))
                if valve and valve.ledger_id == ledger.id and valve.status == "pending":
                    valve.status = "rejected"
                    log = ApprovalLog(
                        ledger_id=ledger.id,
                        valve_id=valve.id,
                        action="reject",
                        user_id=current_user.id,
                        comment=request.form.get("comment", ""),
                    )
                    db.session.add(log)
                    rejected_count += 1
            db.session.commit()
            flash(f"已驳回 {rejected_count} 项台账内容")
            return redirect(url_for("ledgers.detail", id=id, **{"from": from_param}))

    query = Valve.query.filter_by(ledger_id=id)

    if current_user.role == "employee":
        query = query.filter(
            (Valve.created_by == current_user.id) | (Valve.status == "approved")
        )

    search = request.args.get("search")
    if search:
        search_conditions = []
        for column in Valve.__table__.columns:
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
                col = getattr(Valve, column.name)
                search_conditions.append(col.contains(search))
        if search_conditions:
            query = query.filter(or_(*search_conditions))

    status = request.args.get("status")
    if status:
        query = query.filter(Valve.status == status)

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
        if hasattr(Valve, field):
            values = (
                db.session.query(getattr(Valve, field))
                .distinct()
                .filter(
                    getattr(Valve, field).isnot(None),
                    getattr(Valve, field) != "",
                    Valve.ledger_id == id,
                )
                .all()
            )
            filter_options[field] = sorted([v[0] for v in values if v[0]], key=str)

    active_filters = {}
    for label, field in filterable_fields:
        values = request.args.getlist(field)
        if values and hasattr(Valve, field):
            field_filter = getattr(Valve, field).in_(values)
            query = query.filter(field_filter)
            active_filters[field] = values

    pagination = query.order_by(Valve.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    valves_list = pagination.items

    装置列表 = (
        db.session.query(Valve.装置名称)
        .distinct()
        .filter(Valve.装置名称.isnot(None), Valve.ledger_id == id)
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

    pending_count = Valve.query.filter_by(ledger_id=id, status="pending").count()
    if pending_count > 0:
        flash(f"当前有 {pending_count} 条待审批记录，无法删除")
        return redirect(get_back_url(from_param))

    Valve.query.filter_by(ledger_id=id).delete()
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

    valve_ids = request.form.getlist("valve_ids")

    if valve_ids:
        submit_valves = Valve.query.filter(
            Valve.id.in_(valve_ids), Valve.ledger_id == id, Valve.status == "draft"
        ).all()
    else:
        submit_valves = Valve.query.filter_by(ledger_id=id, status="draft").all()

    if not submit_valves:
        flash("没有可提交的台账")
        return redirect(url_for("ledgers.detail", id=id, **{"from": from_param}))

    for valve in submit_valves:
        valve.status = "pending"
        log = ApprovalLog(
            ledger_id=ledger.id,
            valve_id=valve.id,
            action="submit",
            user_id=current_user.id,
        )
        db.session.add(log)

    db.session.commit()

    flash(f"已提交 {len(submit_valves)} 项台账内容审批")
    return redirect(url_for("ledgers.detail", id=id, **{"from": from_param}))


@ledgers.route("/ledger/<int:id>/approve", methods=["POST"])
@login_required
def approve(id):
    from_param = request.args.get("from", "all")
    if current_user.role not in ["leader", "admin"]:
        flash("需要领导权限")
        return redirect(get_back_url(from_param))

    ledger = Ledger.query.get_or_404(id)

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
            comment=request.form.get("comment", ""),
        )
        db.session.add(log)

    db.session.commit()

    flash(f"已审批通过，共 {len(pending_valves)} 项台账内容")
    return redirect(url_for("ledgers.detail", id=id, **{"from": from_param}))


@ledgers.route("/ledger/<int:id>/reject", methods=["POST"])
@login_required
def reject(id):
    from_param = request.args.get("from", "all")
    if current_user.role not in ["leader", "admin"]:
        flash("需要领导权限")
        return redirect(get_back_url(from_param))

    ledger = Ledger.query.get_or_404(id)

    pending_valves = Valve.query.filter_by(ledger_id=id, status="pending").all()
    for valve in pending_valves:
        valve.status = "rejected"
        log = ApprovalLog(
            ledger_id=ledger.id,
            valve_id=valve.id,
            action="reject",
            user_id=current_user.id,
            comment=request.form.get("comment", ""),
        )
        db.session.add(log)

    db.session.commit()

    flash(f"已驳回，共 {len(pending_valves)} 项台账内容")
    return redirect(url_for("ledgers.detail", id=id, **{"from": from_param}))


@ledgers.route("/ledger/<int:id>/valve/new", methods=["GET", "POST"])
@login_required
def new_valve(id):
    from_param = request.args.get("from", "all")
    ledger = Ledger.query.get_or_404(id)

    if not can_edit_ledger(ledger):
        flash("无权操作")
        return redirect(url_for("ledgers.detail", id=id, **{"from": from_param}))

    if request.method == "POST":
        位号 = request.form.get("位号")
        if 位号:
            existing = Valve.query.filter(
                Valve.位号 == 位号, Valve.status != "draft"
            ).first()
            if existing:
                flash("位号已存在，请使用其他位号")
                return redirect(
                    url_for("ledgers.new_valve", id=id, **{"from": from_param})
                )

        valve = Valve()
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
        except:
            db.session.rollback()
            flash("位号已存在，请使用其他位号")
            return redirect(url_for("ledgers.new_valve", id=id, **{"from": from_param}))

        ledger.valve_count = Valve.query.filter_by(ledger_id=id).count()
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
    valve = Valve.query.get_or_404(id)

    if not can_edit_valve(valve):
        flash("无权编辑")
        return redirect(url_for("ledgers.detail", id=ledger_id, **{"from": from_param}))

    if valve.status not in ["draft", "rejected", "approved"]:
        flash("当前状态无法编辑")
        return redirect(url_for("ledgers.detail", id=ledger_id, **{"from": from_param}))

    if request.method == "POST":
        for key in request.form:
            if hasattr(valve, key):
                setattr(valve, key, request.form.get(key))

        db.session.commit()
        flash("更新成功")
        return redirect(url_for("ledgers.detail", id=ledger_id, **{"from": from_param}))

    return render_template(
        "valves/form.html", valve=valve, ledger=ledger, from_param=from_param
    )


@ledgers.route("/ledger/<int:ledger_id>/valve/<int:id>")
@login_required
def valve_detail(ledger_id, id):
    valve = Valve.query.get_or_404(id)
    from_param = request.args.get("from", "all")
    return render_template(
        "valves/detail.html", valve=valve, ledger_id=ledger_id, from_param=from_param
    )


@ledgers.route("/ledger/<int:ledger_id>/valve/delete/<int:id>", methods=["POST"])
@login_required
def delete_valve(ledger_id, id):
    from_param = request.args.get("from", "all")
    ledger = Ledger.query.get_or_404(ledger_id)
    valve = Valve.query.get_or_404(id)

    if not can_delete_valve(valve):
        flash("无权删除")
        return redirect(url_for("ledgers.detail", id=ledger_id, **{"from": from_param}))

    if valve.status not in ["draft", "rejected"]:
        flash("当前状态无法删除")
        return redirect(url_for("ledgers.detail", id=ledger_id, **{"from": from_param}))

    db.session.delete(valve)

    ledger.valve_count = Valve.query.filter_by(ledger_id=ledger_id).count()
    ledger.pending_count = Valve.query.filter_by(
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

    if not can_edit_ledger(ledger):
        return jsonify({"success": False, "message": "无权操作"}), 403

    pending_count = Valve.query.filter_by(ledger_id=id, status="pending").count()
    if pending_count > 0:
        return jsonify({"success": False, "message": "当前有待审批记录，无法编辑"}), 400

    data = request.get_json()
    if not data or not isinstance(data, list):
        return jsonify({"success": False, "message": "无效数据格式"})

    saved_ids = []
    errors = []

    for item in data:
        valve_id = item.get("id")
        form_data = item.get("data", {})

        if valve_id:
            valve = Valve.query.get(valve_id)
            if not valve or valve.ledger_id != id:
                errors.append({"id": valve_id, "error": "台账不存在"})
                continue

            if valve.status not in ["draft", "rejected"]:
                errors.append({"id": valve_id, "error": "当前状态无法编辑"})
                continue
        else:
            valve = Valve()
            valve.ledger_id = id
            valve.created_by = current_user.id
            valve.status = "draft"
            db.session.add(valve)

        for key, value in form_data.items():
            if hasattr(valve, key):
                setattr(valve, key, value)

        saved_ids.append(valve.id)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

    ledger.valve_count = Valve.query.filter_by(ledger_id=id).count()
    db.session.commit()

    return jsonify({"success": True, "saved_ids": saved_ids, "errors": errors})


@ledgers.route("/ledger/<int:id>/valve/batch-delete", methods=["POST"])
@login_required
def batch_delete_valve(id):
    from_param = request.args.get("from", "all")
    ledger = Ledger.query.get_or_404(id)

    if not can_edit_ledger(ledger):
        flash("无权操作")
        return redirect(url_for("ledgers.detail", id=id, **{"from": from_param}))

    pending_count = Valve.query.filter_by(ledger_id=id, status="pending").count()
    if pending_count > 0:
        flash(f"当前有 {pending_count} 条待审批记录，无法删除")
        return redirect(url_for("ledgers.detail", id=id, **{"from": from_param}))

    valve_ids = request.form.getlist("valve_ids")
    if not valve_ids:
        flash("请选择要删除的台账")
        return redirect(url_for("ledgers.detail", id=id, **{"from": from_param}))

    deleted_count = Valve.query.filter(
        Valve.id.in_(valve_ids),
        Valve.ledger_id == id,
        Valve.status.in_(["draft", "rejected"]),
    ).delete(synchronize_session=False)

    ledger.valve_count = Valve.query.filter_by(ledger_id=id).count()

    db.session.commit()
    flash(f"成功删除 {deleted_count} 项台账")
    return redirect(url_for("ledgers.detail", id=id, **{"from": from_param}))
