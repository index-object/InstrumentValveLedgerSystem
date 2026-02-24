# 台账集合批量保存与审批重构方案

**日期**: 2026-02-24

## 1. 目标

重构台账保存、提交审批相关逻辑，将现有的"单个台账保存草稿→提交审批"流程改为"台账集合批量管理"模式。

## 2. 核心流程

```
创建台账集合 → 添加台账(手动/导入) → 保存草稿 → 提交审批 → 审批通过
     ↓               ↓              ↓           ↓
  Ledger      Valve(draft)    批量更新      批量更新      Ledger+Valve
                                                    状态同步
```

## 3. 数据模型变更

### 3.1 Ledger 模型

添加字段：

```python
class Ledger(db.Model):
    # ... 现有字段 ...
    
    # 记录当前集合包含的台账数量
    valve_count = db.Column(db.Integer, default=0)
    
    # 记录待审批数量
    pending_count = db.Column(db.Integer, default=0)
```

### 3.2 Valve 模型

- 约束 `ledger_id` 必填（移除独立 Valve）
- 状态与 Ledger 强绑定

## 4. 状态机

```
Ledger: draft → pending → approved/rejected
                ↓
Valve:      draft → pending → approved/rejected

约束规则：
- Ledger = draft 时，内部所有 Valve 必须为 draft
- Ledger = pending 时，内部所有 Valve 必须为 pending  
- Ledger = approved/rejected 时，内部 Valve 同状态
```

## 5. 路由设计

### 5.1 集合管理

| 路由 | 方法 | 说明 |
|------|------|------|
| `/ledgers` | GET | 集合列表 |
| `/ledger/new` | GET/POST | 创建集合 |
| `/ledger/<id>` | GET | 集合详情+台账列表 |
| `/ledger/<id>/edit` | GET/POST | 编辑集合信息 |
| `/ledger/<id>/delete` | POST | 删除集合 |

### 5.2 审批流程

| 路由 | 方法 | 说明 |
|------|------|------|
| `/ledger/<id>/submit` | POST | 提交审批（部分/全部台账） |
| `/ledger/<id>/approve` | POST | 审批通过（批量） |
| `/ledger/<id>/reject` | POST | 审批驳回（批量） |

### 5.3 台账操作

| 路由 | 方法 | 说明 |
|------|------|------|
| `/ledger/<id>/valve/new` | GET/POST | 新增单个台账 |
| `/ledger/<id>/valve/edit/<id>` | GET/POST | 编辑单个台账 |
| `/ledger/<id>/valve/delete/<id>` | POST | 删除单个台账 |
| `/ledger/<id>/valve/batch-delete` | POST | 批量删除台账 |
| `/ledger/<id>/import` | GET/POST | 批量导入台账 |

### 5.4 移除的路由

- `/valves/*` 独立台账入口全部移除

## 6. 业务逻辑

### 6.1 创建台账

- 用户创建 Ledger（台账集合）
- 在 Ledger 内添加 Valve（台账）
- 新增台账默认 status = "draft"
- 支持手动填写和 Excel 批量导入

### 6.2 提交审批

- 用户选择要提交审批的台账（支持部分提交）
- 选中台账 status: draft → pending
- Ledger.status: draft → pending
- 更新 Ledger.valve_count, pending_count

### 6.3 审批操作

- 审批通过：所有 pending 台账 status → approved
- 审批驳回：所有 pending 台账 status → rejected
- Ledger 状态同步更新

### 6.4 数据清理

- 重构初始化时，删除所有无 ledger_id 的独立 Valve

## 7. 前端页面

现有页面保持不变：

- `ledgers/list.html` - 集合列表
- `ledgers/form.html` - 集合表单
- `valves/list.html` - 台账列表（在 Ledger 内）
- `valves/form.html` - 台账表单
- `valves/detail.html` - 台账详情
- `valves/import.html` - 导入页面

## 8. 权限控制

| 操作 | 权限 |
|------|------|
| 创建台账集合 | 登录用户 |
| 在集合内添加台账 | 集合创建者 / leader / admin |
| 批量保存草稿 | 集合创建者 / leader / admin |
| 提交集合审批 | 集合创建者 |
| 审批/驳回集合 | leader / admin |

## 9. 待确认细节

- [x] 台账数据来源：手动 + 导入
- [x] 审批粒度：部分提交 + 整体审批
- [x] 草稿保存方式：保持现有单个台账保存
- [x] 独立台账：强制绑定 Ledger，清理现有数据
- [x] 路由整合：移除独立入口，统一到集合管理
- [x] 前端页面：保持不变
