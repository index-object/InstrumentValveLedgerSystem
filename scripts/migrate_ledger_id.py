"""清理独立台账，添加 ledger 统计字段"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db, Ledger, Valve

app = create_app()
with app.app_context():
    # 1. 删除所有没有 ledger_id 的独立 Valve
    deleted = Valve.query.filter(Valve.ledger_id.is_(None)).delete()
    print(f"Deleted {deleted} independent valves")

    # 2. 更新所有 Ledger 的 valve_count 和 pending_count
    ledgers = Ledger.query.all()
    for ledger in ledgers:
        ledger.valve_count = Valve.query.filter_by(ledger_id=ledger.id).count()
        ledger.pending_count = Valve.query.filter_by(
            ledger_id=ledger.id, status="pending"
        ).count()

    db.session.commit()
    print("Ledger counts updated")
