from flask import Flask
from config import Config
from app.models import db, User, Valve
from flask_login import LoginManager, current_user
import os

basedir = os.path.abspath(os.path.dirname(__file__))
login_manager = LoginManager()
login_manager.login_view = "auth.login"


def create_app(config_class=Config):
    template_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
    app = Flask(__name__, template_folder=template_dir)
    app.config.from_object(config_class)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

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
                pending_count = Valve.query.filter_by(status="pending").count()
            else:
                pending_count = 0
        except:
            pending_count = 0
        return dict(pending_count=pending_count)

    from app.routes import bp
    from app.routes.auth import auth
    from app.routes.valves import valves
    from app.routes.admin import admin
    from app.routes.ledgers import ledgers

    app.register_blueprint(bp)
    app.register_blueprint(auth)
    app.register_blueprint(valves)
    app.register_blueprint(admin)
    app.register_blueprint(ledgers)

    return app
