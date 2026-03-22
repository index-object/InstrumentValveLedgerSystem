# 权限管理系统设计文档

## 概述

本文档描述仪表阀门台账管理系统的细粒度权限控制方案，实现基于角色和上下文的权限管理。

### 需求背景

当前系统权限控制较为粗粒度：
- leader/admin 可以编辑所有阀门
- 维护记录没有任何权限限制
- 「我的台账」和「全部台账」没有权限区分

新方案需要实现：
- 员工在「我的台账」有完整权限，在「全部台账」只读
- 领导在「全部台账」和「审批界面」只读（审批除外）
- 维护记录按创建者限制编辑权限

## 权限矩阵

### 台账合集操作权限

| 操作 | 员工(我的台账) | 员工(全部台账) | 领导(全部台账) | 领导(审批界面) | 管理员 |
|------|----------------|----------------|----------------|----------------|--------|
| 查看列表 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 查看详情 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 创建合集 | ✅ | ❌ | ❌ | ❌ | ✅ |
| 编辑合集 | ✅(自己的) | ❌ | ❌ | ❌ | ✅ |
| 删除合集 | ✅(自己的) | ❌ | ❌ | ❌ | ✅ |
| 新增阀门 | ✅ | ❌ | ❌ | ❌ | ✅ |
| 编辑阀门 | ✅(自己的) | ❌ | ❌ | ❌ | ✅ |
| 删除阀门 | ✅(自己的) | ❌ | ❌ | ❌ | ✅ |
| 提交审批 | ✅ | ❌ | ❌ | ❌ | ✅ |
| 审批/驳回 | ❌ | ❌ | ❌ | ✅ | ✅ |
| 导入数据 | ✅ | ❌ | ❌ | ❌ | ✅ |
| 导出数据 | ✅ | ✅ | ✅ | ✅ | ✅ |

### 维护记录操作权限

| 操作 | 员工 | 领导 | 管理员 |
|------|------|------|--------|
| 查看列表 | ✅ | ✅ | ✅ |
| 查看详情 | ✅ | ✅ | ✅ |
| 新增记录 | ✅ | ❌ | ✅ |
| 编辑记录 | ✅(自己的) | ❌ | ✅ |
| 删除记录 | ✅(自己的) | ❌ | ✅ |
| 导出记录 | ✅ | ✅ | ✅ |

## 实现方案

### 核心安全原则

**后端权限检查不依赖 URL 参数。** 权限判断始终基于：
1. 用户角色
2. 资源所有权（`created_by` 字段）
3. 资源状态

URL 参数 `from` 仅用于：
- UI 按钮显示控制
- 导航上下文保持

### 上下文参数

通过 `from` 参数区分访问上下文，仅用于前端显示：
- `mine`: 我的台账
- `all`: 全部台账
- `approvals`: 审批界面

### 权限检查函数设计

**重要：权限函数统一放在 `app/routes/valves/permissions.py`，移除 `ledgers.py` 中的重复定义。**

#### 台账合集权限

```python
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
```

#### 阀门权限

```python
# 可编辑状态列表
EDITABLE_STATUSES = ['draft', 'rejected', 'approved']

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

def can_approve_valve():
    """检查是否可以审批阀门"""
    return current_user.role in ['leader', 'admin']
```

#### 导入导出权限

```python
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
```

#### 附件和照片权限

```python
def can_manage_attachments(valve):
    """检查是否可以管理附件（新增/编辑/删除）"""
    return can_edit_valve(valve)

def can_manage_photos(valve):
    """检查是否可以管理照片（上传/删除）"""
    return can_edit_valve(valve)
```

#### 维护记录权限

```python
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
```

### 路由修改

#### 台账合集路由 (`app/routes/ledgers.py`)

需要修改的路由：
1. `detail()` - 根据上下文控制按钮显示
2. `edit()` - 增加权限检查
3. `delete()` - 增加权限检查
4. `new_valve()` - 增加权限检查
5. `edit_valve()` - 增加权限检查
6. `delete_valve()` - 增加权限检查
7. `batch_save_valve()` - 增加权限检查
8. `batch_delete_valve()` - 增加权限检查

#### 阀门路由 (`app/routes/valves/__init__.py`)

需要修改的路由：
1. `edit()` - 增加权限检查
2. `delete()` - 增加权限检查
3. `batch_delete()` - 增加权限检查
4. `save_draft()` - 增加权限检查

#### 维护记录路由 (`app/routes/valves/attachments.py`)

需要修改的路由：
1. `maintenance()` - 增加权限检查
2. `maintenance_create()` - 增加权限检查
3. `maintenance_edit()` - 增加权限检查
4. `maintenance_batch_delete()` - 增加权限检查

### UI控制

#### 模板修改清单

1. **`templates/valves/list.html`**
   - 根据上下文隐藏/显示「新增」、「删除」、「导入」按钮
   - 根据上下文隐藏/显示编辑按钮

2. **`templates/valves/detail.html`**
   - 根据上下文隐藏/显示「编辑」按钮

3. **`templates/ledgers/list.html`**
   - 全部台账界面隐藏「创建合集」按钮

4. **`templates/valves/my_ledgers.html`**
   - 我的台账界面显示所有操作按钮

5. **`templates/maintenance/list.html`**
   - 根据权限隐藏/显示「新增」、「编辑」、「删除」按钮

6. **`templates/maintenance/edit.html`**
   - 增加权限检查，非创建者不能编辑

#### 模板上下文变量

在每个需要权限控制的模板中注入以下变量：

```python
# 在视图函数中
from_param = request.args.get('from', 'all')

# 计算权限变量（用于 UI 显示）
is_owner = ledger.created_by == current_user.id
can_create = current_user.role == 'employee' and is_owner
can_edit = can_edit_ledger(ledger)  # 调用权限函数
can_create_valve = can_create_valve(ledger)
can_import = can_import_data(ledger)
can_export = can_export_data()

return render_template('...',
    from_param=from_param,  # 用于导航
    is_owner=is_owner,
    can_create=can_create,
    can_edit=can_edit,
    can_create_valve=can_create_valve,
    can_import=can_import,
    can_export=can_export,
    ...
)
```

**注意：** 模板中的权限变量仅用于 UI 显示控制，后端路由必须有独立的权限检查。

## 文件修改清单

### 后端文件

| 文件 | 修改内容 |
|------|----------|
| `app/routes/valves/permissions.py` | 新增/修改权限检查函数，移除 context 参数 |
| `app/routes/ledgers.py` | 1. 移除重复的权限函数定义<br>2. 修改路由权限检查逻辑<br>3. 清理调试日志代码（第524-572行） |
| `app/routes/valves/__init__.py` | 修改权限检查逻辑 |
| `app/routes/valves/attachments.py` | 增加维护记录权限检查 |
| `app/routes/valves/exports.py` | 增加导出权限检查 |
| `app/routes/approvals.py` | 确保审批权限正确 |

### 前端文件

| 文件 | 修改内容 |
|------|----------|
| `templates/valves/list.html` | 1. 根据 from_param 隐藏/显示按钮<br>2. 增加 is_owner 条件判断 |
| `templates/valves/detail.html` | 根据 is_owner 隐藏/显示编辑按钮 |
| `templates/ledgers/list.html` | 全部台账界面隐藏「创建合集」按钮 |
| `templates/ledgers/detail.html` | 增加按钮权限控制 |
| `templates/valves/my_ledgers.html` | 确保权限正确 |
| `templates/valves/form.html` | 增加权限变量传递 |
| `templates/valves/import.html` | 增加导入权限检查 |
| `templates/maintenance/list.html` | 根据 is_owner 隐藏/显示编辑删除按钮 |
| `templates/maintenance/edit.html` | 增加权限检查，非创建者不能编辑 |
| `templates/approvals/index.html` | 确保审批权限正确 |

### 清理工作

| 文件 | 清理内容 |
|------|----------|
| `app/routes/ledgers.py` | 删除调试日志代码（debug_form.log 相关） |
| `app/routes/ledgers.py` | 删除重复定义的 can_edit_ledger, can_edit_valve, can_delete_valve 函数 |

## 测试要点

### 单元测试

1. 权限检查函数测试
   - 测试各角色在各上下文中的权限
   - 测试边界条件

### 集成测试

1. 员工权限测试
   - 我的台账：可以增删改查
   - 全部台账：只能查看
   - 维护记录：可以新增，仅编辑自己的

2. 领导权限测试
   - 全部台账：只能查看
   - 审批界面：可以审批/驳回
   - 维护记录：只能查看

3. 管理员权限测试
   - 所有功能正常

### 安全测试

1. URL参数篡改测试
   - 修改 `from` 参数尝试绕过权限（应无效）
   - 后端权限检查不依赖 URL 参数

2. 直接访问测试
   - 员工直接访问其他用户的阀门编辑URL（应拒绝）
   - 领导直接访问阀门编辑URL（应拒绝）

3. 资源所有权测试
   - 员工尝试编辑不属于自己的阀门（应拒绝）
   - 员工尝试编辑他人创建的维护记录（应拒绝）

## 实现优先级

1. **Phase 1**: 权限检查函数实现
2. **Phase 2**: 后端路由权限保护
3. **Phase 3**: 前端UI控制
4. **Phase 4**: 测试和修复