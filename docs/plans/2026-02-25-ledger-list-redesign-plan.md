# 台账列表界面重构实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 紧凑化工具栏布局，扩大表格空间占比

**Architecture:** 修改 templates/valves/list.html 的 CSS 样式和 HTML 结构

**Tech Stack:** HTML, CSS (内联样式)

---

### Task 1: 紧凑化工具栏样式

**Files:**
- Modify: `templates/valves/list.html:23-44`

**Step 1: 修改搜索框尺寸**

修改 `header_actions` 块中的搜索框和筛选器样式：

```html
<!-- 修改搜索框 input -->
<input type="text" name="search" class="form-control form-control-modern" 
       placeholder="搜索所有字段..." value="{{ request.args.get('search', '') }}"
       style="height: 36px; padding-left: 32px; width: 180px;">

<!-- 修改状态筛选 select -->
<select name="status" class="form-control form-control-modern" 
        style="width: 110px; height: 36px; font-size: 13px;">
```

**Step 2: 修改按钮尺寸**

```html
<!-- 搜索按钮 -->
<button type="submit" class="btn btn-primary-custom" style="height: 36px; padding: 0 12px;">
    <i class="bi bi-search"></i>
</button>

<!-- 清除筛选按钮 -->
<a href="{{ url_for('valves.list') }}" class="btn btn-outline-secondary" style="height: 36px; padding: 0 12px;">
    <i class="bi bi-x-lg"></i>
</a>

<!-- 新增按钮 -->
<a href="{{ url_for('valves.new') }}" class="btn btn-accent" style="height: 36px; padding: 0 14px; font-size: 13px;">
    <i class="bi bi-plus-lg"></i> 新增
</a>
```

**Step 3: 修改 form 容器间距**

```html
<!-- 修改 form 样式 -->
<form method="get" class="d-flex gap-2 flex-wrap" style="align-items: center;">
```

---

### Task 1.1: 整合筛选条件提示到工具栏

**Files:**
- Modify: `templates/valves/list.html:83-88`

**Step 1: 将筛选条件提示移入工具栏**

原代码在 `header_actions` 块外部有独立显示区域，需要移除并整合：

```html
<!-- 原代码：第83-88行是单独的提示区域，需删除 -->
{% if active_filters %}
<div class="d-flex gap-2 align-items-center">
    <span class="badge bg-info">有筛选条件</span>
    <a href="..." class="btn btn-sm btn-outline-secondary">清除筛选</a>
</div>
{% endif %}
```

修改 `header_actions` 块末尾，添加筛选提示：

```html
<!-- 在搜索按钮后添加 -->
{% if active_filters %}
<span class="text-muted" style="border-left: 1px solid #dee2e6; padding-left: 8px; margin-left: 4px; font-size: 12px;">
    <i class="bi bi-funnel-fill text-info"></i> 筛选中
    <a href="..." style="margin-left: 4px;"><i class="bi bi-x-lg"></i></a>
</span>
{% endif %}
```

或者使用更简洁的方式，放在搜索框内右侧：

```html
<!-- 修改搜索框容器，添加筛选提示图标 -->
<div class="search-box" style="position: relative;">
    <i class="bi bi-search"></i>
    {% if active_filters %}
    <i class="bi bi-funnel-fill" style="position: absolute; right: 30px; top: 50%; transform: translateY(-50%); color: var(--primary-color); font-size: 12px;"></i>
    {% endif %}
    <input type="text" ...>
</div>
```

---

### Task 2: 扩大表格容器高度

**Files:**
- Modify: `templates/valves/list.html:97-99`

**Step 1: 修改表格容器高度为占满剩余空间**

```html
<!-- 原代码 -->
<div class="table-responsive" style="max-height: calc(100vh - 280px); overflow-y: auto; overflow-x: auto;">

<!-- 修改为 -->
<div class="table-responsive" style="height: calc(100vh - 180px); overflow-y: auto; overflow-x: auto;">
```

---

### Task 3: 精简分页组件

**Files:**
- Modify: `templates/valves/list.html:219-240`

**Step 1: 简化分页 HTML**

```html
<!-- 原分页结构 -->
<nav>
    <ul class="pagination-custom pagination mb-2">
        {% if pagination.has_prev %}
        <li class="page-item"><a class="page-link" href="...">上一页</a></li>
        {% endif %}
        
        {% for p in range(1, pagination.pages + 1) %}
        <li class="page-item {% if p == pagination.page %}active{% endif %}">
            <a class="page-link" href="...">{{ p }}</a>
        </li>
        {% endfor %}
        
        {% if pagination.has_next %}
        <li class="page-item"><a class="page-link" href="...">下一页</a></li>
        {% endif %}
    </ul>
</nav>
<small class="text-muted">共 {{ pagination.total }} 条记录，第 {{ pagination.page }}/{{ pagination.pages }} 页</small>

<!-- 修改为：精简版 -->
<div class="d-flex justify-content-between align-items-center p-2" style="border-top: 1px solid var(--border-color);">
    <small class="text-muted">共 {{ pagination.total }} 条记录，第 {{ pagination.page }}/{{ pagination.pages }} 页</small>
    <nav>
        <ul class="pagination-custom pagination mb-0" style="gap: 4px;">
            {% if pagination.has_prev %}
            <li class="page-item">
                <a class="page-link" style="padding: 4px 10px;" href="{% if ledger %}{{ url_for('ledgers.detail', id=ledger.id, page=pagination.prev_num) }}{% else %}{{ url_for('valves.list', page=pagination.prev_num) }}{% endif %}">
                    <i class="bi bi-chevron-left"></i> 上一页
                </a>
            </li>
            {% endif %}
            {% if pagination.has_next %}
            <li class="page-item">
                <a class="page-link" style="padding: 4px 10px;" href="{% if ledger %}{{ url_for('ledgers.detail', id=ledger.id, page=pagination.next_num) }}{% else %}{{ url_for('valves.list', page=pagination.next_num) }}{% endif %}">
                    下一页 <i class="bi bi-chevron-right"></i>
                </a>
            </li>
            {% endif %}
        </ul>
    </nav>
</div>
```

---

### Task 4: 调整顶部工具栏区块

**Files:**
- Modify: `templates/valves/list.html:47-96`

**Step 1: 紧凑化批量操作工具栏**

```html
<!-- 修改批量操作工具栏样式 -->
<div class="modern-card mb-2">  <!-- mb-3 改为 mb-2 -->
    <div class="d-flex justify-content-between align-items-center p-2" style="border-bottom: 1px solid var(--border-color);">  <!-- p-3 改为 p-2 -->
```

**Step 2: 调整内部元素间距**

```html
<!-- 选中信息区域 -->
<div class="d-flex align-items-center gap-2">  <!-- gap-3 改为 gap-2 -->
```

**Step 3: 调整按钮内边距**

```html
<!-- 批量审批/驳回按钮 -->
<button type="button" class="btn btn-sm btn-success" style="padding: 3px 10px; font-size: 12px;" onclick="submitBatchAction('batch_approve')">
    <i class="bi bi-check-lg"></i> 批量审批
</button>

<!-- 下拉菜单按钮 -->
<button class="btn btn-sm btn-secondary dropdown-toggle" style="padding: 3px 10px; font-size: 12px;" type="button" data-bs-toggle="dropdown">
```

---

### Task 5: 验证效果

**Step 1: 启动开发服务器**

```bash
cd G:\work\python\InstrumentValveLedgerSystem
uv run flask run --debug
```

**Step 2: 访问页面验证**

在浏览器中打开 http://127.0.0.1:5000/valves/list 检查：
1. 工具栏是否紧凑
2. 表格是否占满剩余高度
3. 分页是否精简

---

### Task 6: 提交代码

```bash
git add templates/valves/list.html
git commit -m "refactor: 紧凑化台账列表界面布局，扩大表格空间"
```
