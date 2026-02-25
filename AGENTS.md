# AGENTS.md - 开发指南

本文件为智能代理（agent）提供项目开发规范和操作指南。

## 1. 项目概述

- **项目名称**：仪表阀门台账管理系统
- **技术栈**：Flask + SQLAlchemy + Flask-Login + Bootstrap 5
- **Python 版本**：>= 3.12
- **数据库**：SQLite（默认）
- **包管理**：使用 uv 管理依赖

## 2. 开发命令

### 2.1 环境初始化

```bash
# 创建虚拟环境
uv venv

# 安装依赖
uv pip install -r requirements.txt
# 或
pip install -r requirements.txt
```

### 2.2 运行应用

```bash
# 启动开发服务器
python main.py
# 或
flask run

# 访问地址：http://127.0.0.1:5000
```

### 2.3 数据库初始化

```bash
python init_db.py
# 创建默认管理员账户：admin / admin123
```

### 2.4 测试命令

```bash
# 运行所有测试
pytest

# 运行单个测试文件
pytest tests/test_auth.py

# 运行单个测试函数
pytest tests/test_auth.py::test_login_success

# 运行测试并显示详细输出
pytest -v

# 运行测试并显示 print 输出
pytest -s

# 生成测试覆盖率报告
pytest --cov=app --cov-report=html
```

### 2.5 Lint 和代码检查

项目使用 ruff 作为 linter（如已安装）：

```bash
# 检查代码问题
ruff check .

# 自动修复问题
ruff check . --fix

# 格式化代码
ruff format .
```

## 3. 代码风格规范

### 3.1 导入规范

- 标准库导入放在最前面
- 第三方库导入放在中间
- 本地应用导入放在最后
- 各组之间用空行分隔

```python
# 正确示例
import os
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError

from app.models import db, User, Valve
```

### 3.2 命名规范

| 类型 | 命名规则 | 示例 |
|------|----------|------|
| 变量/函数 | 小写字母 + 下划线 | `user_id`, `get_valve_list()` |
| 类名 | 大驼峰 | `User`, `ValveModel` |
| 常量 | 全大写 + 下划线 | `MAX_FILE_SIZE`, `ALLOWED_EXTENSIONS` |
| 数据库表字段 | 中文（业务术语） | `位号`, `装置名称`, `设备编号` |
| 蓝图名称 | 小写 + 下划线 | `auth`, `valves`, `admin` |
| 路由函数 | 小写 + 下划线 | `def login():`, `def list():` |

### 3.3 类型注解

- 推荐为函数参数和返回值添加类型注解
- 使用 Python 3.12+ 的类型注解语法

```python
# 推荐
def get_valve_by_id(valve_id: int) -> Valve | None:
    return Valve.query.get(valve_id)

# 复杂类型使用 TYPE_CHECKING
from __future__ import annotations
```

### 3.4 代码格式化

- 使用 ruff 格式化工具（已集成于项目）
- 缩进：4 空格
- 行长度：建议不超过 120 字符
- 函数/方法之间用空行分隔

### 3.5 错误处理

#### 路由层错误处理

- 使用 `flash()` 展示用户友好的错误信息
- 使用 `redirect()` 和 `url_for()` 进行页面跳转
- 使用 `get_or_404()` 处理资源不存在的情况

```python
# 正确示例
valve = Valve.query.get_or_404(id)
# 或
if not valve:
    flash("台账不存在")
    return redirect(url_for("valves.list"))
```

#### 异常捕获

```python
try:
    db.session.add(valve)
    db.session.commit()
except IntegrityError:
    db.session.rollback()
    flash("位号已存在，请使用其他位号")
    return redirect(url_for("valves.new"))
```

### 3.6 数据库操作

- 使用 SQLAlchemy ORM 进行数据库操作
- 提交事务后使用 `db.session.commit()`
- 发生异常时使用 `db.session.rollback()`

```python
# 正确示例
try:
    valve = Valve(位号=位号, 名称=名称)
    db.session.add(valve)
    db.session.commit()
except Exception as e:
    db.session.rollback()
    flash(f"操作失败: {str(e)}")
```

### 3.7 权限控制

- 使用 `@login_required` 装饰器保护需要登录的路由
- 使用 `current_user.role` 检查用户角色
- 页面权限检查在视图函数内完成

```python
@valves.route("/valve/delete/<int:id>", methods=["POST"])
@login_required
def delete(id):
    valve = Valve.query.get_or_404(id)
    can_delete = valve.created_by == current_user.id or current_user.role in [
        "leader",
        "admin",
    ]
    if not can_delete:
        flash("无权删除")
        return redirect(url_for("valves.detail", id=id))
```

### 3.8 模板和前端

- 使用 Jinja2 模板引擎
- 模板文件放在 `templates/` 目录
- 静态文件放在 `static/` 目录（如有）
- 使用 Bootstrap 5 进行 UI 开发

### 3.9 测试规范

- 测试文件放在 `tests/` 目录
- 测试文件命名：`test_*.py`
- 测试函数命名：`test_*`
- 使用 pytest fixtures 管理测试依赖

```python
# 测试示例
def test_login_success(client, init_database):
    response = client.post('/login', data={
        'username': 'admin',
        'password': 'admin123'
    }, follow_redirects=True)
    assert response.status_code == 200
```

### 3.10 注意事项

1. **数据库字段**：本项目使用中文命名数据库字段（如 `位号`, `名称`），这是业务需求，必须保留
2. **代码注释**：不主动添加注释，除非解释复杂的业务逻辑
3. **Git 提交**：提交前确保所有测试通过
4. **敏感信息**：不要提交 `.env` 文件或包含密钥的文件

## 4. 项目结构

```
InstrumentValveLedgerSystem/
├── app/
│   ├── __init__.py          # Flask 应用工厂
│   ├── models.py            # 数据库模型
│   └── routes/              # 路由模块
│       ├── auth.py          # 认证路由
│       ├── valves.py        # 阀门管理路由
│       ├── admin.py         # 管理后台路由
│       └── ledgers.py       # 台账路由
├── templates/                # Jinja2 模板
├── tests/                   # 单元测试
│   ├── conftest.py          # pytest fixtures
│   ├── test_auth.py         # 认证测试
│   └── test_index.py        # 首页测试
├── config.py                # 配置文件
├── main.py                  # 应用入口
├── init_db.py               # 数据库初始化
└── requirements.txt         # 依赖列表
```

## 5. 常用操作

### 5.1 创建新模型

在 `app/models.py` 中定义，继承 `db.Model`：

```python
class NewModel(db.Model):
    __tablename__ = "new_models"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

### 5.2 创建新路由

在 `app/routes/` 目录下创建新的 Blueprint 文件：

```python
from flask import Blueprint

bp = Blueprint("new_module", __name__, url_prefix="/new")

@bp.route("/")
def index():
    return render_template("new/index.html")
```

然后在 `app/__init__.py` 中注册 Blueprint。

### 5.3 添加新测试

在 `tests/` 目录下创建测试文件，使用现有 fixtures：

```python
def test_new_feature(client, init_database):
    # 测试代码
    pass
```
