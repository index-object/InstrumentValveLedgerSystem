# Ledger权限重构设计方案

## 概述

重构Ledger和Valve在不同角色下的数据显示逻辑，新增审批中心界面，统一管理审批流程。

## 需求分析

1. **普通员工权限**
   - Ledger列表：只显示 `approved_snapshot_status == "approved"` 的台账合集
   - Valve列表：只显示状态为"已审批"的阀门数据

2. **管理员/领导权限**
   - Ledger列表：显示所有状态的台账合集（待审批/已审批/已驳回）
   - 新增审批中心界面，集中处理审批业务

3. **快照功能修复**
   - 已审批Ledger中新增待审批Valve时，其他账号应看到之前的已审批快照
   - 不应影响已审批Ledger在其他账号中的可访问性

## 详细设计

### 一、数据层

#### Ledger模型现有字段
- `status`: 当前状态 (draft/pending/rejected/approved)
- `approved_snapshot_status`: 审批快照状态
- `approved_snapshot_at`: 审批快照时间

#### 查询逻辑修改

**普通员工 - Ledger列表：**
```python
query.filter(Ledger.approved_snapshot_status == "approved")
```

**普通员工 - Valve列表（在已审批Ledger中）：**
```python
query.filter(
    Valve.status == "approved",
    Valve.approved_at <= ledger.approved_snapshot_at
)
```

**管理员/领导 - Ledger列表：**
```python
query.filter(or_(
    Ledger.approved_snapshot_status == "approved",
    Ledger.status.in_(["pending", "rejected"])
))
```

### 二、审批中心

#### 路由设计
- 路径：`/approvals`
- 权限：leader, admin
- 方法：GET

#### 界面设计

**三个Tab切换：**
1. 待审批 - 显示有待审批Valve的Ledger
2. 已审批 - 显示快照状态为已审批的Ledger
3. 已驳回 - 显示有待驳回Valve的Ledger

**列表页直接操作：**
- 批量审批按钮
- 批量驳回按钮
- 弹出确认框，可填写审批意见

#### 数据获取

```python
@approvals.route("/approvals")
@login_required
@require_leader
def index():
    tab = request.args.get("tab", "pending")
    
    if tab == "pending":
        ledgers = Ledger.query.join(Valve).filter(
            Valve.status == "pending"
        ).distinct().all()
    elif tab == "approved":
        ledgers = Ledger.query.filter(
            Ledger.approved_snapshot_status == "approved"
        ).all()
    elif tab == "rejected":
        ledgers = Ledger.query.join(Valve).filter(
            Valve.status == "rejected"
        ).distinct().all()
    
    return render_template("approvals/index.html", ledgers=ledgers, tab=tab)
```

### 三、审批操作

#### 批量审批
```python
@approvals.route("/approvals/batch-approve", methods=["POST"])
@login_required
@require_leader
def batch_approve():
    ledger_ids = request.form.getlist("ledger_ids")
    
    for ledger_id in ledger_ids:
        ledger = Ledger.query.get(ledger_id)
        pending_valves = Valve.query.filter_by(
            ledger_id=ledger_id, 
            status="pending"
        ).all()
        
        for valve in pending_valves:
            valve.status = "approved"
            valve.approved_by = current_user.id
            valve.approved_at = datetime.utcnow()
        
        # 更新Ledger快照
        update_ledger_status(ledger)
        if ledger.status == "approved":
            ledger.approved_snapshot_status = "approved"
            ledger.approved_snapshot_at = datetime.utcnow()
        
        db.session.commit()
    
    flash(f"已审批 {len(ledger_ids)} 个台账合集")
    return redirect(url_for("approvals.index"))
```

#### 批量驳回
```python
@approvals.route("/approvals/batch-reject", methods=["POST"])
@login_required
@require_leader
def batch_reject():
    ledger_ids = request.form.getlist("ledger_ids")
    comment = request.form.get("comment", "")
    
    for ledger_id in ledger_ids:
        ledger = Ledger.query.get(ledger_id)
        pending_valves = Valve.query.filter_by(
            ledger_id=ledger_id, 
            status="pending"
        ).all()
        
        for valve in pending_valves:
            valve.status = "rejected"
        
        db.session.commit()
    
    flash(f"已驳回 {len(ledger_ids)} 个台账合集")
    return redirect(url_for("approvals.index"))
```

### 四、移除Ledger详情页审批功能

从 `ledgers/detail.html` 移除：
- 批量审批按钮
- 批量驳回按钮

保留功能：
- 提交审批按钮（普通员工提交自己的draft Valve）
- 查看详情功能

### 五、快照逻辑

#### 核心原则
1. Ledger首次完全审批通过时，记录快照时间和快照状态
2. 已审批Ledger中新增/编辑Valve，不会影响快照
3. 普通员工查看Ledger时：
   - Ledger列表：只能看到快照状态为已审批的Ledger
   - Valve列表：只能看到快照时间点之前审批的Valve

#### 实现方式
- 利用现有字段：`approved_snapshot_at` 和 `Valve.approved_at`
- 查询条件：`Valve.approved_at <= Ledger.approved_snapshot_at`

### 六、前端页面

#### 新增文件
- `templates/approvals/index.html` - 审批中心主页

#### 修改文件
- `templates/ledgers/list.html` - 移除审批相关按钮
- `templates/ledgers/detail.html` - 移除审批按钮
- `templates/base.html` - 侧边栏添加审批中心菜单

### 七、菜单配置

侧边栏菜单结构：
```
├── 仪表盘
├── 台账管理
│   ├── 全部台账
│   └── 我的台账
├── 审批中心（仅admin/leader）
│   └── 审批管理
├── 基础数据（仅admin）
└── 个人中心
```

## 实施步骤

1. 修改 `ledgers.py` 查询逻辑，过滤普通员工看到的Valve
2. 创建 `approvals.py` 路由文件
3. 创建 `templates/approvals/index.html` 模板
4. 修改侧边栏菜单，添加审批中心入口
5. 移除详情页审批按钮
6. 测试各角色权限和数据展示
