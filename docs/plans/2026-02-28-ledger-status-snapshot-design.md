# 台账合集审批状态优化方案

## 需求背景

当前「全部台账」列表显示的是所有账号中台账合集（Ledger）为"已审批"状态的合集。但存在一个问题：**已审批的合集可以被修改，当修改后会变成草稿状态**，导致合集的状态显示混乱。

具体问题：
1. 用户修改已审批Ledger中的Valve内容时，Valve状态直接从approved变成draft
2. 这导致Ledger的display_status也变成draft
3. 在「全部台账」列表中，该Ledger不再显示（因为筛选的是approved）

用户期望：
- 本账号修改自己已审批的合集后，只有自己能看到状态变为草稿
- 「全部台账」那边还是显示已审批，只显示已审批过的内容

## 解决方案：双状态字段

### 核心思路

在Ledger模型中新增`approved_snapshot_status`字段（快照状态），记录审批通过时的状态快照：
- **快照状态**：记录审批通过时的状态，用于「全部台账」展示
- **实时状态**：当前实际状态，用于本账号查看

### 详细设计

#### 1. 数据模型变更

```python
# Ledger模型新增字段
approved_snapshot_status = db.Column(db.String(20), nullable=True)  # 审批快照状态
approved_snapshot_at = db.Column(db.DateTime, nullable=True)  # 快照生成时间
```

#### 2. 快照生成逻辑

当Ledger中所有Valve都审批通过时（`update_ledger_status`函数），生成快照：

```python
def update_ledger_status(ledger):
    total = Valve.query.filter_by(ledger_id=ledger.id).count()
    if total == 0:
        return
    
    approved = Valve.query.filter_by(ledger_id=ledger.id, status="approved").count()
    pending = Valve.query.filter_by(ledger_id=ledger.id, status="pending").count()
    rejected = Valve.query.filter_by(ledger_id=ledger.id, status="rejected").count()
    draft = Valve.query.filter_by(ledger_id=ledger.id, status="draft").count()
    
    # 计算实时状态
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

#### 3. 列表查询逻辑变更

「全部台账」列表读取快照状态：

```python
@ledgers.route("/ledgers")
@login_required
def list():
    query = Ledger.query
    
    # ...搜索过滤...
    
    # 状态过滤：根据用户角色和快照状态过滤
    status = request.args.get("status")
    if status:
        # 管理员/领导：按实时status过滤
        # 员工：按快照状态过滤
        if current_user.role == "employee":
            query = query.filter(Ledger.approved_snapshot_status == status)
        else:
            query = query.filter(Ledger.status == status)
    else:
        # 默认：员工只显示快照为approved的
        if current_user.role == "employee":
            query = query.filter(Ledger.approved_snapshot_status == "approved")
    
    ledgers_list = query.order_by(Ledger.created_at.desc()).all()
    
    # 计算显示状态：优先使用快照状态
    for ledger in ledgers_list:
        # 统计valve数量
        ledger.valve_count = Valve.query.filter_by(ledger_id=ledger.id).count()
        
        # 统计各状态数量
        ledger.pending_count = ...
        ledger.rejected_count = ...
        ledger.approved_count = ...
        ledger.draft_count = ...
        
        # 显示状态逻辑：
        # - 全部台账（员工视角）：使用快照状态
        # - 本账号（创建者/领导/管理员）：使用实时状态
        if current_user.role == "employee" or (not can_edit_ledger(ledger)):
            # 他人视角：使用快照状态
            ledger.display_status = ledger.approved_snapshot_status or "draft"
        else:
            # 自己视角：使用实时状态
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
    
    return render_template("ledgers/list.html", ledgers=ledgers_list)
```

#### 4. 详情页显示逻辑

在Ledger详情页，也需要区分显示：

```python
# 详情页显示逻辑
if current_user.role == "employee" or ledger.created_by != current_user.id:
    # 他人查看：显示快照状态
    show_status = ledger.approved_snapshot_status or "draft"
else:
    # 本人查看：显示实时状态
    show_status = ledger.display_status
```

#### 5. 数据迁移

为现有已审批的Ledger生成快照：

```python
# 迁移脚本
def migrate_approved_snapshots():
    ledgers = Ledger.query.filter_by(status="approved").all()
    for ledger in ledgers:
        ledger.approved_snapshot_status = "approved"
        ledger.approved_snapshot_at = ledger.approved_at
    db.session.commit()
```

### 页面展示

#### 「全部台账」列表（员工视角）
| 台账名称 | 状态 | 阀门数量 | 创建人 | 创建时间 |
|---------|------|----------|--------|----------|
| 仪表阀门台账A | 已审批 | 50 | 张三 | 2026-01-15 |
| 仪表阀门台账B | 已审批 | 30 | 李四 | 2026-01-20 |

#### 「我的台账」（本账号视角）
| 台账名称 | 状态 | 阀门数量 | 创建时间 |
|---------|------|----------|----------|
| 仪表阀门台账A | 草稿（已修改） | 50 | 2026-01-15 |
| 仪表阀门台账B | 已审批 | 30 | 2026-01-20 |

### 优点
1. 改动较小，不影响现有审批流程
2. 清晰区分"对外展示状态"和"内部实时状态"
3. 用户修改后自己可见状态变化，符合同事人预期
4. 「全部台账」保持显示已审批，内容一致性与稳定性

### 潜在问题
1. 快照状态与实时状态可能不一致，需在UI上明确区分
2. 当Ledger被删除时，快照数据需要同步处理
3. 初始数据迁移需要确保快照字段有值
