# 台账合集审批状态快照功能实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在Ledger模型中新增审批快照字段，实现"本账号修改后自己可见草稿，全部台账仍显示已审批"

**Architecture:** 通过在Ledger表中新增`approved_snapshot_status`和`approved_snapshot_at`字段，记录审批通过时的快照状态；列表查询时区分员工视角（读快照）和创建者视角（读实时状态）

**Tech Stack:** Python/Flask, SQLAlchemy, SQLite

---

### Task 1: 添加Ledger模型字段

**Files:**
- Modify: `app/models.py:31-53`

**Step 1: 在Ledger模型中添加新字段**

打开文件 `app/models.py`，在第53行（approver关系之前）添加新字段：

```python
    # 审批快照状态
    approved_snapshot_status = db.Column(db.String(20), nullable=True)  # 快照状态
    approved_snapshot_at = db.Column(db.DateTime, nullable=True)  # 快照生成时间
```

**Step 2: 验证模型定义**

运行: `python -c "from app.models import Ledger; print('Ledger fields:', [c.name for c in Ledger.__table__.columns])"`

**Step 3: 创建数据库迁移**

运行: `flask db migrate -m "add approved_snapshot fields to Ledger"`

---

### Task 2: 修改update_ledger_status函数生成快照

**Files:**
- Modify: `app/routes/ledgers.py:31-39`

**Step 1: 更新update_ledger_status函数**

将现有函数替换为：

```python
def update_ledger_status(ledger):
    total = Valve.query.filter_by(ledger_id=ledger.id).count()
    if total == 0:
        return
    
    approved = Valve.query.filter_by(ledger_id=ledger.id, status="approved").count()
    pending = Valve.query.filter_by(ledger_id=ledger.id, status="pending").count()
    rejected = Valve.query.filter_by(ledger_id=ledger.id, status="rejected").count()
    draft = Valve.query.filter_by(ledger_id=ledger.id, status="draft").count()
    
    if pending > 0:
        ledger.status = "pending"
    elif rejected > 0:
        ledger.status = "rejected"
    elif draft > 0:
        ledger.status = "draft"
    elif approved == total:
        ledger.status = "approved"
        ledger.approved_at = datetime.utcnow()
        
        # 生成快照：只有全部审批通过时才生成快照
        ledger.approved_snapshot_status = "approved"
        ledger.approved_snapshot_at = datetime.utcnow()
```

**Step 2: 验证函数逻辑**

运行: `python -c "from app.routes.ledgers import update_ledger_status; print('Function loaded successfully')"`

---

### Task 3: 修改全部台账列表查询逻辑

**Files:**
- Modify: `app/routes/ledgers.py:59-103`

**Step 1: 更新list函数中的状态过滤逻辑**

在第68-73行，将员工状态过滤逻辑修改为：

```python
    status = request.args.get("status")
    if status:
        # 领导/管理员：按实时status过滤
        if current_user.role in ["leader", "admin"]:
            query = query.filter(Ledger.status == status)
        else:
            # 员工：按快照状态过滤
            query = query.filter(Ledger.approved_snapshot_status == status)
    else:
        # 默认：员工只显示快照为approved的
        if current_user.role == "employee":
            query = query.filter(Ledger.approved_snapshot_status == "approved")
```

**Step 2: 更新display_status计算逻辑**

在第77-101行，修改display_status计算逻辑：

```python
    for ledger in ledgers_list:
        ledger.valve_count = Valve.query.filter_by(ledger_id=ledger.id).count()
        ledger.pending_count = Valve.query.filter_by(
            ledger_id=ledger.id, status="pending"
        ).count()
        ledger.rejected_count = Valve.query.filter_by(
            ledger_id=ledger.id, status="rejected"
        ).count()
        ledger.approved_count = Valve.query.filter_by(
            ledger_id=ledger.id, status="approved"
        ).count()
        ledger.draft_count = Valve.query.filter_by(
            ledger_id=ledger.id, status="draft"
        ).count()

        # 显示状态：创建者/领导/管理员看实时状态，其他人看快照状态
        is_owner = ledger.created_by == current_user.id or current_user.role in ["leader", "admin"]
        
        if is_owner:
            # 自己查看：使用实时状态
            if ledger.pending_count > 0:
                ledger.display_status = "pending"
            elif ledger.rejected_count > 0:
                ledger.display_status = "rejected"
            elif ledger.approved_count > 0 and ledger.approved_count == ledger.valve_count:
                ledger.display_status = "approved"
            elif ledger.valve_count > 0:
                ledger.display_status = "draft"
            else:
                ledger.display_status = "draft"
        else:
            # 他人查看：使用快照状态
            ledger.display_status = ledger.approved_snapshot_status or "draft"
```

---

### Task 4: 修改Ledger详情页显示逻辑

**Files:**
- Modify: `app/routes/ledgers.py:126-157`

**Step 1: 在detail函数中添加快照状态判断**

在第156行之后（db.session.commit()之前）添加：

```python
    # 判断查看者身份，用于模板显示
    ledger.is_owner = ledger.created_by == current_user.id or current_user.role in ["leader", "admin"]
    
    if ledger.is_owner:
        # 本人查看：使用实时状态
        if ledger.pending_count > 0:
            ledger.display_status = "pending"
        elif ledger.rejected_count > 0:
            ledger.display_status = "rejected"
        elif ledger.approved_count > 0 and ledger.approved_count == ledger.valve_count:
            ledger.display_status = "approved"
        elif ledger.valve_count > 0:
            ledger.display_status = "draft"
        else:
            ledger.display_status = "draft"
    else:
        # 他人查看：使用快照状态
        ledger.display_status = ledger.approved_snapshot_status or "draft"
```

---

### Task 5: 数据迁移脚本

**Files:**
- Create: `scripts/migrate_ledger_snapshot.py`

**Step 1: 编写迁移脚本**

```python
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
        # 查找所有status为approved且快照为空的Ledger
        ledgers = Ledger.query.filter(
            Ledger.status == "approved",
            Ledger.approved_snapshot_status.is_(None)
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
```

**Step 2: 运行迁移脚本**

运行: `python scripts/migrate_ledger_snapshot.py`

预期输出: "Migration complete!"

---

### Task 6: 验证功能

**Step 1: 启动应用测试**

运行: `flask run`

**Step 2: 验证场景**
1. 用员工账号创建一个Ledger，添加几个Valve
2. 提交审批，用领导账号审批通过
3. 验证「全部台账」显示为"已审批"
4. 用创建者账号修改任意已审批的Valve
5. 验证「我的台账」显示为"草稿"
6. 验证「全部台账」仍显示为"已审批"

---

### Task 7: 提交代码

运行: `git add -A && git commit -m "feat: 添加Ledger审批快照功能，实现修改后本账号显示草稿、全部台账显示已审批"`

---
