from flask import Flask, send_from_directory
from config import Config
from app.models import db, User
from app.devices.valve_helper import get_all_valve_models
from app.devices import DeviceTypeRegistry
from flask_login import LoginManager, current_user
import os

basedir = os.path.abspath(os.path.dirname(__file__))
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = None


def create_app(config_class=Config):
    template_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
    static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    app.config.from_object(config_class)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    @app.route("/uploads/<path:filename>")
    def serve_upload(filename):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.context_processor
    def inject_pending_count():
        try:
            if current_user.is_authenticated and current_user.role in [
                "leader",
                "admin",
            ]:
                from app.models import Ledger
                pending_count = 0
                for ledger in Ledger.query.all():
                    config = DeviceTypeRegistry.get(ledger.类型)
                    if config and config.model_class:
                        model = config.model_class
                        if model.query.filter_by(ledger_id=ledger.id, status="pending").count() > 0:
                            pending_count += 1
            else:
                pending_count = 0
        except:
            pending_count = 0

        try:
            if current_user.is_authenticated:
                from datetime import date, timedelta
                from app.models import MaintenancePlan, MaintenancePlanItem
                now = date.today()
                plan_warning_count = 0
                if current_user.role in ("employee", "admin"):
                    published_plan_ids = db.session.query(MaintenancePlan.id).filter(
                        MaintenancePlan.status == "published"
                    ).subquery()
                    seven_days_later = now + timedelta(days=7)
                    plan_warning_count = MaintenancePlanItem.query.filter(
                        MaintenancePlanItem.plan_id.in_(published_plan_ids),
                        MaintenancePlanItem.status == "pending",
                        MaintenancePlanItem.planned_date_end >= now.isoformat(),
                        MaintenancePlanItem.planned_date_end <= seven_days_later.isoformat(),
                    ).count() + MaintenancePlanItem.query.filter(
                        MaintenancePlanItem.plan_id.in_(published_plan_ids),
                        MaintenancePlanItem.status == "pending",
                        MaintenancePlanItem.planned_date_end < now.isoformat(),
                    ).count()
            else:
                plan_warning_count = 0
        except:
            plan_warning_count = 0

        from app.devices.valve_helper import VALVE_TYPES
        return dict(pending_count=pending_count, VALVE_TYPES=VALVE_TYPES, plan_warning_count=plan_warning_count)

    # 注册导航上下文处理器
    from app.utils.navigation import inject_navigation
    app.context_processor(inject_navigation)

    from app.routes import bp
    from app.routes.auth import auth
    from app.routes.approvals import approvals
    from app.routes.valves import valves
    from app.routes.admin import admin
    from app.routes.ledgers import ledgers
    from app.routes.imports import imports
    from app.routes.maintenance_import import maintenance_import
    from app.routes.statistics import statistics
    from app.routes.plans import plans_bp

    app.register_blueprint(bp)
    app.register_blueprint(auth)
    app.register_blueprint(approvals)
    app.register_blueprint(valves)
    app.register_blueprint(admin)
    app.register_blueprint(ledgers)
    app.register_blueprint(imports)
    app.register_blueprint(maintenance_import)
    app.register_blueprint(statistics)
    app.register_blueprint(plans_bp)

    from app.devices.types import register_all
    register_all()

    from app.routes.devices import devices_bp
    app.register_blueprint(devices_bp)

    # 启动时自动补齐缺失的字段（增量迁移，不破坏已有数据）
    with app.app_context():
        _ensure_columns()

    return app


def _ensure_columns():
    """检查并添加模型表中缺失的字段（仅新增，不修改不删除）"""
    from app.models import MaintenanceRecord
    table = MaintenanceRecord.__tablename__
    try:
        inspector = db.inspect(db.engine)
        existing = {c["name"] for c in inspector.get_columns(table)}
        model_cols = {c.name for c in MaintenanceRecord.__table__.columns}
        for col_name in model_cols - existing:
            col = MaintenanceRecord.__table__.columns[col_name]
            stmt = f"ALTER TABLE {table} ADD COLUMN {col_name} {col.type.compile(db.engine.dialect)}"
            db.session.execute(db.text(stmt))
        if model_cols - existing:
            db.session.commit()
    except Exception:
        db.session.rollback()


def init_seed_data():
    """初始化种子数据（用户 + 系统设置），仅当数据不存在时插入"""
    from app.models import User, Setting

    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", role="admin", real_name="管理员", dept="管理部")
        admin.set_password("admin123")
        db.session.add(admin)

    if not User.query.filter_by(username="ld001").first():
        leader = User(
            username="ld001", role="leader", real_name="审批领导", dept="管理部"
        )
        leader.set_password("ld001")
        db.session.add(leader)

    if not User.query.filter_by(username="化工班").first():
        employee1 = User(
            username="化工班", role="employee", real_name="化工班", dept="化工班"
        )
        employee1.set_password("111")
        db.session.add(employee1)

    if not User.query.filter_by(username="动力班").first():
        employee2 = User(
            username="动力班", role="employee", real_name="动力班", dept="动力班"
        )
        employee2.set_password("222")
        db.session.add(employee2)

    if not Setting.query.get("auto_approval"):
        setting = Setting(key="auto_approval", value="true")
        db.session.add(setting)

    if not Setting.query.get("default_password"):
        setting = Setting(key="default_password", value="123456")
        db.session.add(setting)

    if not Setting.query.get("page_size"):
        setting = Setting(key="page_size", value="20")
        db.session.add(setting)

    if not Setting.query.get("system_name"):
        setting = Setting(key="system_name", value="仪表阀门智能管理系统")
        db.session.add(setting)

    db.session.commit()
