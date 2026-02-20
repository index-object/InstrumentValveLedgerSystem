from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import Valve

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def index():
    total = Valve.query.count()
    pending = Valve.query.filter_by(status="pending").count()
    my_valves = Valve.query.filter_by(created_by=current_user.id).count()
    return render_template(
        "index.html", total=total, pending=pending, my_valves=my_valves
    )


from app.routes import auth, valves, admin
