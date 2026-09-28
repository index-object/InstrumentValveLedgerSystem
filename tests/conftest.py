import sys
import os
import shutil
import tempfile
import atexit

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from app import create_app, db
from app.models import User, Ledger, MaintenanceRecord, Setting

# 测试必须使用独立数据库，绝不能碰项目根目录的 valves.db。
# create_app() 内部会 from_object(Config) 并读取 SQLALCHEMY_DATABASE_URI，
# 因此 URI 必须在 create_app 之前通过 config_class 指定——在创建之后
# 修改 app.config 是无效的，那样 db.create_all()/drop_all() 会直接作用于
# 真实数据库并清空它。
_TEST_DB_FD, _TEST_DB_PATH = tempfile.mkstemp(prefix="valves-test-", suffix=".db")
os.close(_TEST_DB_FD)
atexit.register(lambda: os.path.exists(_TEST_DB_PATH) and os.remove(_TEST_DB_PATH))

# 上传目录同理：测试上传的文件（含导入中间数据）必须落在临时目录，
# 不能写进项目真实的 uploads/，否则每跑一次测试就多一批残留文件。
_TEST_UPLOAD_DIR = tempfile.mkdtemp(prefix="valves-test-uploads-")
atexit.register(lambda: shutil.rmtree(_TEST_UPLOAD_DIR, ignore_errors=True))


def _build_test_config_class():
    from config import Config

    class TestConfig(Config):
        TESTING = True
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + _TEST_DB_PATH
        WTF_CSRF_ENABLED = False
        UPLOAD_FOLDER = _TEST_UPLOAD_DIR

    return TestConfig


@pytest.fixture(scope="session")
def app():
    """整个测试会话共用一个 app 与一个临时数据库。

    必须是会话级：db 是模块级单例，若按函数反复 create_app()，
    同一个测试内多个 fixture 依赖 app 时会重复 init_app 并争抢文件库，
    表现为 sqlite "database is locked"。表结构只建一次，数据在
    init_database fixture 中按用例清空。
    """
    app = create_app(_build_test_config_class())

    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def restore_upload_folder(app):
    """用例里可能临时改写 UPLOAD_FOLDER（如导出/导入用例）指向自己的 tmp_path，
    这些目录在用例结束后会被删掉。app 是会话级的，不还原就会让后面的用例
    把文件写进已删除的目录。"""
    original = app.config.get("UPLOAD_FOLDER")
    yield
    app.config["UPLOAD_FOLDER"] = original


@pytest.fixture(autouse=True)
def clean_db(app):
    """每个用例开始前清空全部业务表，保证用例之间互不影响。

    会话级 app 让表结构只建一次，数据隔离靠这里完成。
    """
    with app.app_context():
        _clear_all_rows()
    yield


def _clear_all_rows():
    """清空全部业务表，保证用例之间互不影响（保留表结构）"""
    from app.models import (
        User, Ledger, MaintenanceRecord, Setting, SheetMapping, Notification,
        MaintenancePlan, MaintenancePlanGroup, MaintenancePlanItem, PlanRecipient,
        ValveAttachment, ValvePhoto, ValveDocument, ValveFile, ApprovalLog,
    )
    from app.devices import DeviceTypeRegistry

    models = [
        MaintenancePlanItem, MaintenancePlanGroup, PlanRecipient, MaintenancePlan,
        Notification, MaintenanceRecord, ApprovalLog, ValveAttachment, ValvePhoto,
        ValveDocument, ValveFile, SheetMapping, Ledger, Setting, User,
    ]
    for config in DeviceTypeRegistry.all():
        if config.model_class:
            models.insert(0, config.model_class)

    for model in models:
        try:
            db.session.query(model).delete()
        except Exception:
            db.session.rollback()
    db.session.commit()


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
