# 仪表阀门台账管理系统 - 设计文档

**日期**: 2026-02-15

## 一、项目概述

仪表阀门台账管理系统是一个用于企业员工和领导共同管理仪表阀门数据的 Web 应用。系统支持基本的增删改查功能，包含审批工作流、数据导入导出、照片管理、维护记录等完整功能。

## 二、技术栈

| 技术 | 说明 |
|------|------|
| 后端 | Flask 3.x (Python) |
| 数据库 | SQLite |
| 前端 | Bootstrap 5 + Jinja2 模板 |
| Excel 处理 | pandas + openpyxl |
| PDF 导出 | WeasyPrint |

## 三、用户角色

| 角色 | 权限 |
|------|------|
| 员工 | 录入台账、提交申请、查看自己提交的数据 |
| 领导 | 审批（可选）、查看所有数据、管理后台 |

## 四、审批流程（可配置）

```python
# 系统设置
auto_approval = True  # 自动审批模式
```

- **自动审批模式 (auto_approval=True)**: 员工提交 → 系统自动通过 → 立即生效
- **手动审批模式 (auto_approval=False)**: 员工提交 → 领导审批 → 通过/驳回

## 五、数据库设计

### 5.1 users (用户表)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| username | String(50) | 用户名（唯一） |
| password_hash | String(200) | 密码哈希 |
| role | String(20) | 角色：employee / leader |
| real_name | String(50) | 真实姓名 |
| dept | String(50) | 部门 |
| status | String(20) | 状态：active / inactive |
| created_at | DateTime | 创建时间 |

### 5.2 valves (仪表阀门台账)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| 序号 | String(20) | 序号 |
| 装置名称 | String(100) | 装置名称 |
| 位号 | String(50) | 位号（唯一标识） |
| 名称 | String(100) | 设备名称 |
| 设备等级 | String(20) | 设备等级 |
| 型号规格 | String(100) | 型号规格 |
| 生产厂家 | String(100) | 生产厂家 |
| 安装位置及用途 | String(200) | 安装位置 |
| 工艺条件_介质名称 | String(50) | 介质名称 |
| 工艺条件_设计温度 | String(50) | 设计温度℃ |
| 工艺条件_阀前压力 | String(50) | 阀前压力MPa |
| 工艺条件_阀后压力 | String(50) | 阀后压力MPa |
| 阀体_公称通径 | String(50) | 公称通径 |
| 阀体_连接方式及规格 | String(100) | 连接方式及规格 |
| 阀体_材质 | String(50) | 阀体材质 |
| 阀内件_阀座直径 | String(50) | 阀座直径 |
| 阀内件_阀芯材质 | String(50) | 阀芯材质 |
| 阀内件_阀座材质 | String(50) | 阀座材质 |
| 阀内件_阀杆材质 | String(50) | 阀杆材质 |
| 阀内件_流量特性 | String(50) | 流量特性 |
| 阀内件_泄露等级 | String(50) | 泄露等级 |
| 阀内件_Cv值 | String(50) | Cv值 |
| 执行机构_形式 | String(50) | 执行机构形式 |
| 执行机构_型号规格 | String(100) | 型号规格 |
| 执行机构_厂家 | String(100) | 生产厂家 |
| 执行机构_作用形式 | String(50) | 作用形式 |
| 执行机构_行程 | String(50) | 行程 |
| 执行机构_弹簧范围 | String(50) | 弹簧范围 |
| 执行机构_气源压力 | String(50) | 气源压力 |
| 执行机构_故障位置 | String(50) | 故障位置 |
| 执行机构_关阀时间 | String(50) | 关阀时间 |
| 执行机构_开阀时间 | String(50) | 开阀时间 |
| 设备编号 | String(50) | 设备编号 |
| 是否联锁 | String(10) | 是否联锁 |
| 备注 | Text | 备注 |
| status | String(20) | 状态：draft/pending/approved/rejected |
| created_by | Integer | 创建人ID |
| approved_by | Integer | 审批人ID |
| approved_at | DateTime | 审批时间 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

### 5.3 valve_photos (照片表)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| valve_id | Integer | 外键关联 valves |
| filename | String(200) | 文件名 |
| description | String(200) | 描述 |
| uploaded_by | Integer | 上传人ID |
| uploaded_at | DateTime | 上传时间 |

### 5.4 maintenance_records (维护记录)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| valve_id | Integer | 外键关联 valves |
| 类型 | String(50) | 维修/检定/保养 |
| 日期 | Date | 维护日期 |
| 内容 | Text | 维护内容 |
| 负责人 | String(50) | 负责人 |
| created_by | Integer | 记录人ID |
| created_at | DateTime | 创建时间 |

### 5.5 approval_logs (审批日志)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| valve_id | Integer | 外键关联 valves |
| action | String(20) | submit/approve/reject |
| user_id | Integer | 操作人ID |
| comment | String(500) | 备注 |
| timestamp | DateTime | 操作时间 |

### 5.6 settings (系统设置)

| 字段 | 类型 | 说明 |
|------|------|------|
| key | String(50) | 设置键 |
| value | String(200) | 设置值 |

## 六、页面结构

| 路由 | 页面 | 说明 |
|------|------|------|
| `/` | 首页 | 统计仪表数量、待审批数量 |
| `/login` | 登录 | 用户登录 |
| `/logout` | 登出 | 退出登录 |
| `/valves` | 台账列表 | 搜索、筛选、导出 |
| `/valve/<id>` | 台账详情 | 查看完整信息、照片、历史 |
| `/valve/new` | 录入申请 | 填写台账信息 |
| `/valve/edit/<id>` | 编辑台账 | 编辑草稿状态的数据 |
| `/valve/delete/<id>` | 删除台账 | 逻辑删除 |
| `/my-applications` | 我的申请 | 查看提交记录、审批状态 |
| `/approvals` | 审批管理 | 手动模式下领导审批 |
| `/import` | Excel导入 | 批量导入台账数据 |
| `/export` | 数据导出 | 导出Excel/PDF |
| `/valve/<id>/photos` | 照片管理 | 上传/查看照片 |
| `/valve/<id>/maintenance` | 维护记录 | 添加维护记录 |
| `/admin` | 后台管理 | 用户管理 |
| `/admin/users` | 用户管理 | 添加/编辑/禁用用户 |
| `/admin/settings` | 系统设置 | 配置自动审批等 |

## 七、核心功能说明

### 7.1 审批工作流

1. **自动审批模式** (默认)
   - 员工提交申请后，系统自动审批通过
   - 台账状态：draft → approved

2. **手动审批模式**
   - 员工提交申请后，台账状态：draft → pending
   - 领导审批：pending → approved / rejected
   - 被驳回后，员工可修改重新提交

### 7.2 Excel 导入

- 读取 Excel 文件，解析台账数据
- 支持字段映射（Excel列名 → 数据库字段）
- 导入预览，确认后写入数据库

### 7.3 数据导出

- **Excel 导出**: 使用 pandas 导出完整台账
- **PDF 报表**: 使用 WeasyPrint 生成 PDF 报表

### 7.4 照片管理

- 支持上传仪表设备照片
- 照片与台账关联存储
- 详情页展示照片列表

## 八、安全性

- 密码使用 bcrypt 哈希存储
- 登录会话使用 Flask-Login 管理
- 路由权限检查装饰器
- 文件上传路径限制和验证
