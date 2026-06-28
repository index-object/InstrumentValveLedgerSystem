"""删除 shaft_instruments 表"""
from app import create_app
from app.models import db

app = create_app()
with app.app_context():
    if db.engine.dialect.has_table(db.engine, "shaft_instruments"):
        db.engine.execute("DROP TABLE IF EXISTS shaft_instruments")
        print("已删除 shaft_instruments 表")
    else:
        print("shaft_instruments 表不存在，跳过")
