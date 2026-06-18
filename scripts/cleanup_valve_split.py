"""
清理拆分迁移后的残留数据，为重新导入做准备
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from app.models import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    print("=== 清理阀门数据 ===")

    # 1. 清空 control_valves
    deleted = db.session.execute(text("DELETE FROM control_valves"))
    db.session.commit()
    print(f"  已清空 control_valves: {deleted.rowcount} 行删除")

    # 2. 重置子表的 control_valve 关联
    for table in ["valve_photos", "maintenance_records", "valve_attachments"]:
        result = db.session.execute(
            text(f"UPDATE {table} SET device_type = '', device_id = NULL WHERE device_type = 'control_valve'")
        )
        db.session.commit()
        print(f"  已重置 {table}: {result.rowcount} 行")

    # 3. 重置 approval_logs（保留非 control_valve 的记录）
    result = db.session.execute(
        text("UPDATE approval_logs SET device_type = '', device_id = NULL WHERE device_type = 'control_valve'")
    )
    db.session.commit()
    print(f"  已重置 approval_logs: {result.rowcount} 行")

    # 4. 将 Ledger 类型改回 valve？（保持 control_valve 不变，新导入会直接用 control_valve 类型）
    # 但导入程序会检查 Ledger.类型 是否匹配，所以保持 control_valve 没问题

    print("\n=== 清理完成，可以重新导入 ===")
