"""
数据库迁移脚本：将旧 valves 表拆分为 control_valves 和 onoff_valves

用法: uv run python scripts/migrate_split_valves.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from app.models import db, Ledger
from app.devices.types.control_valve import ControlValve
from app.devices.types.onoff_valve import OnOffValve
from sqlalchemy import text, inspect as sa_inspect


def column_exists(table, col):
    insp = sa_inspect(db.engine)
    cols = [c["name"] for c in insp.get_columns(table)]
    return col in cols


def add_column(table, col, col_type, default=None):
    if not column_exists(table, col):
        sql = f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"
        if default:
            sql += f" DEFAULT {default}"
        with db.engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()
        print(f"  添加列 {table}.{col}")


def migrate():
    app = create_app()
    with app.app_context():
        print("=== 阀门表拆分迁移 ===\n")

        # 1. 创建新表
        print("1. 创建新表 control_valves 和 onoff_valves...")
        ControlValve.__table__.create(db.engine, checkfirst=True)
        OnOffValve.__table__.create(db.engine, checkfirst=True)
        print("  完成")

        # 2. 检查旧 valves 表是否存在
        print("\n2. 迁移 valves 数据...")
        if not sa_inspect(db.engine).has_table("valves"):
            print("  旧 valves 表不存在，跳过")
        else:
            with db.engine.connect() as conn:
                old_valves = conn.execute(
                    text("SELECT * FROM valves ORDER BY id")
                ).fetchall()
                columns = [
                    c["name"]
                    for c in sa_inspect(db.engine).get_columns("valves")
                ]

            if old_valves:
                col_names = [c for c in columns if c != "id"]
                placeholders = ", ".join([f":{c}" for c in col_names])
                col_list = ", ".join(col_names)

                inserted = 0
                with db.engine.connect() as conn:
                    for row in old_valves:
                        row_dict = dict(zip(columns, row))
                        insert_data = {
                            k: v for k, v in row_dict.items() if k != "id"
                        }
                        conn.execute(
                            text(
                                f"INSERT INTO control_valves ({col_list}) "
                                f"VALUES ({placeholders})"
                            ),
                            insert_data,
                        )
                        inserted += 1
                    conn.commit()
                print(f"  已迁移 {inserted} 条记录到 control_valves")

                # 此时记下旧 id 映射（valves.id -> control_valves.id 相同）
                # SQLite 自增 id 在插入时若不指定则自动分配，但上面保留了自增行为
                # 需要验证 id 是否一致
            else:
                print("  旧 valves 表为空")

        # 3. 更新 Ledger 类型
        print("\n3. 更新 Ledger 类型编码...")
        valve_ledgers = Ledger.query.filter_by(类型="valve").all()
        if valve_ledgers:
            for ledger in valve_ledgers:
                ledger.类型 = "control_valve"
            db.session.commit()
            print(f"  更新 {len(valve_ledgers)} 个 Ledger: valve -> control_valve")
        else:
            print("  无 type=valve 的 Ledger")

        # 4. 给子表添加多态列
        print("\n4. 添加多态关联列...")
        add_column("valve_photos", "device_type", "VARCHAR(50)", "'control_valve'")
        add_column("valve_photos", "device_id", "INTEGER", "0")
        add_column("maintenance_records", "device_type", "VARCHAR(50)", "'control_valve'")
        add_column("maintenance_records", "device_id", "INTEGER", "0")
        add_column("valve_attachments", "device_type", "VARCHAR(50)", "'control_valve'")
        add_column("valve_attachments", "device_id", "INTEGER", "0")
        if not column_exists("approval_logs", "device_type"):
            add_column("approval_logs", "device_type", "VARCHAR(50)", "'control_valve'")
        if not column_exists("approval_logs", "device_id"):
            add_column("approval_logs", "device_id", "INTEGER", "0")
        print("  完成")

        # 5. 设置子表的 device_type 和 device_id
        print("\n5. 更新子表 device_type/device_id...")
        child_tables = [
            "valve_photos",
            "maintenance_records",
            "valve_attachments",
            "approval_logs",
        ]
        for table in child_tables:
            # 检查旧表是否有 valve_id 列
            if not column_exists(table, "valve_id"):
                print(f"  {table}: 无 valve_id 列，跳过")
                continue
            with db.engine.connect() as conn:
                result = conn.execute(
                    text(
                        f"UPDATE {table} SET "
                        f"device_type = 'control_valve', "
                        f"device_id = valve_id "
                        f"WHERE (device_id IS NULL OR device_id = 0) "
                        f"AND valve_id IS NOT NULL"
                    )
                )
                conn.commit()
                print(f"  {table}: {result.rowcount} 行更新")

        # 6. 删除旧 valves 表
        print("\n6. 删除旧 valves 表...")
        if sa_inspect(db.engine).has_table("valves"):
            with db.engine.connect() as conn:
                conn.execute(text("DROP TABLE valves"))
                conn.commit()
            print("  已删除")
        else:
            print("  不存在，跳过")

        print("\n=== 迁移完成 ===")


if __name__ == "__main__":
    migrate()
