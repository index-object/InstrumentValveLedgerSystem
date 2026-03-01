# Ledger权限重构实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 重构Ledger权限逻辑，实现审批中心，普通员工只能看到已审批快照数据

**Architecture:** 修改查询逻辑增加快照时间过滤，新增审批中心路由和模板，移除详情页审批按钮

**Tech Stack:** Flask, SQLAlchemy, Jinja2

---

## Task 1: 修改普通员工Valve查询逻辑

**Files:**
- Modify: `app/routes/ledgers.py:269-276`

**Step 1: 分析现有代码**

当前普通员工查看Ledger时，Valve查询逻辑为：
```python
if (
    from_param != "mine"
    and ledger.created_by != current_user.id
    and current_user.role == "employee"
):
    query = query.filter(Valve.status == "approved")
```

**Step 2: 修改为基于快照时间过滤**

```python
if (
    from_param != "mine"
    and ledger.created_by != current_user.id
    and current_user.role == "employee"
):
    # 只显示已审批且在快照时间点之前的Valve
    if ledger.approved_snapshot_at:
        query = query.filter(
            Valve.status == "approved",
            Valve.approved_at <= ledger.approved_snapshot_at
        )
    else:
        query = query.filter(Valve.status == "approved")
```

**Step 3: 提交**

```bash
git add app/routes/ledgers.py
git commit -m "refactor: 普通员工Valve查询增加快照时间过滤"
```

---

## Task 2: 创建审批中心路由文件

**Files:**
- Create: `app/routes/approvals.py`

**Step 1: 创建审批中心蓝图**

```python
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app.models import db, Ledger, Valve, ApprovalLog
from app.routes.valves.permissions import require_leader
from datetime import datetime

approvals = Blueprint("approvals", __name__)


@approvals.route("/approvals")
@login_required
@require_leader
def index():
    tab = request.args.get("tab", "pending")
    
    if tab == "pending":
        ledgers = Ledger.query.join(Valve).filter(
            Valve.status == "pending"
        ).distinct().order_by(Ledger.created_at.desc()).all()
    elif tab == "approved":
        ledgers = Ledger.query.filter(
            Ledger.approved_snapshot_status == "approved"
        ).order_by(Ledger.created_at.desc()).all()
    elif tab == "rejected":
        ledgers = Ledger.query.join(Valve).filter(
            Valve.status == "rejected"
        ).distinct().order_by(Ledger.created_at.desc()).all()
    
    for ledger in ledgers:
        ledger.pending_count = Valve.query.filter_by(
            ledger_id=ledger.id, status="pending"
        ).count()
        ledger.approved_count = Valve.query.filter_by(
            ledger_id=ledger.id, status="approved"
        ).count()
        ledger.rejected_count = Valve.query.filter_by(
            ledger_id=ledger.id, status="rejected"
        ).count()
    
    return render_template("approvals/index.html", ledgers=ledgers, tab=tab)


@approvals.route("/approvals/batch-approve", methods=["POST"])
@login_required
@require_leader
def batch_approve():
    ledger_ids = request.form.getlist("ledger_ids")
    comment = request.form.get("comment", "")
    
    approved_count = 0
    for ledger_id in ledger_ids:
        ledger = Ledger.query.get(ledger_id)
        if not ledger:
            continue
            
        pending_valves = Valve.query.filter_by(
            ledger_id=ledger_id, 
            status="pending"
        ).all()
        
        for valve in pending_valves:
            valve.status = "approved"
            valve.approved_by = current_user.id
            valve.approved_at = datetime.utcnow()
            
            log = ApprovalLog(
                ledger_id=ledger.id,
                valve_id=valve.id,
                action="approve",
                user_id=current_user.id,
                comment=comment,
            )
            db.session.add(log)
            approved_count += 1
        
        # 更新Ledger状态
        total = Valve.query.filter_by(ledger_id=ledger_id).count()
        approved = Valve.query.filter_by(ledger_id=ledger_id, status="approved").count()
        
        if approved == total and total > 0:
            ledger.status = "approved"
            ledger.approved_snapshot_status = "approved"
            ledger.approved_snapshot_at = datetime.utcnow()
        elif approved > 0:
            ledger.status = "approved"
        
        db.session.commit()
    
    flash(f"已审批 {approved_count} 项台账内容")
    return redirect(url_for("approvals.index"))


@approvals.route("/approvals/batch-reject", methods=["POST"])
@login_required
@require_leader
def batch_reject():
    ledger_ids = request.form.getlist("ledger_ids")
    comment = request.form.get("comment", "")
    
    rejected_count = 0
    for ledger_id in ledger_ids:
        ledger = Ledger.query.get(ledger_id)
        if not ledger:
            continue
            
        pending_valves = Valve.query.filter_by(
            ledger_id=ledger_id, 
            status="pending"
        ).all()
        
        for valve in pending_valves:
            valve.status = "rejected"
            
            log = ApprovalLog(
                ledger_id=ledger.id,
                valve_id=valve.id,
                action="reject",
                user_id=current_user.id,
                comment=comment,
            )
            db.session.add(log)
            rejected_count += 1
        
        ledger.status = "rejected"
        db.session.commit()
    
    flash(f"已驳回 {rejected_count} 项台账内容")
    return redirect(url_for("approvals.index"))
```

**Step 2: 在主应用注册蓝图**

Modify: `main.py` 或 `app/__init__.py`

```python
from app.routes.approvals import approvals
app.register_blueprint(approvals)
```

**Step 3: 提交**

```bash
git add app/routes/approvals.py
git commit -m "feat: 添加审批中心路由"
```

---

## Task 3: 创建审批中心模板

**Files:**
- Create: `templates/approvals/index.html`

**Step 1: 创建审批中心页面**

参考现有模板结构创建，包含三个Tab切换和批量操作按钮。

**Step 2: 提交**

```bash
git add templates/approvals/index.html
git commit -m "feat: 添加审批中心页面模板"
```

---

## Task 4: 修改侧边栏菜单

**Files:**
- Modify: `templates/base.html`

**Step 1: 在侧边栏添加审批中心菜单**

```html
{% if current_user.role in ['leader', 'admin'] %}
<li>
    <a href="{{ url_for('approvals.index') }}">
        <i class="fa fa-check-circle"></i> 审批中心
    </a>
</li>
{% endif %}
```

**Step 2: 提交**

```bash
git add templates/base.html
git commit -m "feat: 侧边栏添加审批中心入口"
```

---

## Task 5: 移除Ledger详情页审批按钮

**Files:**
- Modify: `templates/ledgers/detail.html`

**Step 1: 移除审批相关按钮**

找到并删除：
- 批量审批按钮
- 批量驳回按钮
- 提交审批按钮（仅保留给创建者）

**Step 2: 提交**

```bash
git add templates/ledgers/detail.html
git commit -m "refactor: 移除Ledger详情页审批按钮"
```

---

## Task 6: 测试验证

**Step 1: 使用不同角色测试**

1. 使用admin/leader账号登录
   - 访问 `/approvals` 查看审批中心
   - 测试待审批/已审批/已驳回三个Tab
   - 测试批量审批/驳回功能

2. 使用employee账号登录
   - 访问 `/ledgers` 确认只显示已审批Ledger
   - 进入已审批Ledger，确认只看到已审批Valve

3. 测试快照功能
   - 用employee账号创建Ledger并完全审批
   - 用admin账号在已审批Ledger中新增待审批Valve
   - 确认employee账号仍能查看原快照数据

**Step 2: 提交**

```bash
git commit -m "test: 添加权限和审批功能测试"
```

---

## 计划完成

**执行方式：**
1. Subagent-Driven - 本会话中逐个执行任务
2. Parallel Session - 新开会话批量执行

请选择执行方式。
