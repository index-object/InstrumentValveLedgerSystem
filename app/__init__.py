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
                pending_count = 0
                for model in get_all_valve_models():
                    pending_count += model.query.filter_by(status="pending").count()
                valve_model_set = set(get_all_valve_models())
                for config in DeviceTypeRegistry.all():
                    if config.model_class and config.model_class not in valve_model_set:
                        pending_count += config.model_class.query.filter_by(status="pending").count()
            else:
                pending_count = 0
        except:
            pending_count = 0
        return dict(pending_count=pending_count)

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

    app.register_blueprint(bp)
    app.register_blueprint(auth)
    app.register_blueprint(approvals)
    app.register_blueprint(valves)
    app.register_blueprint(admin)
    app.register_blueprint(ledgers)
    app.register_blueprint(imports)

    from app.devices.types import register_all
    register_all()

    from app.routes.devices import devices_bp
    app.register_blueprint(devices_bp)

    return app


def init_seed_data():
    """初始化种子数据（用户 + 系统设置），仅当数据不存在时插入"""
    from app.models import User, Setting

    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", role="admin", real_name="管理员", dept="管理部")
        admin.set_password("admin123")
        db.session.add(admin)

    if not User.query.filter_by(username="leader").first():
        leader = User(
            username="leader", role="leader", real_name="李领导", dept="维修部"
        )
        leader.set_password("leader123")
        db.session.add(leader)

    if not User.query.filter_by(username="user1").first():
        employee = User(
            username="user1", role="employee", real_name="张三", dept="维修部"
        )
        employee.set_password("user123")
        db.session.add(employee)

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
        setting = Setting(key="system_name", value="仪表阀门台账系统")
        db.session.add(setting)

    db.session.commit()
