import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from app import create_app, db
from app.models import User, Valve, Setting


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def init_database(app):
    with app.app_context():
        admin = User(username="admin", role="admin", real_name="管理员", dept="管理部")
        admin.set_password("admin123")
        db.session.add(admin)

        user = User(username="user1", role="employee", real_name="张三", dept="维修部")
        user.set_password("user123")
        db.session.add(user)

        setting = Setting(key="auto_approval", value="true")
        db.session.add(setting)

        db.session.commit()

        yield db

        db.session.remove()
        db.drop_all()
