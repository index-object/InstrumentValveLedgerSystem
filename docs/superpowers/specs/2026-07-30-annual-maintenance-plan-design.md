# 年度阀门检修计划功能 — 设计文档

## 1. 背景

当前系统已有阀门台账管理和维护记录功能，但缺乏**检修计划**维度。领导无法统一发布检修任务，员工缺乏待办提醒，计划执行进度不可视。本功能填补这一空白。

## 2. 需求概要

| 角色 | 需求 |
|------|------|
| 领导 | 创建/发布检修计划，从已审批阀门中选择项，设置计划日期范围，查看执行进度看板 |
| 员工 | 收到计划发布通知，查看计划中的待办阀门项，预警即将过期/已逾期项，创建维护记录时关联计划项自动推进进度 |
| 管理员 | 拥有领导全部权限，可管理所有计划 |

## 3. 数据模型

### 3.1 MaintenancePlan（检修计划主表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | int | PK | |
| title | varchar(200) | NOT NULL | 计划标题 |
| description | text | NULL | 计划描述 |
| status | varchar(20) | NOT NULL, default=draft | draft / published / archived |
| total_items | int | default=0 | 总阀门项数（冗余） |
| completed_items | int | default=0 | 已完成项数（冗余） |
| created_by | int | FK→users.id | 创建人 |
| published_by | int | FK→users.id, NULL | 发布人 |
| published_at | datetime | NULL | 发布时间 |
| created_at | datetime | default=utcnow | |
| updated_at | datetime | onupdate=utcnow | |

### 3.2 MaintenancePlanItem（计划明细项）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | int | PK | |
| plan_id | int | FK→maintenance_plans.id, NOT NULL | 所属计划 |
| device_type | varchar(20) | NOT NULL | 阀门/设备类型 |
| device_id | int | NOT NULL | 对应阀门表主键 ID |
| tag | varchar(50) | NOT NULL | 位号（冗余，方便显示和搜索） |
| device_name | varchar(100) | NULL | 设备名称（冗余） |
| planned_date_start | date | NOT NULL | 计划开始日期 |
| planned_date_end | date | NOT NULL | 计划截止日期 |
| status | varchar(20) | NOT NULL, default=pending | pending / completed / overdue |
| maintenance_id | int | FK→maintenance_records.id, NULL | 关联的实际维护记录 ID |
| completed_at | datetime | NULL | 实际完成时间 |
| completed_by | int | FK→users.id, NULL | 完成人 |
| created_at | datetime | default=utcnow | |

说明：
- device_type + device_id 为多态关联，覆盖现有所有阀门类型和仪表类型
- tag 冗余存储用于列表展示和搜索，避免跨表 join
- 系统自动根据当前日期与计划截止日期计算 overdue 状态（非持久化或在查询时计算）
- maintenance_id 被更新时，同步更新 status、completed_at、completed_by

### 3.3 Notification（通知消息）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | int | PK | |
| user_id | int | FK→users.id | 接收人 |
| type | varchar(20) | NOT NULL | plan_published / plan_reminder |
| title | varchar(200) | NOT NULL | 通知标题 |
| content | text | NULL | 通知内容 |
| ref_type | varchar(20) | NULL | 关联对象类型（plan） |
| ref_id | int | NULL | 关联对象 ID |
| is_read | bool | default=false | |
| created_at | datetime | default=utcnow | |

## 4. 路由设计

### 4.1 计划主路由

| 方法 | 路由 | 视图函数 | 权限 | 说明 |
|------|------|----------|------|------|
| GET | `/plans` | `plans.list` | 全部登录 | 计划列表（员工仅看到已发布/已归档，领导+管理员看到全部） |
| GET/POST | `/plan/new` | `plans.create` | leader/admin | 新建计划 |
| GET | `/plan/<id>` | `plans.detail` | 全部登录 | 计划详情+进度 |
| GET/POST | `/plan/<id>/edit` | `plans.edit` | leader/admin | 编辑（draft 状态） |
| POST | `/plan/<id>/publish` | `plans.publish` | leader/admin | 发布（draft→published，创建通知） |
| POST | `/plan/<id>/archive` | `plans.archive` | leader/admin | 归档 |
| POST | `/plan/<id>/delete` | `plans.delete` | leader/admin | 删除（draft 状态） |

### 4.2 计划项路由

| 方法 | 路由 | 视图函数 | 权限 | 说明 |
|------|------|----------|------|------|
| POST | `/plan/<id>/items/add` | `plans.add_items` | leader/admin | 批量添加阀门项 |
| POST | `/plan/<id>/items/<item_id>/remove` | `plans.remove_item` | leader/admin | 移除单条计划项 |
| GET | `/plan/<id>/items/<item_id>` | `plans.item_detail` | 全部登录 | 单项详情（含关联维护记录） |

### 4.3 员工端路由

| 方法 | 路由 | 视图函数 | 权限 | 说明 |
|------|------|----------|------|------|
| GET | `/plans/early-warning` | `plans.early_warning` | employee/admin | 预警列表（即将到期+逾期） |
| POST | `/maintenance/new` | (扩展现有) | employee/admin | 创建维护记录时增加 plan_item_id 参数 |

### 4.4 通知路由

| 方法 | 路由 | 视图函数 | 说明 |
|------|------|----------|------|
| GET | `/notifications` | `notifications.list` | 通知列表 |
| POST | `/notifications/<id>/read` | `notifications.mark_read` | 标记已读 |
| POST | `/notifications/read-all` | `notifications.read_all` | 全部标记已读 |
| GET | `/notifications/unread-count` | `notifications.unread_count` | 未读数量（AJAX） |

## 5. 权限设计

| 操作 | 员工 | 领导 | 管理员 |
|------|------|------|--------|
| 查看计划列表 | 仅已发布+已归档 | 全部 | 全部 |
| 查看计划详情 | 已发布+已归档 | 全部 | 全部 |
| 创建/编辑计划 | ❌ | ✓ | ✓ |
| 发布计划 | ❌ | ✓ | ✓ |
| 归档/删除计划 | ❌ | ✓ | ✓ |
| 添加/移除阀门项 | ❌ | ✓ | ✓ |
| 查看预警看板 | ✓ | ❌ | ✓ |
| 关联维护记录到计划项 | ✓ | ❌ | ✓ |
| 收到发布通知 | ✓ | ❌ | ✓ |

## 6. 核心交互流程

### 6.1 领导发布计划

```
领导 → /plans/new (填写标题/描述)
     → 保存为草稿 (status=draft)
     → /plan/<id>/edit → 点击「添加阀门」
         → 弹窗：从已审批 (status=approved) 阀门中搜索/筛选/批量勾选
         → 设置计划开始/截止日期（支持批量设置）
     → /plan/<id>/publish
         → status=published, published_at=now
         → 为所有 employee 角色用户创建 Notification
         → 跳转到计划详情页
```

### 6.2 员工处理检修任务

```
员工收到通知／看到预警数字 → /plans/early-warning
     → 按紧急度列出待处理项（逾期 > 即将到期 > 本月到期）
     → 点击某行「创建维护记录」
     → /maintenance/new?plan_item=<id>
         → 表单预填位号、设备名称、装置名称
         → 顶部提示关联的计划信息
         → 员工补充检修时间、人员、内容 → 提交
     → 系统自动：
         1. 创建 MaintenanceRecord
         2. 更新 MaintenancePlanItem.maintenance_id / status / completed_at
         3. 更新 MaintenancePlan.completed_items（+1）
```

### 6.3 进度追踪

```
领导 → /plan/<id>
     → 环形图显示完成率
     → 统计卡片：已完成 / 待办 / 逾期
     → 下方计划项表格（可搜索/筛选状态）
```

## 7. 与现有系统的集成

### 7.1 侧边导航栏

```
领导导航：
  📋 台账管理 > ......
  📋 检修计划      ← 新增
  📋 审批中心 > ......
  ...

员工导航：
  📋 台账管理 > ......
  📋 检修计划      ← 新增
  📋 检修预警      ← 新增（带未读逾期数量徽标）
  📋 维护记录 > ......
```

### 7.2 首页统计卡片

**员工首页**新增检修预警卡片：
```
显示「X 项即将到期 · Y 项已逾期」
点击跳转到 /plans/early-warning
```

**领导首页**新增检修计划卡片：
```
显示「已发布计划数 · 总完成率」
点击跳转到 /plans
```

### 7.3 维护记录表单扩展

- 在现有 `maintenance/create.html` 表单底部增加「关联检修计划」下拉选择框
- 选项来源：当前设备所有 status=pending 的 MaintenancePlanItem
- 如从预警页跳转，自动预选并锁定关联项
- 提交时传递 plan_item_id，后端更新关联

### 7.4 维护记录列表扩展

- 全局维护记录列表 / 阀门详情维护记录列表 增加「所属计划」列
- 关联计划项的记录显示计划名称链接，可点击跳转到计划详情

## 8. 通知系统设计

### 8.1 触发点

- 计划发布时 → 向所有 employee/admin 角色用户创建通知
- 可选：计划项逾期时 → 向相关员工创建提醒（二期）

### 8.2 通知样式

```
顶部导航栏右侧增加铃铛图标
未读时显示红色数字徽标
点击弹出通知下拉列表
点击单条跳转到对应计划详情
```

## 9. 预警算法

`/plans/early-warning` 的查询逻辑：

```
SELECT * FROM maintenance_plan_items
WHERE plan_id IN (已发布计划IDs)
  AND status = 'pending'
  AND planned_date_end >= 当前日期 - 7天  -- 逾期+7天内到期
ORDER BY
  CASE WHEN planned_date_end < 当前日期 THEN 0 ELSE 1 END,  -- 逾期优先
  planned_date_end ASC  -- 按紧急度升序
```

前端分类展示：
- **已逾期**：planned_date_end < 当前日期
- **即将到期**：当前日期 ≤ planned_date_end ≤ 当前日期+7天

## 10. 关联的阀门口

系统已有的相关模型和路由计划保持不动，新增独立蓝图 `plans_bp`，不侵入现有阀门/维护路由。与现有系统唯一交叉点是：

1. 计划项添加时查 `已审批阀门`（跨所有 valve 表 + 非阀门设备表）
2. 维护记录创建/编辑时，多传递一个 `plan_item_id` 参数
3. 导航栏/首页增加入口

## 11. 不与实现的

- 周期性自动生成下一项（已确认跳过）
- 计划审批流（已有阀门审批流，计划本身不走审批）
- 定时任务/自动提醒（二期）
- Excel 批量导入导出计划项（一期只做手动选择）
- 计划模板复用
- 员工维度过滤（员工能看到全部已发布计划项，不按班组过滤）

## 12. 测试要点

- 计划 CRUD 权限测试（领导可创建/发布，员工只能查看）
- 发布后通知生成验证
- 维护记录关联计划项后状态更新验证
- 逾期状态计算逻辑
- 预警列表排序和分类
