# 权限管理系统实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现细粒度权限控制系统，员工只能在「我的台账」中增删改查，领导只能审批不能编辑，维护记录按创建者限制。

**Architecture:** 采用权限检查函数集中管理，后端权限检查不依赖URL参数，前端通过权限变量控制按钮显示。

**Tech Stack:** Flask, Flask-Login, Jinja2, SQLAlchemy

---

## 文件结构

### 需要修改的文件

| 文件 | 职责 |
|------|------|
| `app/routes/valves/permissions.py` | 权限检查函数（核心） |
| `app/routes/ledgers.py` | 台账合集路由权限保护 |
| `app/routes/valves/__init__.py` | 阀门路由权限保护 |
| `app/routes/valves/attachments.py` | 维护记录路由权限保护 |
| `templates/valves/list.html` | 阀门列表按钮控制 |
| `templates/valves/detail.html` | 阀门详情按钮控制 |
| `templates/ledgers/list.html` | 台账列表按钮控制 |
| `templates/maintenance/list.html` | 维护记录按钮控制 |

### 需要创建的测试文件

| 文件 | 职责 |
|------|------|
| `tests/test_permissions.py` | 权限函数单元测试 |

---

## Task 1: 实现权限检查函数

**Files:**
- Modify: `app/routes/valves/permissions.py`
- Create: `tests/test_permissions.py`

### Step 1.1: 编写权限函数测试

- [ ] **编写测试：台账合集权限**

```python
# tests/test_permissions.py
import pytest
from flask_login import current_user
from app.routes.valves.permissions import (
    can_create_ledger,
    can_edit_ledger,
    can_delete_ledger,
    can_create_valve,
    can_edit_valve,
    can_delete_valve,
    can_submit_valve,
    can_approve_valve,
    can_create_maintenance,
    can_edit_maintenance,
    can_delete_maintenance,
)
from app.models import User, Ledger, Valve, MaintenanceRecord


class TestLedgerPermissions:
    """台账合集权限测试"""

    def test_employee_can_create_ledger(self, app, employee_user):
        """员工可以创建台账合集"""
        with app.test_request_context():
            from flask_login import login_user
            login_user(employee_user)
            assert can_create_ledger() is True

    def test_leader_cannot_create_ledger(self, app, leader_user):
        """领导不能创建台账合集"""
        with app.test_request_context():
            from flask_login import login_user
            login_user(leader_user)
            assert can_create_ledger() is False

    def test_admin_can_create_ledger(self, app, admin_user):
        """管理员可以创建台账合集"""
        with app.test_request_context():
            from flask_login import login_user
            login_user(admin_user)
            assert can_create_ledger() is True

    def test_employee_can_edit_own_ledger(self, app, employee_user, test_ledger):
        """员工可以编辑自己的台账合集"""
        with app.test_request_context():
            from flask_login import login_user
            login_user(employee_user)
            test_ledger.created_by = employee_user.id
            assert can_edit_ledger(test_ledger) is True

    def test_employee_cannot_edit_others_ledger(self, app, employee_user, test_ledger, other_user):
        """员工不能编辑他人的台账合集"""
        with app.test_request_context():
            from flask_login import login_user
            login_user(employee_user)
            test_ledger.created_by = other_user.id
            assert can_edit_ledger(test_ledger) is False

    def test_leader_cannot_edit_ledger(self, app, leader_user, test_ledger):
        """领导不能编辑台账合集"""
        with app.test_request_context():
            from flask_login import login_user
            login_user(leader_user)
            assert can_edit_ledger(test_ledger) is False


class TestValvePermissions:
    """阀门权限测试"""

    def test_employee_can_edit_own_valve_draft(self, app, employee_user, test_valve):
        """员工可以编辑自己的草稿阀门"""
        with app.test_request_context():
            from flask_login import login_user
            login_user(employee_user)
            test_valve.created_by = employee_user.id
            test_valve.status = 'draft'
            assert can_edit_valve(test_valve) is True

    def test_employee_cannot_edit_pending_valve(self, app, employee_user, test_valve):
        """员工不能编辑待审批状态的阀门"""
        with app.test_request_context():
            from flask_login import login_user
            login_user(employee_user)
            test_valve.created_by = employee_user.id
            test_valve.status = 'pending'
            assert can_edit_valve(test_valve) is False

    def test_leader_cannot_edit_valve(self, app, leader_user, test_valve):
        """领导不能编辑阀门"""
        with app.test_request_context():
            from flask_login import login_user
            login_user(leader_user)
            test_valve.status = 'draft'
            assert can_edit_valve(test_valve) is False

    def test_leader_can_approve_pending_valve(self, app, leader_user, test_valve):
        """领导可以审批待审批状态的阀门"""
        with app.test_request_context():
            from flask_login import login_user
            login_user(leader_user)
            test_valve.status = 'pending'
            assert can_approve_valve(test_valve) is True

    def test_leader_cannot_approve_draft_valve(self, app, leader_user, test_valve):
        """领导不能审批草稿状态的阀门"""
        with app.test_request_context():
            from flask_login import login_user
            login_user(leader_user)
            test_valve.status = 'draft'
            assert can_approve_valve(test_valve) is False


class TestMaintenancePermissions:
    """维护记录权限测试"""

    def test_employee_can_create_maintenance(self, app, employee_user):
        """员工可以创建维护记录"""
        with app.test_request_context():
            from flask_login import login_user
            login_user(employee_user)
            assert can_create_maintenance() is True

    def test_leader_cannot_create_maintenance(self, app, leader_user):
        """领导不能创建维护记录"""
        with app.test_request_context():
            from flask_login import login_user
            login_user(leader_user)
            assert can_create_maintenance() is False

    def test_employee_can_edit_own_maintenance(self, app, employee_user, test_maintenance):
        """员工可以编辑自己的维护记录"""
        with app.test_request_context():
            from flask_login import login_user
            login_user(employee_user)
            test_maintenance.created_by = employee_user.id
            assert can_edit_maintenance(test_maintenance) is True

    def test_employee_cannot_edit_others_maintenance(self, app, employee_user, test_maintenance, other_user):
        """员工不能编辑他人的维护记录"""
        with app.test_request_context():
            from flask_login import login_user
            login_user(employee_user)
            test_maintenance.created_by = other_user.id
            assert can_edit_maintenance(test_maintenance) is False

    def test_leader_cannot_edit_maintenance(self, app, leader_user, test_maintenance):
        """领导不能编辑维护记录"""
        with app.test_request_context():
            from flask_login import login_user
            login_user(leader_user)
            assert can_edit_maintenance(test_maintenance) is False
```

- [ ] **Step 1.2: 运行测试确认失败**

Run: `pytest tests/test_permissions.py -v`
Expected: FAIL (测试文件/函数不存在或测试失败)

- [ ] **Step 1.3: 创建测试 fixtures**

```python
# tests/conftest.py 添加以下 fixtures

@pytest.fixture
def employee_user(app, db):
    """员工用户"""
    user = User(username='employee_test', role='employee', real_name='测试员工')
    user.set_password('password')
    db.session.add(user)
    db.session.commit()
    return user

@pytest.fixture
def leader_user(app, db):
    """领导用户"""
    user = User(username='leader_test', role='leader', real_name='测试领导')
    user.set_password('password')
    db.session.add(user)
    db.session.commit()
    return user

@pytest.fixture
def admin_user(app, db):
    """管理员用户"""
    user = User(username='admin_test', role='admin', real_name='测试管理员')
    user.set_password('password')
    db.session.add(user)
    db.session.commit()
    return user

@pytest.fixture
def other_user(app, db):
    """其他用户"""
    user = User(username='other_test', role='employee', real_name='其他员工')
    user.set_password('password')
    db.session.add(user)
    db.session.commit()
    return user

@pytest.fixture
def test_ledger(db, employee_user):
    """测试台账合集"""
    ledger = Ledger(名称='测试台账', created_by=employee_user.id, status='draft')
    db.session.add(ledger)
    db.session.commit()
    return ledger

@pytest.fixture
def test_valve(db, test_ledger, employee_user):
    """测试阀门"""
    valve = Valve(
        位号='TEST-001',
        名称='测试阀门',
        ledger_id=test_ledger.id,
        created_by=employee_user.id,
        status='draft'
    )
    db.session.add(valve)
    db.session.commit()
    return valve

@pytest.fixture
def test_maintenance(db, test_valve, employee_user):
    """测试维护记录"""
    record = MaintenanceRecord(
        valve_id=test_valve.id,
        设备位号=test_valve.位号,
        设备名称=test_valve.名称,
        检修内容='测试检修内容',
        created_by=employee_user.id
    )
    db.session.add(record)
    db.session.commit()
    return record
```

- [ ] **Step 1.4: 实现权限检查函数**

```python
# app/routes/valves/permissions.py
# 替换整个文件内容

from flask import flash, redirect, url_for
from flask_login import current_user
from functools import wraps
from app.models import Valve


# 可编辑状态列表
EDITABLE_STATUSES = ['draft', 'rejected', 'approved']


# ============ 台账合集权限 ============

def can_create_ledger():
    """检查是否可以创建台账合集"""
    return current_user.role in ['employee', 'admin']


def can_edit_ledger(ledger):
    """
    检查是否可以编辑台账合集

    后端权限检查不依赖 URL 参数，始终基于资源所有权。
    """
    if current_user.role == 'admin':
        return True
    if current_user.role == 'employee' and ledger.created_by == current_user.id:
        return True
    # leader 不能编辑台账合集
    return False


def can_delete_ledger(ledger):
    """检查是否可以删除台账合集"""
    # 有待审批记录时不能删除
    pending_count = Valve.query.filter_by(
        ledger_id=ledger.id, status='pending'
    ).count()
    if pending_count > 0:
        return False
    return can_edit_ledger(ledger)


# ============ 阀门权限 ============

def can_create_valve(ledger):
    """检查是否可以在台账合集中新增阀门"""
    if current_user.role == 'admin':
        return True
    if current_user.role == 'employee' and ledger.created_by == current_user.id:
        return True
    return False


def can_edit_valve(valve):
    """
    检查是否可以编辑阀门

    后端权限检查不依赖 URL 参数，始终基于资源所有权和状态。
    """
    if current_user.role == 'admin':
        return True
    if current_user.role == 'employee' and valve.created_by == current_user.id:
        # 还需要检查状态
        return valve.status in EDITABLE_STATUSES
    # leader 不能编辑阀门
    return False


def can_delete_valve(valve):
    """检查是否可以删除阀门"""
    return can_edit_valve(valve)


def can_submit_valve(valve):
    """检查是否可以提交阀门审批"""
    if valve.status != 'draft':
        return False
    if current_user.role == 'admin':
        return True
    if current_user.role == 'employee' and valve.created_by == current_user.id:
        return True
    return False


def can_approve_valve(valve):
    """
    检查是否可以审批阀门

    只有 pending 状态的阀门才能被审批
    """
    if valve.status != 'pending':
        return False
    return current_user.role in ['leader', 'admin']


# ============ 导入导出权限 ============

def can_import_data(ledger=None):
    """
    检查是否可以导入数据

    员工只能导入到自己的台账合集
    """
    if current_user.role == 'admin':
        return True
    if current_user.role == 'employee':
        if ledger is None:
            return True  # 导入页面可以选择目标合集
        if ledger.created_by == current_user.id:
            return True
    return False


def can_export_data():
    """检查是否可以导出数据"""
    return True  # 所有登录用户都可以导出


# ============ 附件和照片权限 ============

def can_manage_attachments(valve):
    """检查是否可以管理附件（新增/编辑/删除）"""
    return can_edit_valve(valve)


def can_manage_photos(valve):
    """检查是否可以管理照片（上传/删除）"""
    return can_edit_valve(valve)


# ============ 维护记录权限 ============

def can_create_maintenance():
    """检查是否可以创建维护记录"""
    return current_user.role in ['employee', 'admin']


def can_edit_maintenance(record):
    """检查是否可以编辑维护记录"""
    if current_user.role == 'admin':
        return True
    if current_user.role == 'employee' and record.created_by == current_user.id:
        return True
    return False


def can_delete_maintenance(record):
    """检查是否可以删除维护记录"""
    return can_edit_maintenance(record)


# ============ 辅助函数（保持向后兼容） ============

def can_view_valve(valve):
    """查看台账权限"""
    if valve.created_by == current_user.id:
        return True
    if current_user.role in ["leader", "admin"]:
        return True
    if valve.status == "approved":
        return True
    return False


def can_view_ledger(ledger):
    """查看台账集合权限"""
    if ledger.created_by == current_user.id:
        return True
    if current_user.role in ["leader", "admin"]:
        return True
    if ledger.approved_snapshot_status == "approved":
        return True
    return False


def require_edit_permission(valve):
    """检查编辑权限，返回错误信息或None"""
    if not can_edit_valve(valve):
        return "无权编辑"
    if valve.status not in EDITABLE_STATUSES:
        return "当前状态无法编辑"
    return None


def require_delete_permission(valve):
    """检查删除权限，返回错误信息或None"""
    if not can_delete_valve(valve):
        return "无权删除"
    if valve.status not in EDITABLE_STATUSES:
        return "当前状态无法删除"
    return None
```

- [ ] **Step 1.5: 运行测试确认通过**

Run: `pytest tests/test_permissions.py -v`
Expected: PASS

- [ ] **Step 1.6: 提交**

```bash
git add app/routes/valves/permissions.py tests/test_permissions.py tests/conftest.py
git commit -m "feat: 实现细粒度权限检查函数

- 台账合集权限：员工可创建/编辑自己的，领导无权限
- 阀门权限：员工可编辑自己的（排除pending状态），领导无权限
- 维护记录权限：员工可创建/编辑自己的，领导无权限
- 审批权限：仅领导和管理员可审批pending状态阀门

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 2: 修改台账合集路由权限

**Files:**
- Modify: `app/routes/ledgers.py`

### Step 2.1: 移除重复的权限函数定义

- [ ] **删除 ledgers.py 中的重复函数**

找到 `ledgers.py` 中的以下函数定义（约第55-70行）并删除：

```python
# 删除这些重复定义的函数
def can_edit_ledger(ledger):
    return ledger.created_by == current_user.id or current_user.role in [
        "leader",
        "admin",
    ]


def can_edit_valve(valve):
    return valve.created_by == current_user.id or current_user.role in [
        "leader",
        "admin",
    ]


def can_delete_valve(valve):
    return can_edit_valve(valve)
```

### Step 2.2: 更新导入语句

- [ ] **更新 ledgers.py 的导入**

```python
# app/routes/ledgers.py 顶部导入部分
# 修改为：

from app.routes.valves.permissions import (
    can_edit_ledger,
    can_delete_ledger,
    can_create_valve,
    can_edit_valve,
    can_delete_valve,
    can_view_ledger,
    can_view_valve,
)
```

### Step 2.3: 清理调试代码

- [ ] **删除调试日志代码**

找到并删除以下调试代码（约第524-572行）：

```python
# 删除这些调试代码
with open("debug_form.log", "a", encoding="utf-8") as f:
    f.write("=== DEBUG FORM DATA ===\n")
    ...
```

### Step 2.4: 修改 new_valve 路由

- [ ] **增加权限检查**

找到 `new_valve` 函数，修改权限检查部分：

```python
@ledgers.route("/ledger/<int:id>/valve/new", methods=["GET", "POST"])
@login_required
def new_valve(id):
    from_param = request.args.get("from", "all")
    ledger = Ledger.query.get_or_404(id)

    # 使用新的权限函数
    if not can_create_valve(ledger):
        flash("无权操作")
        return redirect(url_for("ledgers.detail", id=id, **{"from": from_param}))

    # ... 其余代码保持不变
```

### Step 2.5: 修改 edit_valve 路由

- [ ] **增加状态检查**

找到 `edit_valve` 函数，修改权限检查部分：

```python
@ledgers.route("/ledger/<int:ledger_id>/valve/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_valve(ledger_id, id):
    from_param = request.args.get("from", "all")
    ledger = Ledger.query.get_or_404(ledger_id)
    valve = Valve.query.get_or_404(id)

    if not can_edit_valve(valve):
        flash("无权编辑")
        return redirect(url_for("ledgers.detail", id=ledger_id, **{"from": from_param}))

    # ... 其余代码保持不变
```

### Step 2.6: 修改 delete_valve 路由

- [ ] **使用新的权限函数**

```python
@ledgers.route("/ledger/<int:ledger_id>/valve/delete/<int:id>", methods=["POST"])
@login_required
def delete_valve(ledger_id, id):
    from_param = request.args.get("from", "all")
    ledger = Ledger.query.get_or_404(ledger_id)
    valve = Valve.query.get_or_404(id)

    if not can_delete_valve(valve):
        flash("无权删除")
        return redirect(url_for("ledgers.detail", id=ledger_id, **{"from": from_param}))

    # ... 其余代码保持不变
```

### Step 2.7: 修改 batch_delete_valve 路由

- [ ] **增加权限检查**

```python
@ledgers.route("/ledger/<int:id>/valve/batch-delete", methods=["POST"])
@login_required
def batch_delete_valve(id):
    from_param = request.args.get("from", "all")
    ledger = Ledger.query.get_or_404(id)

    if not can_edit_ledger(ledger):
        flash("无权操作")
        return redirect(url_for("ledgers.detail", id=id, **{"from": from_param}))

    # ... 其余代码保持不变
```

### Step 2.8: 提交

```bash
git add app/routes/ledgers.py
git commit -m "refactor: 修改台账合集路由权限检查

- 移除重复的权限函数定义
- 使用统一的权限检查函数
- 清理调试日志代码
- 增加阀门操作权限检查

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 3: 修改阀门路由权限

**Files:**
- Modify: `app/routes/valves/__init__.py`

### Step 3.1: 更新导入

- [ ] **确认导入正确**

```python
# app/routes/valves/__init__.py 顶部
# 确保导入了所有需要的权限函数
from app.routes.valves.permissions import (
    can_edit_valve,
    can_delete_valve,
    can_view_valve,
    can_submit_valve,
    require_edit_permission,
    require_delete_permission,
)
```

### Step 3.2: 修改 edit 路由

- [ ] **确认权限检查正确**

`edit` 函数已经有 `require_edit_permission` 调用，确认它使用的是更新后的权限函数。

### Step 3.3: 修改 delete 路由

- [ ] **确认权限检查正确**

`delete` 函数已经有 `require_delete_permission` 调用，确认它使用的是更新后的权限函数。

### Step 3.4: 修改 batch_delete 路由

- [ ] **增加权限检查**

找到 `batch_delete` 函数，修改为：

```python
@valves.route("/valves/batch-delete", methods=["POST"])
@login_required
def batch_delete():
    from_param = get_from_param()
    ids = request.form.getlist("ids")
    if not ids:
        flash("请选择要删除的记录")
        return redirect_to_list(from_param)

    count = 0
    for id in ids:
        valve = Valve.query.get(int(id))
        # 使用新的权限函数
        if valve and can_delete_valve(valve):
            ApprovalLog.query.filter_by(valve_id=valve.id).delete()
            db.session.delete(valve)
            count += 1

    db.session.commit()
    flash(f"成功删除 {count} 条记录")
    return redirect_to_list(from_param)
```

### Step 3.5: 提交

```bash
git add app/routes/valves/__init__.py
git commit -m "refactor: 修改阀门路由权限检查

- 使用统一的权限检查函数
- 批量删除增加权限验证

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 4: 修改维护记录路由权限

**Files:**
- Modify: `app/routes/valves/attachments.py`

### Step 4.1: 更新导入

- [ ] **添加权限函数导入**

```python
# app/routes/valves/attachments.py 顶部
from app.routes.valves.permissions import (
    can_edit_valve,
    can_create_maintenance,
    can_edit_maintenance,
    can_delete_maintenance,
)
```

### Step 4.2: 修改 maintenance 路由

- [ ] **增加权限检查**

找到 `maintenance` 函数，修改为：

```python
def maintenance(id):
    """维护记录"""
    from_param = get_from_param()
    valve = Valve.query.get_or_404(id)

    if request.method == "POST":
        # 检查是否可以创建维护记录
        if not can_create_maintenance():
            flash("无权创建维护记录")
            return redirect(url_for("valves.detail", id=id, **{'from': from_param}))

        # ... 其余创建逻辑保持不变
```

### Step 4.3: 修改 maintenance_create 路由

- [ ] **增加权限检查**

```python
def maintenance_create():
    """新建维护记录"""
    # 检查权限
    if not can_create_maintenance():
        flash("无权创建维护记录")
        return redirect(url_for("valves.maintenance_list"))

    valves = Valve.query.filter(Valve.status != "draft").order_by(Valve.位号).all()

    if request.method == "POST":
        # ... 其余代码保持不变
```

### Step 4.4: 修改 maintenance_edit 路由

- [ ] **增加权限检查**

```python
def maintenance_edit(id):
    """编辑维护记录"""
    record = MaintenanceRecord.query.get_or_404(id)

    # 检查权限
    if not can_edit_maintenance(record):
        flash("无权编辑此维护记录")
        return redirect(url_for("valves.maintenance_list"))

    valves = Valve.query.filter(Valve.status != "draft").order_by(Valve.位号).all()

    if request.method == "POST":
        # ... 其余代码保持不变
```

### Step 4.5: 修改 maintenance_batch_delete 路由

- [ ] **增加权限检查**

```python
def maintenance_batch_delete():
    """批量删除维护记录"""
    ids = request.form.getlist("ids")
    if not ids:
        flash("请选择要删除的记录")
        return redirect(url_for("valves.maintenance_list"))

    count = 0
    for record_id in ids:
        record = MaintenanceRecord.query.get(int(record_id))
        if record and can_delete_maintenance(record):
            db.session.delete(record)
            count += 1

    db.session.commit()
    flash(f"成功删除 {count} 条记录")
    return redirect(url_for("valves.maintenance_list"))
```

### Step 4.6: 提交

```bash
git add app/routes/valves/attachments.py
git commit -m "feat: 增加维护记录权限检查

- 创建维护记录：仅员工和管理员
- 编辑维护记录：仅创建者和管理员
- 删除维护记录：仅创建者和管理员

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 5: 修改前端模板 - 阀门列表

**Files:**
- Modify: `templates/valves/list.html`

### Step 5.1: 修改工具栏按钮

- [ ] **根据权限控制按钮显示**

找到工具栏部分（约第38-76行），修改为：

```html
{% block toolbar %}
{% set from_param = from_param|default(request.args.get('from', 'all')) %}
<div class="table-toolbar-compact">
    <div class="d-flex justify-content-between align-items-center">
        <div class="d-flex align-items-center gap-2">
            <div class="form-check">
                <input type="checkbox" class="form-check-input" id="selectAll">
            </div>
            <span style="font-size: 13px;">已选 <span id="selectedCount">0</span> 项</span>
            {% if ledger %}
            <div class="d-flex align-items-center gap-1">
                {# 新增按钮：员工且是自己的台账才显示 #}
                {% if current_user.role == 'employee' and ledger.created_by == current_user.id and ledger.display_status != 'pending' %}
                <a href="{{ url_for('ledgers.new_valve', id=ledger.id, from=from_param) }}" class="btn btn-sm btn-primary" style="padding: 4px 12px; font-size: 12px;" title="新增台账">
                    <i class="bi bi-plus-lg"></i> 新增
                </a>
                <button type="button" class="btn btn-sm btn-outline-danger" style="padding: 4px 12px; font-size: 12px;" onclick="batchDelete()" title="批量删除">
                    <i class="bi bi-trash"></i> 删除
                </button>
                {% endif %}
                {# 导出按钮：所有用户可见 #}
                <a href="{{ url_for('valves.export_data') }}" class="btn btn-sm btn-outline-secondary" style="padding: 4px 12px; font-size: 12px;" title="导出全部">
                    <i class="bi bi-download"></i> 导出
                </a>
                {# 导入按钮：员工且是自己的台账才显示 #}
                {% if current_user.role == 'employee' and ledger.created_by == current_user.id %}
                <a href="{{ url_for('valves.import_data', ledger_id=ledger.id) }}" class="btn btn-sm btn-outline-secondary" style="padding: 4px 12px; font-size: 12px;" title="导入数据">
                    <i class="bi bi-upload"></i> 导入
                </a>
                {% endif %}
            </div>
            {% else %}
            {# 无 ledger 时的处理（独立阀门） #}
            <div class="d-flex align-items-center gap-1">
                {% if current_user.role == 'employee' %}
                <a href="{{ url_for('valves.new') }}" class="btn btn-sm btn-primary" style="padding: 4px 12px; font-size: 12px;" title="新增台账">
                    <i class="bi bi-plus-lg"></i> 新增
                </a>
                <button type="button" class="btn btn-sm btn-outline-danger" style="padding: 4px 12px; font-size: 12px;" onclick="batchDelete()" title="批量删除">
                    <i class="bi bi-trash"></i> 删除
                </button>
                <a href="{{ url_for('valves.import_data') }}" class="btn btn-sm btn-outline-secondary" style="padding: 4px 12px; font-size: 12px;" title="导入数据">
                    <i class="bi bi-upload"></i> 导入
                </a>
                {% endif %}
                <a href="{{ url_for('valves.export_data') }}" class="btn btn-sm btn-outline-secondary" style="padding: 4px 12px; font-size: 12px;" title="导出全部">
                    <i class="bi bi-download"></i> 导出
                </a>
            </div>
            {% endif %}
        </div>
        <!-- 搜索部分保持不变 -->
    </div>
</div>
{% endblock %}
```

### Step 5.2: 修改表格操作列

- [ ] **根据权限控制编辑按钮**

找到表格操作列部分（约第221-227行），修改为：

```html
<td style="position: sticky; right: 0; z-index: 2; background: #fff;">
    <a href="{% if ledger %}{{ url_for('ledgers.valve_detail', ledger_id=ledger.id, id=valve.id) }}?from={{ from_param|default(request.args.get('from', 'all')) }}{% else %}{{ url_for('valves.detail', id=valve.id) }}{% endif %}" class="btn-action" style="background: #e2e8f0; color: #475569;"><i class="bi bi-eye"></i></a>
    {# 编辑按钮：员工且是自己的阀门且状态允许编辑 #}
    {% if current_user.role == 'employee' and valve.created_by == current_user.id and valve.status in ['draft', 'rejected', 'approved'] %}
    <a href="{% if ledger %}{{ url_for('ledgers.edit_valve', ledger_id=ledger.id, id=valve.id, from=from_param|default(request.args.get('from', 'all'))) }}{% else %}{{ url_for('valves.edit', id=valve.id) }}{% endif %}" class="btn-action" style="background: rgba(56,178,172,0.1); color: var(--accent-color);"><i class="bi bi-pencil"></i></a>
    {% endif %}
</td>
```

### Step 5.3: 提交

```bash
git add templates/valves/list.html
git commit -m "feat: 阀门列表页面权限控制

- 新增按钮：仅员工且自己的台账显示
- 编辑按钮：仅员工且自己的阀门显示
- 导入按钮：仅员工且自己的台账显示
- 导出按钮：所有用户可见

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 6: 修改前端模板 - 阀门详情

**Files:**
- Modify: `templates/valves/detail.html`

### Step 6.1: 修改编辑按钮

- [ ] **根据权限控制编辑按钮显示**

找到 `header_actions` 块（约第26-33行），修改为：

```html
{% block header_actions %}
{% set from_param = from_param|default(request.args.get('from', 'all')) %}
{# 编辑按钮：员工且是自己的阀门且状态允许编辑 #}
{% if current_user.role == 'employee' and valve.created_by == current_user.id and valve.status in ['draft', 'rejected', 'approved'] %}
<a href="{{ url_for('valves.edit', id=valve.id, from=from_param) }}" class="toolbar-btn toolbar-btn-primary">
    <i class="bi bi-pencil"></i> 编辑
</a>
{% endif %}
{% endblock %}
```

### Step 6.2: 提交

```bash
git add templates/valves/detail.html
git commit -m "feat: 阀门详情页面权限控制

- 编辑按钮：仅员工且自己的阀门显示

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 7: 修改前端模板 - 台账列表

**Files:**
- Modify: `templates/ledgers/list.html`

### Step 7.1: 隐藏创建按钮

- [ ] **全部台账界面不显示创建按钮**

找到创建按钮部分，添加条件判断：

```html
{# 创建台账按钮：不在全部台账界面显示 #}
{% if request.endpoint != 'ledgers.list' %}
<a href="{{ url_for('ledgers.new') }}" class="btn btn-primary-custom">
    <i class="bi bi-plus-lg"></i> 创建合集
</a>
{% endif %}
```

或者更简单的方式，直接删除全部台账列表中的创建按钮。

### Step 7.2: 提交

```bash
git add templates/ledgers/list.html
git commit -m "feat: 全部台账界面隐藏创建按钮

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 8: 修改前端模板 - 维护记录

**Files:**
- Modify: `templates/maintenance/list.html`

### Step 8.1: 修改工具栏按钮

- [ ] **根据权限控制按钮显示**

找到工具栏部分，修改为：

```html
{% block header_actions %}
<div class="d-flex gap-2">
    {# 导出按钮：所有用户可见 #}
    <a href="{{ url_for('valves.maintenance_export') }}" class="btn btn-outline-secondary">
        <i class="bi bi-download"></i> 导出
    </a>
    {# 新增按钮：仅员工和管理员可见 #}
    {% if current_user.role in ['employee', 'admin'] %}
    <a href="{{ url_for('valves.maintenance_create') }}" class="btn btn-primary-custom">
        <i class="bi bi-plus-lg"></i> 新增记录
    </a>
    {% endif %}
</div>
{% endblock %}
```

### Step 8.2: 修改表格操作列

- [ ] **根据权限控制编辑删除按钮**

找到表格操作列部分，修改为：

```html
<td>
    <a href="{{ url_for('valves.maintenance_export', ids=[record.id]) }}" class="btn-action" title="导出"><i class="bi bi-download"></i></a>
    {# 编辑按钮：仅创建者和管理员可见 #}
    {% if current_user.role == 'admin' or (current_user.role == 'employee' and record.created_by == current_user.id) %}
    <a href="{{ url_for('valves.maintenance_edit', id=record.id) }}" class="btn-action" title="编辑"><i class="bi bi-pencil"></i></a>
    {% endif %}
</td>
```

### Step 8.3: 提交

```bash
git add templates/maintenance/list.html
git commit -m "feat: 维护记录页面权限控制

- 新增按钮：仅员工和管理员显示
- 编辑按钮：仅创建者和管理员显示
- 导出按钮：所有用户可见

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 9: 修改前端模板 - 台账详情页

**Files:**
- Modify: `templates/ledgers/detail.html`

### Step 9.1: 修改工具栏按钮

- [ ] **根据权限控制按钮显示**

找到工具栏部分，根据 `is_owner` 控制编辑/删除按钮：

```html
{% block header_actions %}
{% set from_param = from_param|default(request.args.get('from', 'all')) %}
<div class="d-flex gap-2">
    {# 编辑按钮：仅台账所有者和管理员可见 #}
    {% if current_user.role == 'admin' or (current_user.role == 'employee' and ledger.created_by == current_user.id) %}
    <a href="{{ url_for('ledgers.edit', id=ledger.id, from=from_param) }}" class="btn btn-outline-primary">
        <i class="bi bi-pencil"></i> 编辑
    </a>
    {% endif %}
    {# 提交审批按钮：仅台账所有者可见 #}
    {% if current_user.role == 'employee' and ledger.created_by == current_user.id and ledger.draft_count > 0 %}
    <form method="POST" action="{{ url_for('ledgers.submit', id=ledger.id, from=from_param) }}" style="display:inline;">
        <button type="submit" class="btn btn-primary-custom">
            <i class="bi bi-send"></i> 提交审批
        </button>
    </form>
    {% endif %}
    {# 删除按钮：仅台账所有者和管理员可见，且无待审批记录 #}
    {% if (current_user.role == 'admin' or (current_user.role == 'employee' and ledger.created_by == current_user.id)) and ledger.pending_count == 0 %}
    <form method="POST" action="{{ url_for('ledgers.delete', id=ledger.id, from=from_param) }}" style="display:inline;" onsubmit="return confirm('确定删除？');">
        <button type="submit" class="btn btn-outline-danger">
            <i class="bi bi-trash"></i> 删除
        </button>
    </form>
    {% endif %}
</div>
{% endblock %}
```

### Step 9.2: 提交

```bash
git add templates/ledgers/detail.html
git commit -m "feat: 台账详情页面权限控制

- 编辑按钮：仅所有者和管理员显示
- 删除按钮：仅所有者和管理员显示，且无待审批记录
- 提交审批按钮：仅所有者显示

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 10: 修改前端模板 - 维护记录编辑页

**Files:**
- Modify: `templates/maintenance/edit.html`

### Step 10.1: 增加权限检查提示

- [ ] **在页面顶部增加权限检查**

```html
{% block content %}
{% if not (current_user.role == 'admin' or (current_user.role == 'employee' and record.created_by == current_user.id)) %}
<div class="modern-card">
    <div class="alert alert-warning m-3">
        <i class="bi bi-exclamation-triangle"></i> 您没有权限编辑此维护记录
    </div>
    <a href="{{ url_for('valves.maintenance_list') }}" class="btn btn-secondary m-3">返回列表</a>
</div>
{% else %}
<!-- 原有表单内容 -->
{% endif %}
{% endblock %}
```

### Step 10.2: 提交

```bash
git add templates/maintenance/edit.html
git commit -m "feat: 维护记录编辑页面权限检查

- 非创建者显示无权限提示

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 11: 增加导出权限检查

**Files:**
- Modify: `app/routes/valves/exports.py`

### Step 11.1: 确认导出权限

- [ ] **查看导出路由，确认权限正确**

导出功能应该对所有登录用户开放（`can_export_data()` 返回 `True`），无需额外修改。确认代码正确。

### Step 11.2: 提交

如果无需修改，跳过提交。

---

## Task 12: 确认审批路由权限

**Files:**
- Check: `app/routes/approvals.py`

### Step 12.1: 确认审批权限正确

- [ ] **检查审批路由权限**

现有代码使用 `@require_leader` 装饰器，这已经限制了只有领导和管理员可以访问。确认这与新的权限系统一致。

### Step 12.2: 如需修改

如果需要使用新的权限函数，可以修改为：

```python
from app.routes.valves.permissions import can_approve_valve

@approvals.route("/approvals/<int:id>/approve", methods=["POST"])
@login_required
def single_approve(id):
    ledger = Ledger.query.get_or_404(id)
    # 检查权限
    # ... 审批逻辑
```

---

## Task 13: 运行完整测试

**Files:**
- Create: `tests/test_permission_integration.py`
- Run tests

### Step 13.1: 运行权限单元测试

- [ ] **运行测试**

Run: `pytest tests/test_permissions.py -v`
Expected: PASS

### Step 13.2: 编写集成测试

- [ ] **添加集成测试**

```python
# tests/test_permission_integration.py

import pytest
from flask import url_for
from app.models import User, Ledger, Valve, MaintenanceRecord, db


class TestEmployeePermissions:
    """员工权限集成测试"""

    def test_employee_can_edit_own_valve(self, app, employee_user, test_valve):
        """员工可以编辑自己的阀门"""
        with app.test_client() as client:
            client.post('/auth/login', data={
                'username': 'employee_test',
                'password': 'password'
            })
            test_valve.created_by = employee_user.id
            test_valve.status = 'draft'
            db.session.commit()

            response = client.get(f'/valve/edit/{test_valve.id}')
            assert response.status_code == 200

    def test_employee_cannot_edit_others_valve(self, app, employee_user, test_valve, other_user):
        """员工不能编辑他人的阀门"""
        with app.test_client() as client:
            client.post('/auth/login', data={
                'username': 'employee_test',
                'password': 'password'
            })
            test_valve.created_by = other_user.id
            test_valve.status = 'draft'
            db.session.commit()

            response = client.get(f'/valve/edit/{test_valve.id}', follow_redirects=True)
            assert b'\xe6\x97\xa0\xe6\x9d\x83' in response.data  # "无权"

    def test_employee_cannot_edit_pending_valve(self, app, employee_user, test_valve):
        """员工不能编辑待审批状态的阀门"""
        with app.test_client() as client:
            client.post('/auth/login', data={
                'username': 'employee_test',
                'password': 'password'
            })
            test_valve.created_by = employee_user.id
            test_valve.status = 'pending'
            db.session.commit()

            response = client.get(f'/valve/edit/{test_valve.id}', follow_redirects=True)
            assert b'\xe6\x97\xa0\xe6\x9d\x83' in response.data or b'\xe6\x97\xa0\xe6\xb3\x95\xe7\xbc\x96\xe8\xbe\x91' in response.data


class TestLeaderPermissions:
    """领导权限集成测试"""

    def test_leader_cannot_edit_valve(self, app, leader_user, test_valve):
        """领导不能编辑阀门"""
        with app.test_client() as client:
            client.post('/auth/login', data={
                'username': 'leader_test',
                'password': 'password'
            })
            test_valve.status = 'draft'
            db.session.commit()

            response = client.get(f'/valve/edit/{test_valve.id}', follow_redirects=True)
            assert b'\xe6\x97\xa0\xe6\x9d\x83' in response.data

    def test_leader_can_access_approvals(self, app, leader_user):
        """领导可以访问审批页面"""
        with app.test_client() as client:
            client.post('/auth/login', data={
                'username': 'leader_test',
                'password': 'password'
            })

            response = client.get('/approvals')
            assert response.status_code == 200


class TestSecurity:
    """安全测试"""

    def test_url_parameter_cannot_bypass_permission(self, app, employee_user, test_valve, other_user):
        """URL参数不能绕过权限"""
        with app.test_client() as client:
            client.post('/auth/login', data={
                'username': 'employee_test',
                'password': 'password'
            })
            test_valve.created_by = other_user.id
            test_valve.status = 'draft'
            db.session.commit()

            # 尝试通过修改 from 参数绕过权限
            response = client.get(f'/valve/edit/{test_valve.id}?from=mine', follow_redirects=True)
            assert b'\xe6\x97\xa0\xe6\x9d\x83' in response.data

    def test_direct_access_without_permission(self, app, employee_user, test_valve, other_user):
        """直接访问无权限资源被拒绝"""
        with app.test_client() as client:
            client.post('/auth/login', data={
                'username': 'employee_test',
                'password': 'password'
            })
            test_valve.created_by = other_user.id
            test_valve.status = 'draft'
            db.session.commit()

            # 尝试直接访问编辑页面
            response = client.post(f'/valve/edit/{test_valve.id}', data={
                '名称': '测试修改'
            }, follow_redirects=True)
            assert b'\xe6\x97\xa0\xe6\x9d\x83' in response.data
```

### Step 13.3: 运行所有测试

- [ ] **运行完整测试套件**

Run: `pytest tests/ -v`
Expected: PASS

### Step 13.4: 手动测试关键场景

- [ ] **员工权限测试**
  1. 登录员工账号
  2. 访问「我的台账」：确认可以新增、编辑、删除
  3. 访问「全部台账」：确认只能查看，按钮不显示
  4. 访问维护记录：确认可以新增，只能编辑自己的

- [ ] **领导权限测试**
  1. 登录领导账号
  2. 访问「全部台账」：确认只能查看
  3. 访问「审批界面」：确认可以审批
  4. 访问维护记录：确认只能查看

- [ ] **管理员权限测试**
  1. 登录管理员账号
  2. 确认所有功能正常

---

## Task 14: 最终提交

- [ ] **确认所有修改完成**

```bash
git status
```

- [ ] **推送代码**

```bash
git push origin master
```