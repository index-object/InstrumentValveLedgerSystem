# 台账集合批量保存与审批重构实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将现有的单个台账保存草稿→提交审批流程改为台账集合批量管理模式，强制所有台账必须属于某个集合。

**Architecture:** 
- 数据模型：Ledger 添加 valve_count, pending_count 字段，Valve 强制绑定 ledger_id
- 路由：移除独立台账入口 /valves/*，统一到 /ledger/* 
- 状态：Ledger 与 Valve 状态强绑定，一致性校验

**Tech Stack:** Flask, SQLAlchemy, Flask-Login, Bootstrap 5

---

## Task 1: 修改 Ledger 模型，添加统计字段

**Files:**
- Modify: `app/models.py:31-51`

**Step 1: 添加 Ledger 模型字段**

在 Ledger 类中添加 valve_count 和 pending_count 字段：

```python
class Ledger(db.Model):
    __tablename__ = "ledgers"
    id = db.Column(db.Integer, primary_key=True)

    名称 = db.Column(db.String(100), nullable=False)
    描述 = db.Column(db.Text)

    status = db.Column(db.String(20), default="draft")

    # 新增字段
    valve_count = db.Column(db.Integer, default=0)
    pending_count = db.Column(db.Integer, default=0)

    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    approved_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    approved_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    creator = db.relationship("User", foreign_keys=[created_by])
    approver = db.relationship("User", foreign_keys=[approved_by])
    valves = db.relationship("Valve", backref="ledger", lazy="dynamic")
```

**Step 2: 验证模型**

运行：`python -c "from app.models import Ledger, Valve; print('OK')"`

---

## Task 2: 修改 Valve 模型，添加 ledger_id 约束

**Files:**
- Modify: `app/models.py:53-112`

**Step 1: 修改 Valve.ledger_id 为必填**

找到 Valve 模型定义，将 ledger_id 改为 nullable=False：

```python
ledger_id = db.Column(db.Integer, db.ForeignKey("ledgers.id"), nullable=False)
```

---

## Task 3: 创建数据库迁移脚本

**Files:**
- Create: `migrations/versions/001_add_ledger_counts.py`

**Step 1: 创建迁移脚本**

```python
"""add ledger valve_count and pending_count"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('ledgers', sa.Column('valve_count', sa.Integer(), default=0))
    op.add_column('ledgers', sa.Column('pending_count', sa.Integer(), default=0))
    # 将 ledger_id 改为必填需要处理现有数据
    # 先给所有没有 ledger_id 的 Valve 分配一个默认 Ledger，或者删除它们

def downgrade():
    op.drop_column('ledgers', 'pending_count')
    op.drop_column('ledgers', 'valve_count')
```

**Step 2: 由于使用 SQLite，简单起见直接在 init_db.py 或新脚本中处理**

创建：`scripts/migrate_ledger_id.py`

```python
"""清理独立台账，添加 ledger 统计字段"""
from app import create_app
from app.models import db, Ledger, Valve

app = create_app()
with app.app_context():
    # 1. 删除所有没有 ledger_id 的独立 Valve
    deleted = Valve.query.filter(Valve.ledger_id.is_(None)).delete()
    print(f"Deleted {deleted} independent valves")
    
    # 2. 更新所有 Ledger 的 valve_count
    ledgers = Ledger.query.all()
    for ledger in ledgers:
        ledger.valve_count = Valve.query.filter_by(ledger_id=ledger.id).count()
        ledger.pending_count = Valve.query.filter_by(
            ledger_id=ledger.id, status="pending"
        ).count()
    
    db.session.commit()
    print("Ledger counts updated")
```

---

## Task 4: 修改 ledgers.py 路由 - 添加批量保存功能

**Files:**
- Modify: `app/routes/ledgers.py`

**Step 1: 添加批量保存台账 API**

在 ledgers.py 中添加新的路由函数：

```python
@ledgers.route("/ledger/<int:id>/valve/batch-save", methods=["POST"])
@login_required
def batch_save_valve(id):
    """批量保存台账（JSON 格式）"""
    ledger = Ledger.query.get_or_404(id)
    
    if not can_edit_ledger(ledger):
        return jsonify({"success": False, "message": "无权操作"}), 403
    
    if ledger.status != "draft":
        return jsonify({"success": False, "message": "当前状态无法编辑"}), 400
    
    data = request.get_json()
    if not data or not isinstance(data, list):
        return jsonify({"success": False, "message": "无效数据格式"})
    
    saved_ids = []
    errors = []
    
    for item in data:
        valve_id = item.get("id")
        form_data = item.get("data", {})
        
        if valve_id:
            # 更新现有台账
            valve = Valve.query.get(valve_id)
            if not valve or valve.ledger_id != id:
                errors.append({"id": valve_id, "error": "台账不存在"})
                continue
            
            if valve.status not in ["draft", "rejected"]:
                errors.append({"id": valve_id, "error": "当前状态无法编辑"})
                continue
        else:
            # 创建新台账
            valve = Valve()
            valve.ledger_id = id
            valve.created_by = current_user.id
            valve.status = "draft"
            db.session.add(valve)
        
        # 更新台账字段
        for key, value in form_data.items():
            if hasattr(valve, key):
                setattr(valve, key, value)
        
        saved_ids.append(valve.id)
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    
    # 更新 Ledger 统计
    ledger.valve_count = Valve.query.filter_by(ledger_id=id).count()
    db.session.commit()
    
    return jsonify({
        "success": True, 
        "saved_ids": saved_ids,
        "errors": errors
    })
```

**Step 2: 添加 jsonify 导入**

在 ledgers.py 顶部添加：

```python
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    jsonify,  # 添加这行
)
```

---

## Task 5: 修改提交审批逻辑 - 支持部分提交

**Files:**
- Modify: `app/routes/ledgers.py:265-287`

**Step 1: 修改 submit 函数**

原逻辑是提交所有 draft 台账，改为可选的批量提交：

```python
@ledgers.route("/ledger/<int:id>/submit", methods=["POST"])
@login_required
def submit(id):
    ledger = Ledger.query.get_or_404(id)

    if not can_edit_ledger(ledger):
        flash("无权操作")
        return redirect(url_for("ledgers.list"))

    # 支持部分提交：从前端选择要提交的台账
    valve_ids = request.form.getlist("valve_ids")
    
    if valve_ids:
        # 部分提交
        submit_valves = Valve.query.filter(
            Valve.id.in_(valve_ids),
            Valve.ledger_id == id,
            Valve.status == "draft"
        ).all()
    else:
        # 全部提交（兼容原有行为）
        submit_valves = Valve.query.filter_by(
            ledger_id=id, status="draft"
        ).all()
    
    if not submit_valves:
        flash("没有可提交的台账")
        return redirect(url_for("ledgers.detail", id=id))
    
    for valve in submit_valves:
        valve.status = "pending"
        log = ApprovalLog(
            ledger_id=ledger.id,
            valve_id=valve.id,
            action="submit",
            user_id=current_user.id,
        )
        db.session.add(log)
    
    # 更新 Ledger 状态和统计
    ledger.status = "pending"
    ledger.pending_count = len(submit_valves)
    
    db.session.commit()

    flash(f"已提交 {len(submit_valves)} 项台账内容审批")
    return redirect(url_for("ledgers.detail", id=id))
```

---

## Task 6: 修改审批通过逻辑 - 批量审批

**Files:**
- Modify: `app/routes/ledgers.py:290-320`

**Step 1: 修改 approve 函数**

```python
@ledgers.route("/ledger/<int:id>/approve", methods=["POST"])
@login_required
def approve(id):
    if current_user.role not in ["leader", "admin"]:
        flash("需要领导权限")
        return redirect(url_for("ledgers.list"))

    ledger = Ledger.query.get_or_404(id)

    # 审批所有 pending 状态的台账
    pending_valves = Valve.query.filter_by(ledger_id=id, status="pending").all()
    
    if not pending_valves:
        flash("没有待审批的台账")
        return redirect(url_for("ledgers.detail", id=id))
    
    for valve in pending_valves:
        valve.status = "approved"
        valve.approved_by = current_user.id
        valve.approved_at = datetime.utcnow()
        log = ApprovalLog(
            ledger_id=ledger.id,
            valve_id=valve.id,
            action="approve",
            user_id=current_user.id,
            comment=request.form.get("comment", ""),
        )
        db.session.add(log)

    # 更新 Ledger 状态
    ledger.status = "approved"
    ledger.approved_by = current_user.id
    ledger.approved_at = datetime.utcnow()
    ledger.pending_count = 0

    db.session.commit()

    flash(f"已审批通过，共 {len(pending_valves)} 项台账内容")
    return redirect(url_for("ledgers.detail", id=id))
```

---

## Task 7: 修改审批驳回逻辑 - 批量驳回

**Files:**
- Modify: `app/routes/ledgers.py:323-349`

**Step 1: 修改 reject 函数**

```python
@ledgers.route("/ledger/<int:id>/reject", methods=["POST"])
@login_required
def reject(id):
    if current_user.role not in ["leader", "admin"]:
        flash("需要领导权限")
        return redirect(url_for("ledgers.list"))

    ledger = Ledger.query.get_or_404(id)

    # 驳回所有 pending 状态的台账
    pending_valves = Valve.query.filter_by(ledger_id=id, status="pending").all()
    
    if not pending_valves:
        flash("没有待审批的台账")
        return redirect(url_for("ledgers.detail", id=id))
    
    for valve in pending_valves:
        valve.status = "rejected"
        log = ApprovalLog(
            ledger_id=ledger.id,
            valve_id=valve.id,
            action="reject",
            user_id=current_user.id,
            comment=request.form.get("comment", ""),
        )
        db.session.add(log)

    # 更新 Ledger 状态
    ledger.status = "rejected"
    ledger.pending_count = 0

    db.session.commit()

    flash(f"已驳回，共 {len(pending_valves)} 项台账内容")
    return redirect(url_for("ledgers.detail", id=id))
```

---

## Task 8: 修改 detail 路由 - 更新统计

**Files:**
- Modify: `app/routes/ledgers.py:64-223`

**Step 1: 在 detail 视图函数中添加统计更新逻辑**

在 detail 函数开始处添加：

```python
@ledgers.route("/ledger/<int:id>", methods=["GET", "POST"])
@login_required
def detail(id):
    ledger = Ledger.query.get_or_404(id)
    
    # 更新统计（确保数据一致性）
    ledger.valve_count = Valve.query.filter_by(ledger_id=id).count()
    ledger.pending_count = Valve.query.filter_by(ledger_id=id, status="pending").count()
    db.session.commit()
    
    # ... 后续原有逻辑 ...
```

---

## Task 9: 修改台账创建逻辑 - 统计更新

**Files:**
- Modify: `app/routes/ledgers.py:352-405`

**Step 1: 修改 new_valve 函数**

在创建台账后更新 Ledger 统计：

```python
@ledgers.route("/ledger/<int:id>/valve/new", methods=["GET", "POST"])
@login_required
def new_valve(id):
    ledger = Ledger.query.get_or_404(id)

    if not can_edit_ledger(ledger):
        flash("无权操作")
        return redirect(url_for("ledgers.detail", id=id))

    if ledger.status != "draft":
        flash("当前状态无法添加台账")
        return redirect(url_for("ledgers.detail", id=id))

    if request.method == "POST":
        位号 = request.form.get("位号")
        if 位号:
            existing = Valve.query.filter(
                Valve.位号 == 位号, Valve.status != "draft"
            ).first()
            if existing:
                flash("位号已存在，请使用其他位号")
                return redirect(url_for("ledgers.new_valve", id=id))

        valve = Valve()
        for key in request.form:
            if key == "attachments":
                continue
            if hasattr(valve, key):
                setattr(valve, key, request.form.get(key))

        valve.ledger_id = id
        valve.created_by = current_user.id
        valve.status = "draft"

        try:
            db.session.add(valve)
            db.session.commit()
        except:
            db.session.rollback()
            flash("位号已存在，请使用其他位号")
            return redirect(url_for("ledgers.new_valve", id=id))

        # 更新 Ledger 统计
        ledger.valve_count = Valve.query.filter_by(ledger_id=id).count()
        db.session.commit()

        flash("添加成功")
        return redirect(url_for("ledgers.detail", id=id))

    return render_template("valves/form.html", valve=None, ledger=ledger)
```

---

## Task 10: 修改台账删除逻辑 - 统计更新

**Files:**
- Modify: `app/routes/ledgers.py:441-458`

**Step 1: 修改 delete_valve 函数**

```python
@ledgers.route("/ledger/<int:ledger_id>/valve/delete/<int:id>", methods=["POST"])
@login_required
def delete_valve(ledger_id, id):
    ledger = Ledger.query.get_or_404(ledger_id)
    valve = Valve.query.get_or_404(id)

    if not can_edit_ledger(ledger):
        flash("无权删除")
        return redirect(url_for("ledgers.detail", id=ledger_id))

    if valve.status not in ["draft", "rejected"]:
        flash("当前状态无法删除")
        return redirect(url_for("ledgers.detail", id=ledger_id))

    db.session.delete(valve)
    
    # 更新 Ledger 统计
    ledger.valve_count = Valve.query.filter_by(ledger_id=ledger_id).count()
    ledger.pending_count = Valve.query.filter_by(
        ledger_id=ledger_id, status="pending"
    ).count()
    
    db.session.commit()
    flash("删除成功")
    return redirect(url_for("ledgers.detail", id=ledger_id))
```

---

## Task 11: 批量删除台账 - 添加路由

**Files:**
- Modify: `app/routes/ledgers.py`

**Step 1: 添加批量删除路由**

```python
@ledgers.route("/ledger/<int:id>/valve/batch-delete", methods=["POST"])
@login_required
def batch_delete_valve(id):
    ledger = Ledger.query.get_or_404(id)
    
    if not can_edit_ledger(ledger):
        flash("无权操作")
        return redirect(url_for("ledgers.detail", id=id))
    
    if ledger.status != "draft":
        flash("当前状态无法删除")
        return redirect(url_for("ledgers.detail", id=id))
    
    valve_ids = request.form.getlist("valve_ids")
    if not valve_ids:
        flash("请选择要删除的台账")
        return redirect(url_for("ledgers.detail", id=id))
    
    # 只删除 draft 或 rejected 状态的台账
    deleted_count = Valve.query.filter(
        Valve.id.in_(valve_ids),
        Valve.ledger_id == id,
        Valve.status.in_(["draft", "rejected"])
    ).delete(synchronize_session=False)
    
    # 更新 Ledger 统计
    ledger.valve_count = Valve.query.filter_by(ledger_id=id).count()
    
    db.session.commit()
    flash(f"成功删除 {deleted_count} 项台账")
    return redirect(url_for("ledgers.detail", id=id))
```

---

## Task 12: 运行迁移脚本

**Step 1: 执行迁移**

```bash
python scripts/migrate_ledger_id.py
```

预期输出：
```
Deleted X independent valves
Ledger counts updated
```

---

## Task 13: 测试验证

**Step 1: 运行应用测试基本功能**

```bash
python main.py
```

访问 http://127.0.0.1:5000/ledgers 测试：
1. 创建新台账集合
2. 在集合内添加台账
3. 提交审批
4. 审批通过/驳回

**Step 2: 运行单元测试**

```bash
pytest
```

---

## Task 14: 提交代码

```bash
git add -A
git commit -m "refactor: 台账集合批量保存与审批重构

- Ledger 添加 valve_count, pending_count 字段
- Valve.ledger_id 改为必填
- 支持部分台账提交审批
- 批量审批/驳回功能
- 更新台账操作统计同步
- 清理独立台账数据"
```
