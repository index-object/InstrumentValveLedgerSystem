from app import create_app, db
from app.models import User, Setting

app = create_app()
with app.app_context():
    db.create_all()

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
    print("初始化完成!")
    print("管理员: admin / admin123")
    print("领导: leader / leader123")
    print("员工: user1 / user123")
