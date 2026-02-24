# 台账系统重构设计方案

## 一、需求概述

### 1.1 背景
当前系统为简单的"用户-台账内容"二级结构。业务需求是：一个员工管理多类台账，每类台账中有多条阀门内容。

### 1.2 目标架构
```
User（员工）→ 台账集合（Ledger）→ 台账内容（Valve）
```

### 1.3 核心原则
- **台账内容（Valve）功能完全沿用现有实现**，不做任何修改
- **界面流程**：台账集合列表 → 点击进入 → 看到的就是现有台账列表
- **界面布局原则**：
  - 顶部信息紧凑，单行显示
  - 界面主要空间留给表格控件
  - 搜索框、按钮等元素紧凑排列

---

## 二、数据模型设计

### 2.1 新增模型：Ledger（台账集合）

```python
class Ledger(db.Model):
    __tablename__ = "ledgers"
    id = db.Column(db.Integer, primary_key=True)
    
    名称 = db.Column(db.String(100), nullable=False)
    描述 = db.Column(db.Text)
    
    # 台账集合的状态
    status = db.Column(
        db.String(20), default="draft"
    )  # draft/pending/approved/rejected
    
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    approved_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    approved_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    creator = db.relationship("User", foreign_keys=[created_by])
    approver = db.relationship("User", foreign_keys=[approved_by])
```

### 2.2 修改模型：Valve

**不做任何修改**，保持现有结构不变。Valve 通过 `created_by` 直接关联 User。

### 2.3 修改模型：ApprovalLog

```python
class ApprovalLog(db.Model):
    __tablename__ = "approval_logs"
    id = db.Column(db.Integer, primary_key=True)
    
    # 增加 ledger_id，用于台账集合层级的审批记录
    ledger_id = db.Column(db.Integer, db.ForeignKey("ledgers.id"))
    valve_id = db.Column(db.Integer, db.ForeignKey("valves.id"), nullable=False)
    
    action = db.Column(db.String(20))  # submit/approve/reject
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    comment = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    ledger = db.relationship("Ledger", backref="approval_logs")
    valve = db.relationship("Valve", backref="approval_logs")
    user = db.relationship("User")
```

---

## 三、权限模型

| 角色 | 台账集合操作 | 台账内容操作 |
|------|--------------|--------------|
| 创建者 | 增删改查 | 增删改查 |
| Leader/Admin | 增删改查 | 增删改查 |
| 普通员工 | 仅查看 | 仅查看（现有逻辑） |

---

## 四、路由设计

### 4.1 新增路由

| 路由 | 方法 | 功能 |
|------|------|------|
| `/ledgers` | GET | 台账集合列表 |
| `/ledger/new` | GET/POST | 创建台账集合 |
| `/ledger/<int:id>` | GET | 台账集合详情（含其中所有台账内容） |
| `/ledger/<int:id>/edit` | GET/POST | 编辑台账集合 |
| `/ledger/<int:id>/delete` | POST | 删除台账集合 |
| `/ledger/<int:id>/submit` | POST | 提交台账集合审批（批量提交内所有台账内容） |
| `/ledger/<int:id>/approve` | POST | 审批通过台账集合 |
| `/ledger/<int:id>/reject` | POST | 驳回台账集合 |

### 4.2 现有路由保持不变

- `/valves` - 台账内容列表（显示所有，或可按 ledger 筛选）
- `/valve/new` - 新增台账内容
- `/valve/<id>` - 台账内容详情
- `/valve/edit/<id>` - 编辑台账内容
- `/approvals` - 审批页面

### 4.3 路由映射

```
/ledgers                    → 台账集合列表（新增）
/ledgers/<id>               → 台账集合详情（内含现有台账列表功能）
/ledgers/<id>/valves        → 等同于现有 /valves，但限定在该集合内
```

---

## 五、界面设计

### 5.1 台账集合列表页

**设计原则**：紧凑布局，主要展示表格

```
┌─────────────────────────────────────────────────────────────┐
│  台账集合                                            [+新建] │
├─────────────────────────────────────────────────────────────┤
│  [搜索......] [状态▼]                                      │
├─────────────────────────────────────────────────────────────┤
│  集合名称      │ 台账数 │ 状态    │ 操作                    │
│  ─────────────────────────────────────────────────────────│
│  一期装置      │  150   │ 已审批  │[查看][编辑]             │
│  二期仪表      │   80   │ 待审批  │[查看]                   │
│  备用阀门      │   25   │ 草稿    │[查看][编辑]             │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 台账集合详情页（点击进入后）

**设计原则**：顶部信息紧凑，界面主要展示表格控件

```
┌─────────────────────────────────────────────────────────────┐
│  ← 返回  一期装置阀门台账                          [编辑集合]│
├─────────────────────────────────────────────────────────────┤
│                                                            │
│  台账内容列表                                              │
│  ─────────────────────────────────────────────────────────│
│  [+新增]  [搜索......] [状态▼] [筛选]           [提交审批] │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ ☐ │ 位号    │ 名称     │ 装置名称 │ 状态    │ 操作   │  │
│  │ ─────────────────────────────────────────────────────│  │
│  │ ☑ │ FV-001  │ 调节阀A  │ 一期     │ 已审批  │详情编辑│  │
│  │ ☑ │ FV-002  │ 调节阀B  │ 一期     │ 待审批  │详情编辑│  │
│  └──────────────────────────────────────────────────────┘  │
│  已选择 2 项                              [批量审批] [驳回] │
└─────────────────────────────────────────────────────────────┘
```

**布局要点**：
- 顶部标题栏：紧凑单行显示，仅保留"返回链接 + 集合名称 + 编辑按钮"
- 工具栏：紧凑布局，搜索框和按钮紧凑排列
- 表格：撑满剩余空间
- 底部操作栏：紧凑显示选中数量和批量操作按钮

### 5.3 审批页面

现有审批页面保持不变，可选择：
- 按台账集合筛选（显示某集合内的待审批内容）
- 或在台账集合详情页进行批量审批

---

## 六、审批流程

### 6.1 方案一：台账集合整体审批

在台账集合详情页：
- 「提交审批」按钮 → 提交集合内所有"草稿"状态的台账内容
- 「批量审批」按钮 → 审批通过集合内选中的台账内容
- 「批量驳回」按钮 → 驳回集合内选中的台账内容

### 6.2 审批日志

```python
# 提交审批时
log = ApprovalLog(
    ledger_id=ledger_id,
    valve_id=valve.id,
    action="submit",
    user_id=current_user.id
)

# 审批通过时
log = ApprovalLog(
    ledger_id=ledger_id,
    valve_id=valve.id,
    action="approve",
    user_id=current_user.id,
    comment=request.form.get("comment", "")
)
```

---

## 七、数据迁移

由于数据库可删除重建：
1. 删除现有表（如需要）
2. 创建新表 Ledger
3. 创建/修改 ApprovalLog

---

## 八、实施步骤

### 第一步：数据模型
1. 创建 Ledger 模型
2. 修改 ApprovalLog 添加 ledger_id
3. 初始化数据库

### 第二步：台账集合 CRUD
1. 实现 Ledger 增删改查
2. 创建台账集合列表页面
3. 创建台账集合详情页面（复用现有台账列表）

### 第三步：集成审批
1. 在台账集合详情页添加批量审批功能
2. 实现提交审批功能

### 第四步：路由与导航
1. 更新导航菜单
2. 配置路由

---

## 九、注意事项

1. **现有 Valve 功能完全不变** - 增删改查、审批、导入导出等都保持原样
2. **新建设台账内容时可选择所属集合** - 在现有新增表单中增加"所属台账集合"下拉框
3. **现有台账内容可迁移到集合中** - 可选功能：为现有 Valve 批量指定 ledger_id
