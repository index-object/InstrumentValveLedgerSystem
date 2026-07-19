from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import MaintenanceRecord, User, Ledger
from app.devices.valve_helper import get_all_valve_models, count_valves_by_status

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def index():
    # 全部台账 - 合集数量和记录总数（与 ledgers 页面过滤条件一致）
    approved_ledgers = Ledger.query.filter(
        Ledger.approved_snapshot_status == "approved"
    ).all()
    total_ledgers = len(approved_ledgers)

    # 统计每个已审批合集在快照时间点之前已审批的阀门数量
    total_valves = 0
    for ledger in approved_ledgers:
        count = 0
        for model in get_all_valve_models():
            q = model.query.filter(
                model.ledger_id == ledger.id,
                model.status == "approved",
            )
            if ledger.approved_snapshot_at:
                q = q.filter(model.approved_at <= ledger.approved_snapshot_at)
            count += q.count()
        total_valves += count

    # 我的台账 - 用户创建的合集和记录数
    my_ledger_count = Ledger.query.filter_by(created_by=current_user.id).count()
    my_valve_count = 0
    for model in get_all_valve_models():
        my_valve_count += (
            model.query.join(Ledger).filter(Ledger.created_by == current_user.id).count()
        )

    # 我的申请 - 用户提交的待审批合集
    my_pending_ledger_ids = set()
    for model in get_all_valve_models():
        for ledger_id, in (
            Ledger.query.join(model, Ledger.id == model.ledger_id)
            .with_entities(Ledger.id)
            .filter(Ledger.created_by == current_user.id, model.status == "pending")
            .distinct()
        ):
            my_pending_ledger_ids.add(ledger_id)
    my_pending_ledgers = len(my_pending_ledger_ids)

    # 待审批（管理员/领导）
    if current_user.role in ["leader", "admin"]:
        pending_valves = 0
        for model in get_all_valve_models():
            pending_valves += model.query.filter_by(status="pending").count()
    else:
        pending_valves = my_pending_ledgers

    maintenance_query = MaintenanceRecord.query
    if current_user.role == "employee":
        maintenance_query = maintenance_query.filter(MaintenanceRecord.created_by == current_user.id)
    maintenance_count = maintenance_query.count()

    user_stats = []
    if current_user.role in ["leader", "admin"]:
        users = User.query.filter_by(status="active").all()
        for user in users:
            count = 0
            for model in get_all_valve_models():
                count += model.query.filter_by(created_by=user.id).count()
            user_stats.append(
                {"username": user.real_name or user.username, "count": count}
            )

    return render_template(
        f"index_{current_user.role}.html",
        total_ledgers=total_ledgers,
        total_valves=total_valves,
        my_ledger_count=my_ledger_count,
        my_valve_count=my_valve_count,
        my_pending_ledgers=my_pending_ledgers,
        pending=pending_valves,
        maintenance_count=maintenance_count,
        user_stats=user_stats,
    )


from app.routes import auth, admin
from app.routes.valves import valves
