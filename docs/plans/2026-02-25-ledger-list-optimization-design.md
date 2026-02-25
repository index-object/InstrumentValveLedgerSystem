# 台账列表界面优化设计方案

> **Date:** 2026-02-25
> **Status:** 已批准
> **Author:** OpenCode

## 需求概述

优化阀门台账列表界面 (`templates/valves/list.html`)：
1. 实现表头冻结 - 垂直滚动时表头保持固定可见
2. 紧凑工具栏布局 - 保留现有功能，优化布局

## 方案B：紧凑工具栏

### 架构设计

**修改文件：**
- `templates/valves/list.html`

**技术实现：**
- 使用 CSS `position: sticky` 实现表头冻结
- 保持现有右侧固定操作列
- 优化顶部批量工具栏布局

---

## 详细设计

### 1. 表头冻结实现

**目标：** 垂直滚动时表头保持固定可见

**实现方式：**
- 使用 `position: sticky` + `top: 0`
- 为 `thead` 设置固定高度和背景色
- 确保滚动容器正确设置 `overflow-y: auto`

**CSS 样式调整：**

```css
thead th {
    position: sticky;
    top: 0;
    z-index: 10;
    background: #f8f9fa;
}
```

**修改点：**
- 第99行：表格容器 `style` 添加 `position: relative`
- 第101-112行：表头分组行添加 `position: sticky; top: 0; z-index: 11;`
- 第113-146行：表头字段行添加 `position: sticky; top: 50px; z-index: 10;`

### 2. 紧凑工具栏布局

**当前状态：**
- 第50-96行：已有批量操作工具栏
- 第199-204行：右侧固定操作列（查看、编辑按钮）

**优化点：**
- 保持现有功能不变
- 优化按钮样式使其更紧凑
- 确保表头冻结不影响现有交互

---

## 数据流与交互

### 页面加载
1. Flask 传递 `valves`, `pagination`, `ledger`, `active_filters`, `filter_options` 等数据
2. 模板渲染表格和分页组件

### 表头冻结交互
- 用户垂直滚动时，表头固定在视口顶部
- 左侧复选框列保持固定 (`position: sticky; left: 0`)
- 右侧操作列保持固定 (`position: sticky; right: 0`)

---

## 验收标准

1. **表头冻结**
   - [ ] 垂直滚动时表头保持可见
   - [ ] 水平滚动时首尾列保持可见
   - [ ] 表头背景色正确，不透明

2. **功能完整性**
   - [ ] 搜索筛选功能正常
   - [ ] 批量操作功能正常
   - [ ] 分页功能正常
   - [ ] 新增/编辑/查看按钮正常

3. **兼容性**
   - [ ] Chrome/Edge 浏览器正常显示
   - [ ] 响应式布局无明显问题

---

## 风险与限制

- CSS `position: sticky` 在旧版浏览器可能不完全支持（IE11）
- 表头冻结可能与固定列样式产生 z-index 冲突
