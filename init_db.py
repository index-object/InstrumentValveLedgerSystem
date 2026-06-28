from app import create_app, db, init_seed_data

app = create_app()
with app.app_context():
    db.create_all()
    init_seed_data()
    print("初始化完成!")
    print("管理员: admin / admin123")
    print("领导: ld001 / ld001")
    print("普通用户: 化工班 / 111")
    print("普通用户: 动力班 / 222")
