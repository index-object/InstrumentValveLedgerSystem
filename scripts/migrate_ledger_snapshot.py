#!/usr/bin/env python
"""为现有已审批的Ledger生成审批快照"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db, Ledger


def migrate_approved_snapshots():
    app = create_app()
    with app.app_context():
        ledgers = Ledger.query.filter(
            Ledger.status == "approved", Ledger.approved_snapshot_status.is_(None)
        ).all()

        print(f"Found {len(ledgers)} ledgers to migrate")

        for ledger in ledgers:
            ledger.approved_snapshot_status = "approved"
            ledger.approved_snapshot_at = ledger.approved_at
            print(f"  Migrated ledger: {ledger.名称} (ID: {ledger.id})")

        db.session.commit()
        print("Migration complete!")


if __name__ == "__main__":
    migrate_approved_snapshots()
