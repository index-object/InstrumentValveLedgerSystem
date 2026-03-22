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

### 上下文感知权限

通过 `from` 参数区分访问上下文：
- `mine`: 我的台账
- `all`: 全部台账
- `approvals`: 审批界面

权限检查函数根据上下文动态判断权限。

### 权限检查函数设计

#### 新增权限函数 (`app/routes/valves/permissions.py`)

```python
def get_context_from_request():
    """从请求中获取上下文"""
    from flask import request
    return request.args.get('from', 'all')

def can_create_ledger(context=None):
    """检查是否可以创建台账合集"""
    if context is None:
        context = get_context_from_request()

    if current_user.role == 'admin':
        return True
    if current_user.role == 'employee' and context == 'mine':
        return True
    return False

def can_edit_ledger(ledger, context=None):
    """检查是否可以编辑台账合集"""
    if context is None:
        context = get_context_from_request()

    if current_user.role == 'admin':
        return True
    if current_user.role == 'employee' and context == 'mine' and ledger.created_by == current_user.id:
        return True
    return False

def can_create_valve(ledger, context=None):
    """检查是否可以在台账合集中新增阀门"""
    if context is None:
        context = get_context_from_request()

    if current_user.role == 'admin':
        return True
    if current_user.role == 'employee' and context == 'mine' and ledger.created_by == current_user.id:
        return True
    return False

def can_edit_valve(valve, context=None):
    """检查是否可以编辑阀门"""
    if context is None:
        context = get_context_from_request()

    if current_user.role == 'admin':
        return True
    if current_user.role == 'employee' and context == 'mine' and valve.created_by == current_user.id:
        return True
    return False

def can_delete_valve(valve, context=None):
    """检查是否可以删除阀门"""
    return can_edit_valve(valve, context)

def can_submit_valve(valve, context=None):
    """检查是否可以提交阀门审批"""
    if context is None:
        context = get_context_from_request()

    if current_user.role == 'admin':
        return True
    if current_user.role == 'employee' and context == 'mine' and valve.created_by == current_user.id:
        return True
    return False

def can_approve_valve():
    """检查是否可以审批阀门"""
    return current_user.role in ['leader', 'admin']

def can_import_data(context=None):
    """检查是否可以导入数据"""
    if context is None:
        context = get_context_from_request()

    if current_user.role == 'admin':
        return True
    if current_user.role == 'employee' and context == 'mine':
        return True
    return False

def can_export_data():
    """检查是否可以导出数据"""
    return True  # 所有登录用户都可以导出

# 维护记录权限
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
context = request.args.get('from', 'all')
can_create = can_create_ledger(context)
can_edit = can_edit_ledger(ledger, context)
can_create_valve = can_create_valve(ledger, context)
can_import = can_import_data(context)
can_export = can_export_data()

return render_template('...',
    context=context,
    can_create=can_create,
    can_edit=can_edit,
    can_create_valve=can_create_valve,
    can_import=can_import,
    can_export=can_export,
    ...
)
```

### 权限装饰器

新增权限装饰器用于路由保护：

```python
def require_context_permission(permission_func, *args, **kwargs):
    """权限装饰器工厂"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*f_args, **f_kwargs):
            if not permission_func(*args, **kwargs):
                flash("无权执行此操作")
                return redirect(url_for('ledgers.list'))
            return f(*f_args, **f_kwargs)
        return decorated_function
    return decorator
```

## 文件修改清单

### 后端文件

| 文件 | 修改内容 |
|------|----------|
| `app/routes/valves/permissions.py` | 新增权限检查函数 |
| `app/routes/ledgers.py` | 修改权限检查逻辑 |
| `app/routes/valves/__init__.py` | 修改权限检查逻辑 |
| `app/routes/valves/attachments.py` | 增加维护记录权限检查 |
| `app/routes/approvals.py` | 确保审批权限正确 |

### 前端文件

| 文件 | 修改内容 |
|------|----------|
| `templates/valves/list.html` | 增加按钮权限控制 |
| `templates/valves/detail.html` | 增加按钮权限控制 |
| `templates/ledgers/list.html` | 增加按钮权限控制 |
| `templates/valves/my_ledgers.html` | 确保权限正确 |
| `templates/maintenance/list.html` | 增加按钮权限控制 |
| `templates/maintenance/edit.html` | 增加权限检查 |
| `templates/approvals/index.html` | 确保审批权限正确 |

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
   - 修改 `from` 参数尝试绕过权限
   - 确保后端严格验证

2. 直接访问测试
   - 直接访问编辑URL测试权限

## 实现优先级

1. **Phase 1**: 权限检查函数实现
2. **Phase 2**: 后端路由权限保护
3. **Phase 3**: 前端UI控制
4. **Phase 4**: 测试和修复