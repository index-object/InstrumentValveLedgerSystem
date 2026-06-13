from app import create_app, db, init_seed_data

app = create_app()
with app.app_context():
    db.create_all()
    init_seed_data()
    print("初始化完成!")
    print("管理员: admin / admin123")
    print("领导: leader / leader123")
    print("员工: user1 / user123")
