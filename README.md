# 仪表阀门台账管理系统

基于 Flask 构建的工业仪表阀门台账管理系统，用于管理企业仪表阀门的设备信息、检修记录和审批流程。

## 功能特性

- **用户管理**：支持员工、班长、管理员三种角色，完整的权限控制
- **阀门台账**：记录阀门的基本信息、工艺条件、阀体规格、执行机构参数等
- **审批流程**：支持阀门信息的提交、审批（通过/驳回）流程
- **照片管理**：为阀门上传和管理现场照片
- **附件管理**：管理阀门相关技术文档
- **检修记录**：记录阀门的维护检修历史
- **Excel 导入**：支持从 Excel 文件批量导入阀门数据

## 技术栈

- **后端**：Flask + SQLAlchemy
- **前端**：HTML + CSS + JavaScript (Bootstrap 5)
- **数据库**：SQLite
- **认证**：Flask-Login

## 项目结构

```
InstrumentValveLedgerSystem/
├── app/
│   ├── __init__.py          # 应用工厂
│   ├── models.py            # 数据库模型
│   └── routes/              # 路由模块
│       ├── auth.py          # 认证路由
│       ├── valves.py        # 阀门管理路由
│       └── admin.py         # 管理后台路由
├── templates/                # Jinja2 模板
├── tests/                   # 单元测试
├── config.py                # 配置文件
├── main.py                  # 应用入口
└── requirements.txt         # 依赖列表
```

## 快速开始

### 1. 克隆项目

```bash
git clone <repository-url>
cd InstrumentValveLedgerSystem
```

### 2. 创建虚拟环境

```bash
# 使用 uv（推荐）
uv venv
uv pip install -r requirements.txt

# 或使用 pip
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

### 3. 初始化数据库

```bash
python init_db.py
```

这将创建默认管理员账户：
- 用户名：`admin`
- 密码：`admin123`

### 4. 运行应用

```bash
python main.py
```

访问 http://127.0.0.1:5000

## 用户角色

| 角色 | 权限 |
|------|------|
| employee（员工） | 创建、查看阀门台账，提交审批申请 |
| leader（班长） | 审批所属部门的阀门申请 |
| admin（管理员） | 用户管理、系统设置、全部数据权限 |

## 目录说明

- `uploads/` - 上传的文件存储目录
- `instance/` - SQLite 数据库文件
- `docs/plans/` - 开发设计文档

## 许可证

MIT License
