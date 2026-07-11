from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import db, User, Ledger, MaintenanceRecord
from app.devices import DeviceTypeRegistry

statistics = Blueprint("statistics", __name__, url_prefix="/statistics")


@statistics.route("/")
@login_required
def index():
    all_users = User.query.filter_by(status="active", role="employee").order_by(User.real_name).all()

    user_count = len(all_users)
    all_ledgers = Ledger.query.filter(Ledger.approved_snapshot_status == "approved").order_by(Ledger.created_by).all()
    ledger_count = len(all_ledgers)
    device_count = 0
    maintenance_count = MaintenanceRecord.query.count()

    user_stats = []
    for user in all_users:
        user_ledgers = [l for l in all_ledgers if l.created_by == user.id]
        if not user_ledgers:
            user_stats.append(_build_user_stat(user, []))
            continue

        ledger_stats = []
        user_device_total = 0
        user_maintenance_total = 0

        for ledger in user_ledgers:
            config = DeviceTypeRegistry.get(ledger.类型)
            model = config and config.model_class
            approved_count = 0
            if model:
                approved_count = model.query.filter_by(ledger_id=ledger.id, status="approved").count()

            device_ids_inner = []
            if model:
                device_ids_inner = [r[0] for r in model.query.with_entities(model.id).filter_by(ledger_id=ledger.id).all()]

            device_maintenance_count = 0
            if device_ids_inner:
                device_maintenance_count = MaintenanceRecord.query.filter(
                    MaintenanceRecord.device_type == ledger.类型,
                    MaintenanceRecord.device_id.in_(device_ids_inner),
                ).count()
            user_maintenance_total += device_maintenance_count

            ledger_stats.append({
                "id": ledger.id,
                "名称": ledger.名称,
                "type_name": (config and config.name) or ledger.类型,
                "type_color": (config and config.color_scheme) or ["#f1f5f9", "#e2e8f0", "#475569", "#cbd5e1"],
                "approved_count": approved_count,
                "maintenance_count": device_maintenance_count,
            })
            user_device_total += approved_count

        role_colors = {
            "admin": "#dc2626",
            "leader": "#7c3aed",
            "employee": "#3b82f6",
        }
        role_badge_colors = {
            "admin": ["#fee2e2", "#991b1b"],
            "leader": ["#f5f3ff", "#7c3aed"],
            "employee": ["#e0e7ff", "#3730a3"],
        }
        role_names = {"admin": "管理员", "leader": "领导", "employee": "员工"}

        user_stats.append({
            "username": user.username,
            "real_name": user.real_name or user.username,
            "dept": user.dept or "未设置班组",
            "role": user.role,
            "role_name": role_names.get(user.role, user.role),
            "role_color": role_colors.get(user.role, "#6b7280"),
            "role_badge": role_badge_colors.get(user.role, ["#f3f4f6", "#6b7280"]),
            "avatar_color": _avatar_color(user.id),
            "ledger_count": len(user_ledgers),
            "device_count": user_device_total,
            "maintenance_count": user_maintenance_total,
            "ledgers": ledger_stats,
        })

        device_count += user_device_total

    return render_template(
        "statistics/index.html",
        user_count=user_count,
        ledger_count=ledger_count,
        device_count=device_count,
        maintenance_count=maintenance_count,
        user_stats=user_stats,
    )


def _avatar_color(user_id):
    colors = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6", "#f97316"]
    return colors[user_id % len(colors)]


def _build_user_stat(user, ledgers):
    return {
        "username": user.username,
        "real_name": user.real_name or user.username,
        "dept": user.dept or "未设置班组",
        "role": user.role,
        "role_name": {"admin": "管理员", "leader": "领导", "employee": "员工"}.get(user.role, user.role),
        "role_color": {"admin": "#dc2626", "leader": "#7c3aed", "employee": "#3b82f6"}.get(user.role, "#6b7280"),
        "role_badge": {"admin": ["#fee2e2", "#991b1b"], "leader": ["#f5f3ff", "#7c3aed"], "employee": ["#e0e7ff", "#3730a3"]}.get(user.role, ["#f3f4f6", "#6b7280"]),
        "avatar_color": _avatar_color(user.id),
        "ledger_count": 0,
        "device_count": 0,
        "maintenance_count": 0,
        "ledgers": [],
    }
