# 首页优化实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 优化首页展示，将以单条记录为单位改为以台账合集为单位显示统计数据

**Architecture:** 修改首页路由数据获取逻辑，新增两个页面路由（我的台账合集列表、我的审批申请），更新首页模板展示

**Tech Stack:** Flask, SQLAlchemy, Jinja2

---

## 任务总览

| 任务 | 描述 |
|------|------|
| Task 1 | 修改首页路由数据逻辑 |
| Task 2 | 修改首页模板卡片显示 |
| Task 3 | 新增 /my-ledgers 路由和模板 |
| Task 4 | 新增 /my-ledger-applications 路由和模板 |
| Task 5 | 测试验证 |

---

## Task 1: 修改首页路由数据逻辑

**Files:**
- Modify: `app/routes/__init__.py`

**Step 1: 查看现有代码并修改**

修改 `app/routes/__init__.py` 中的 index 函数，将统计数据改为按合集统计：

```python
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import Valve, MaintenanceRecord, User, Ledger

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def index():
    # 全部台账 - 合集数量和记录总数
    total_ledgers = Ledger.query.count()
    total_valves = Valve.query.count()
    
    # 我的台账 - 用户创建的合集和记录数
    my_ledger_count = Ledger.query.filter_by(created_by=current_user.id).count()
    my_valve_count = Valve.query.join(Ledger).filter(Ledger.created_by == current_user.id).count()
    
    # 我的申请 - 用户提交的待审批合集
    my_pending_ledgers = (
        Ledger.query
        .join(Valve, Ledger.id == Valve.ledger_id)
        .filter(Ledger.created_by == current_user.id, Valve.status == "pending")
        .distinct()
        .count()
    )
    
    # 待审批（管理员/领导）
    if current_user.role in ["leader", "admin"]:
        pending_valves = Valve.query.filter_by(status="pending").count()
    else:
        pending_valves = my_pending_ledgers
    
    maintenance_count = MaintenanceRecord.query.count()

    user_stats = []
    if current_user.role in ["leader", "admin"]:
        users = User.query.filter_by(status="active").all()
        for user in users:
            count = Valve.query.filter_by(created_by=user.id).count()
            user_stats.append(
                {"username": user.real_name or user.username, "count": count}
            )

    return render_template(
        "index.html",
        total_ledgers=total_ledgers,
        total_valves=total_valves,
        my_ledger_count=my_ledger_count,
        my_valve_count=my_valve_count,
        my_pending_ledgers=my_pending_ledgers,
        pending=pending_valves,
        maintenance_count=maintenance_count,
        user_stats=user_stats,
    )


from app.routes import auth, valves, admin
```

**Step 2: 运行应用测试**

```bash
python main.py
```

访问 http://127.0.0.1:5000/ 验证首页正常加载

---

## Task 2: 修改首页模板卡片显示

**Files:**
- Modify: `templates/index.html`

**Step 1: 修改模板**

在 `templates/index.html` 中找到统计卡片部分，修改显示逻辑：

修改"我的台账"卡片（大约178-187行）：
```html
<a href="{{ url_for('valves.my_ledgers') }}" class="stat-card">
    <div class="stat-icon primary">
        <i class="bi bi-bookmark-heart"></i>
    </div>
    <div class="stat-content">
        <h3>{{ my_ledger_count }} 个合集<br><small style="font-size:14px;color:var(--text-muted)">共 {{ my_valve_count }} 条记录</small></h3>
        <p>我的台账</p>
    </div>
</a>
```

修改"全部台账"卡片（大约203-211行）：
```html
<a href="{{ url_for('ledgers.list') }}" class="stat-card">
    <div class="stat-icon info">
        <i class="bi bi-list-columns"></i>
    </div>
    <div class="stat-content">
        <h3>{{ total_ledgers }} 个合集<br><small style="font-size:14px;color:var(--text-muted)">共 {{ total_valves }} 条记录</small></h3>
        <p>全部台账</p>
    </div>
</a>
```

修改"我的申请"卡片（大约233-244行）：
```html
<a href="{{ url_for('valves.my_ledger_applications') }}" class="stat-card">
    <div class="stat-icon success" style="position: relative;">
        <i class="bi bi-file-earmark-check"></i>
        {% if my_pending_ledgers > 0 %}
        <span style="position: absolute; top: -5px; right: -5px; width: 12px; height: 12px; background: #ef4444; border-radius: 50%; border: 2px solid white;"></span>
        {% endif %}
    </div>
    <div class="stat-content">
        <h3>{{ my_pending_ledgers }} 个待审批</h3>
        <p>我的申请</p>
    </div>
</a>
```

同时删除"待审批"卡片（管理员），因为已经合并到"我的申请"

**Step 2: 验证显示**

刷新首页查看卡片显示是否正确

---

## Task 3: 新增 /my-ledgers 路由和模板

**Files:**
- Modify: `app/routes/valves.py` (末尾添加)
- Create: `templates/valves/my_ledgers.html`

**Step 1: 添加路由**

在 `app/routes/valves.py` 末尾添加：

```python
@valves.route("/my-ledgers")
@login_required
def my_ledgers():
    """我的台账合集列表"""
    query = Ledger.query.filter_by(created_by=current_user.id)
    
    search = request.args.get("search")
    if search:
        query = query.filter(Ledger.名称.contains(search))

    status = request.args.get("status")
    if status:
        query = query.filter(Ledger.status == status)

    ledgers_list = query.order_by(Ledger.created_at.desc()).all()

    for ledger in ledgers_list:
        ledger.valve_count = Valve.query.filter_by(ledger_id=ledger.id).count()
        ledger.pending_count = Valve.query.filter_by(
            ledger_id=ledger.id, status="pending"
        ).count()
        ledger.rejected_count = Valve.query.filter_by(
            ledger_id=ledger.id, status="rejected"
        ).count()
        ledger.approved_count = Valve.query.filter_by(
            ledger_id=ledger.id, status="approved"
        ).count()
        ledger.draft_count = Valve.query.filter_by(
            ledger_id=ledger.id, status="draft"
        ).count()

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

    return render_template("valves/my_ledgers.html", ledgers=ledgers_list)
```

**Step 2: 创建模板**

创建 `templates/valves/my_ledgers.html`：

```html
{% extends "base.html" %}

{% block page_title %}我的台账合集{% endblock %}

{% block extra_css %}
<style>
    .ledger-card {
        background: white;
        border-radius: var(--radius-md);
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: var(--shadow-sm);
        border: 1px solid var(--border-color);
        transition: all 0.2s ease;
    }
    .ledger-card:hover {
        box-shadow: var(--shadow-md);
        border-color: var(--primary-light);
    }
    .ledger-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 12px;
    }
    .ledger-title {
        font-size: 18px;
        font-weight: 600;
        color: var(--text-dark);
        margin: 0;
    }
    .ledger-desc {
        color: var(--text-muted);
        font-size: 14px;
        margin-top: 4px;
    }
    .ledger-stats {
        display: flex;
        gap: 16px;
        flex-wrap: wrap;
    }
    .stat-item {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 13px;
    }
    .stat-item .badge {
        font-size: 12px;
        padding: 2px 8px;
    }
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 500;
    }
    .status-badge.draft { background: #e2e8f0; color: #475569; }
    .status-badge.pending { background: #fef3c7; color: #92400e; }
    .status-badge.approved { background: #d1fae5; color: #065f46; }
    .status-badge.rejected { background: #fee2e2; color: #991b1b; }
</style>
{% endblock %}

{% block content %}
<div class="main-body">
    <div class="page-header">
        <h4>我的台账合集</h4>
    </div>
    
    <div class="toolbar">
        <a href="{{ url_for('ledgers.new') }}" class="btn btn-primary">
            <i class="bi bi-plus-lg"></i> 新建合集
        </a>
    </div>
    
    {% if ledgers %}
    <div class="ledger-list">
        {% for ledger in ledgers %}
        <a href="{{ url_for('ledgers.detail', id=ledger.id) }}" class="ledger-card" style="text-decoration:none;display:block;color:inherit;">
            <div class="ledger-header">
                <div>
                    <h5 class="ledger-title">{{ ledger.名称 }}</h5>
                    {% if ledger.描述 %}
                    <p class="ledger-desc">{{ ledger.描述 }}</p>
                    {% endif %}
                </div>
                <span class="status-badge {{ ledger.display_status }}">
                    {% if ledger.display_status == 'draft' %}草稿
                    {% elif ledger.display_status == 'pending' %}待审批
                    {% elif ledger.display_status == 'approved' %}已通过
                    {% elif ledger.display_status == 'rejected' %}已驳回
                    {% endif %}
                </span>
            </div>
            <div class="ledger-stats">
                <div class="stat-item">
                    <span class="badge bg-secondary">{{ ledger.valve_count }}</span> 条记录
                </div>
                {% if ledger.pending_count > 0 %}
                <div class="stat-item">
                    <span class="badge bg-warning">{{ ledger.pending_count }}</span> 待审批
                </div>
                {% endif %}
                {% if ledger.approved_count > 0 %}
                <div class="stat-item">
                    <span class="badge bg-success">{{ ledger.approved_count }}</span> 已通过
                </div>
                {% endif %}
                {% if ledger.draft_count > 0 %}
                <div class="stat-item">
                    <span class="badge bg-secondary">{{ ledger.draft_count }}</span> 草稿
                </div>
                {% endif %}
            </div>
        </a>
        {% endfor %}
    </div>
    {% else %}
    <div class="empty-state">
        <i class="bi bi-inbox" style="font-size: 48px; color: #cbd5e1;"></i>
        <p>暂无台账合集</p>
        <a href="{{ url_for('ledgers.new') }}" class="btn btn-primary">创建第一个合集</a>
    </div>
    {% endif %}
</div>
{% endblock %}
```

**Step 3: 注册路由**

确保在 `app/routes/valves.py` 顶部导入 Ledger:
```python
from app.models import db, Valve, Setting, ApprovalLog, User, ValveAttachment, Ledger
```

---

## Task 4: 新增 /my-ledger-applications 路由和模板

**Files:**
- Modify: `app/routes/valves.py`
- Create: `templates/valves/my_ledger_applications.html`

**Step 1: 添加路由**

在 `app/routes/valves.py` 中添加：

```python
@valves.route("/my-ledger-applications")
@login_required
def my_ledger_applications():
    """我的审批申请 - 按合集显示"""
    # 查询用户创建的包含待审批内容的合集
    ledgers = (
        Ledger.query
        .join(Valve, Ledger.id == Valve.ledger_id)
        .filter(
            Ledger.created_by == current_user.id,
            Valve.status == "pending"
        )
        .distinct()
        .all()
    )
    
    for ledger in ledgers:
        ledger.pending_count = Valve.query.filter_by(
            ledger_id=ledger.id, status="pending"
        ).count()
        ledger.total_count = Valve.query.filter_by(ledger_id=ledger.id).count()
    
    return render_template("valves/my_ledger_applications.html", ledgers=ledgers)
```

**Step 2: 创建模板**

创建 `templates/valves/my_ledger_applications.html`：

```html
{% extends "base.html" %}

{% block page_title %}我的申请{% endblock %}

{% block extra_css %}
<style>
    .application-card {
        background: white;
        border-radius: var(--radius-md);
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: var(--shadow-sm);
        border: 1px solid var(--border-color);
        transition: all 0.2s ease;
    }
    .application-card:hover {
        box-shadow: var(--shadow-md);
        border-color: var(--primary-light);
    }
    .app-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
    }
    .app-title {
        font-size: 18px;
        font-weight: 600;
        color: var(--text-dark);
        margin: 0;
    }
    .app-stats {
        display: flex;
        gap: 16px;
    }
    .stat-badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 13px;
        font-weight: 500;
    }
    .stat-badge.pending {
        background: #fef3c7;
        color: #92400e;
    }
    .stat-badge.info {
        background: #e0f2fe;
        color: #0369a1;
    }
</style>
{% endblock %}

{% block content %}
<div class="main-body">
    <div class="page-header">
        <h4>我的申请</h4>
    </div>
    
    {% if ledgers %}
    <div class="application-list">
        {% for ledger in ledgers %}
        <div class="application-card">
            <div class="app-header">
                <h5 class="app-title">{{ ledger.名称 }}</h5>
                <span class="stat-badge pending">
                    <i class="bi bi-clock"></i> {{ ledger.pending_count }} 项待审批
                </span>
            </div>
            <div class="app-stats">
                <span class="stat-badge info">
                    <i class="bi bi-collection"></i> 共 {{ ledger.total_count }} 条记录
                </span>
            </div>
            <div style="margin-top: 12px;">
                <a href="{{ url_for('ledgers.detail', id=ledger.id) }}" class="btn btn-sm btn-outline-primary">查看详情</a>
            </div>
        </div>
        {% endfor %}
    </div>
    {% else %}
    <div class="empty-state">
        <i class="bi bi-check-circle" style="font-size: 48px; color: #86efac;"></i>
        <p>暂无待审批的申请</p>
    </div>
    {% endif %}
</div>
{% endblock %}
```

---

## Task 5: 测试验证

**Step 1: 运行测试**

```bash
pytest tests/ -v
```

**Step 2: 手动测试**

1. 使用普通员工账号登录
2. 访问首页，确认卡片显示正确
3. 点击"我的台账"，确认跳转到 `/my-ledgers`
4. 点击"全部台账"，确认跳转到 `/ledgers`
5. 点击"我的申请"，确认跳转到 `/my-ledger-applications`

**Step 3: 使用管理员账号测试**

1. 登录管理员账号
2. 确认首页显示正确

---

## 执行选择

**Plan complete and saved to `docs/plans/2026-02-25-homepage-optimization-design.md`**

**Two execution options:**

1. **Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

2. **Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
