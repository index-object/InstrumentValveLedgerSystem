import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from app import create_app, db
from app.models import User, Ledger, MaintenanceRecord, Setting


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


# ========== 权限测试用fixtures ==========

@pytest.fixture
def employee_user(app):
    """员工用户"""
    with app.app_context():
        user = User(username="employee1", role="employee", real_name="员工甲", dept="维修部")
        user.set_password("password")
        db.session.add(user)
        db.session.commit()
        yield user


@pytest.fixture
def leader_user(app):
    """领导用户"""
    with app.app_context():
        user = User(username="leader1", role="leader", real_name="领导甲", dept="管理部")
        user.set_password("password")
        db.session.add(user)
        db.session.commit()
        yield user


@pytest.fixture
def admin_user(app):
    """管理员用户"""
    with app.app_context():
        user = User(username="admin_test", role="admin", real_name="管理员甲", dept="管理部")
        user.set_password("password")
        db.session.add(user)
        db.session.commit()
        yield user


@pytest.fixture
def other_employee(app):
    """其他员工用户（用于测试所有权）"""
    with app.app_context():
        user = User(username="employee2", role="employee", real_name="员工乙", dept="其他部")
        user.set_password("password")
        db.session.add(user)
        db.session.commit()
        yield user


@pytest.fixture
def test_ledger(app, employee_user):
    """测试用台账合集"""
    with app.app_context():
        ledger = Ledger(
            名称="测试台账",
            描述="测试用台账合集",
            status="draft",
            created_by=employee_user.id
        )
        db.session.add(ledger)
        db.session.commit()
        yield ledger


@pytest.fixture
def test_valve(app, test_ledger, employee_user):
    """测试用阀门"""
    from app.devices.types.control_valve import ControlValve
    with app.app_context():
        test_ledger.类型 = "control_valve"
        valve = ControlValve(
            ledger_id=test_ledger.id,
            位号="TEST-001",
            名称="测试阀门",
            status="draft",
            created_by=employee_user.id
        )
        db.session.add(valve)
        db.session.commit()
        yield valve


@pytest.fixture
def test_maintenance(app, test_valve, employee_user):
    """测试用维护记录"""
    with app.app_context():
        record = MaintenanceRecord(
            valve_id=test_valve.id,
            设备位号="TEST-001",
            设备名称="测试阀门",
            检修内容="测试检修",
            created_by=employee_user.id
        )
        db.session.add(record)
        db.session.commit()
        yield record
