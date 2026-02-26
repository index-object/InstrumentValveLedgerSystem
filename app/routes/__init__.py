from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import Valve, MaintenanceRecord, User, Ledger

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def index():
    # 全部台账 - 合集数量和记录总数
    total_ledgers = Ledger.query.count()
    total_valves = Valve.query.count()

    # 我的台账 - 用户创建的合集和记录数
    my_ledger_count = Ledger.query.filter_by(created_by=current_user.id).count()
    my_valve_count = (
        Valve.query.join(Ledger).filter(Ledger.created_by == current_user.id).count()
    )

    # 我的申请 - 用户提交的待审批合集
    my_pending_ledgers = (
        Ledger.query.join(Valve, Ledger.id == Valve.ledger_id)
        .filter(Ledger.created_by == current_user.id, Valve.status == "pending")
        .distinct()
        .count()
    )

    # 待审批（管理员/领导）
    if current_user.role in ["leader", "admin"]:
        pending_valves = Valve.query.filter_by(status="pending").count()
    else:
        pending_valves = my_pending_ledgers

    maintenance_count = MaintenanceRecord.query.count()

    user_stats = []
    if current_user.role in ["leader", "admin"]:
        users = User.query.filter_by(status="active").all()
        for user in users:
            count = Valve.query.filter_by(created_by=user.id).count()
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
