from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import Valve, MaintenanceRecord, User

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def index():
    total = Valve.query.count()
    pending = Valve.query.filter_by(status="pending").count()
    my_valves = Valve.query.filter_by(created_by=current_user.id).count()
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
        "index.html",
        total=total,
        pending=pending,
        my_valves=my_valves,
        maintenance_count=maintenance_count,
        user_stats=user_stats,
    )


from app.routes import auth, valves, admin
