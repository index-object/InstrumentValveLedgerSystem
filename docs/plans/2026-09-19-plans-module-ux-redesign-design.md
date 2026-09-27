# 检修计划模块 UI 重构设计方案

> 状态：已评审通过并实施完毕
> 日期：2026-09-19
> 分支：`feature/plans-ux-redesign`
> 范围：`app/routes/plans.py`、`templates/plans/*`、`templates/maintenance/*`、`app/__init__.py`、`app/models.py`、`static/css/components.css`
> 依据：`design-prototypes/plans-employee-early-warning.html`、`plans-employee-list.html`、`plans-leader-list.html`、`maintenance-create-with-plan.html`

## 评审确认的四项决策

| # | 决策 | 落地情况 |
|---|---|---|
| 1 | `published` 的中文显示改为「进行中」 | 已实现（底层状态值仍为 `published`，仅统一展示文案） |
| 2 | 直接做全量结构重构，不采用折中方案 A | 已实现：新增 `maintenance_plan_groups` 表，组级字段上移 |
| 3 | 直接删除 `completed_items` 冗余列 | 已实现：迁移脚本 `DROP COLUMN`，归档通知改为实时统计 |
| 4 | 计划可同时纳管阀门与其他仪表；阀门须关联维护记录完成，其他仪表由被指派账号确认完成并记录完成时间；阀门与仪表的计划条目要分开 | 已实现：任务组带 `category`（valve/instrument），表单与详情页均分区展示；两类完成路径分离 |

## 一、需求来源：用户反馈原话

1. **点开检修计划不知道如何完成。**
2. **发布检修计划后没有很直观的进度追踪。**
3. **看到"逾期""已完成"等字样忍不住想点一下。**
4. **"归档"是什么意思？**

四条反馈指向三个根因，后文所有设计都围绕这三个根因展开：

| 根因 | 说明 | 对应反馈 |
|---|---|---|
| R1 完成入口缺失且不对等 | 阀门类计划项的完成按钮不存在于计划页，必须自己去"维护记录"新建；而非阀门类项有内联"确认"按钮 | 1 |
| R2 进度呈现层级错误 | 进度只看列表页一个 6px 细条；种别页没有"我还要做什么"的任务视图；两页口径不一致 | 2 |
| R3 状态词与动作词混用 | 徽章和按钮共用"已完成"三个字；归档术语未解释；视觉上都是小圆角块，看起来都可点 | 3、4 |

## 二、现状问题清单（含代码位置）

### 2.1 完成路径问题（R1）

| 编号 | 问题 | 位置 |
|---|---|---|
| P1 | 阀门类计划项在计划详情页**完全没有完成入口**。`confirm_item` 明确拒绝阀门类型并 flash "阀门类型需通过维护记录完成"，但页面上没有任何跳转到维护记录新建的链接 | `app/routes/plans.py:370-372`；`templates/plans/detail.html:142-146` |
| P2 | 非阀门类项有内联"确认"按钮，且只对 `current_user.role == 'employee'` 显示，管理员点不了 | `templates/plans/detail.html:142` |
| P3 | 维护记录新建页的"归属检修计划"下拉**只在已选设备存在待办计划项时才显示**（`display:none`），并且标签写"归属年度计划"、说明写"该设备有待完成的年度保养计划项"——"年度/保养"是错的，计划里也可能有维修、校验 | `templates/maintenance/create.html:41-48` |
| P4 | 计划项可能包含非阀门仪表（`_approved_devices()` 遍历 `DeviceTypeRegistry.all()`），但维护记录新建页的设备来源是 `get_all_valve_models()`，**根本选不到非阀门仪表**，一旦关联还会静默失败（设备类型不匹配即不更新计划项） | `app/routes/plans.py:13-28`；`app/routes/valves/attachments.py:229-232、267-276` |
| P5 | 完成后的正向反馈只有一句 "确认完成"，不告知计划进度是否推进、推进到多少 | `app/routes/plans.py:378` |

### 2.2 进度追踪问题（R2）

| 编号 | 问题 | 位置 |
|---|---|---|
| P6 | 进度条只存在于领导/管理员的列表卡片，且仅 6px 高、仅 `published` 显示；草稿只显示"X 项" | `templates/plans/list.html:51-67` |
| P7 | 详情页的环形图 + 三格统计**仅对 `published` 渲染**，草稿计划详情页一个数字都没有 | `templates/plans/detail.html:60-101` |
| P8 | 员工看到的是**整份计划**的完成率/待办/逾期，而不是"我负责的 N 项"。计划详情页的后端统计不分接收人，前端也不区分 | `app/routes/plans.py:201-203`；`templates/plans/detail.html:81-100` |
| P9 | 列表页"逾期"数也是整份计划口径，员工会误以为自己逾期 | `app/routes/plans.py:149`；`templates/plans/list.html:64` |
| P10 | 侧边栏"检修计划"红色角标统计的是**所有已发布计划的待办项**，不按 `plan_recipients` 过滤，员工看到的是全厂数字 | `app/__init__.py:59-74` |
| P11 | 角标点击后落到计划列表，**没有任何"按紧急度排列的预警视图"**（原型 `plans-employee-early-warning.html` 已给出设计，未实现） | `templates/base.html:72-77` |
| P12 | 列表页对每个计划单独查一次 items（N+1），计划一多明显变慢 | `app/routes/plans.py:146-152` |

### 2.3 状态词 / 交互误导问题（R3）

| 编号 | 问题 | 位置 |
|---|---|---|
| P13 | "已完成"既做状态徽章（`cmp-badge--approved`）又做按钮（`cmp-toolbar-btn--secondary`），两者文字完全相同 | `templates/plans/list.html:41 vs 75`；`templates/plans/detail.html:15 vs 24` |
| P14 | 该按钮的实际动作是 `archive()`，语义是"归档/结束计划"，却显示为"已完成"；原型里这个动作就叫"归档" | `app/routes/plans.py:311-336` |
| P15 | 归档按钮**没有二次确认**，而删除有确认——不可逆操作反而没保护 | `templates/plans/list.html:74-76 vs 79` |
| P16 | 同一状态两套视觉：列表页"已发布"用 `cmp-badge--pending` + 时钟图标，详情页"已发布"用 `cmp-badge--approved` + 对勾 | `templates/plans/list.html:40` vs `templates/plans/detail.html:12-15` |
| P17 | 徽章与按钮本身样式确实有区分（徽章 20px 圆角/12px/无 pointer，按钮 6px/13px/有 pointer），但**文字相同**的情况下用户不会去观察圆角差异；且详情页的"确认"按钮（`btn-outline-success`）与位号徽章（`tag-badge`）尺寸接近、都带边框，紧挨在一起显示，进一步加剧混淆 | `static/css/components.css:43-49 vs 146-150`；`templates/plans/detail.html:136-146` |
| P18 | 术语未解释："草稿 / 已发布 / 已完成" 与动作"发布 / 归档 / 删除"之间没有映射说明 | 全局 |

### 2.4 顺带发现的错误信息（必须修）

| 编号 | 问题 | 位置 |
|---|---|---|
| P19 | 归档通知文案"共完成 {completed_items}/{total_items}"中的 `completed_items` **全项目无任何地方写入**，永远是 0。这是一条发给全体接收人的错误通知 | `app/models.py:269`；`app/routes/plans.py:328` |
| P20 | 详情页表头写"设备名称"，单元格里显示的是**位号标签** | `templates/plans/detail.html:118 vs 133-147` |
| P21 | "状态"列先判逾期再判已完成，导致同时"已完成+逾期"的项只显示"逾期"，与上方统计卡的"已完成"对不上 | `templates/plans/detail.html:157-161` |
| P22 | 编辑草稿时 `delete()` 全部计划项后重新插入，`group_id` 按新行序重编号；已关联的维护记录会留下错位/悬空关联 | `app/routes/plans.py:260-261` |
| P23 | 位号选择器勾选状态是全局的，不按行隔离；"全选"会选中被搜索隐藏的行；"确认添加"缺 `activeRow` 兜底会静默无响应 | `templates/plans/form.html:271-300` |
| P24 | 表单"检修时间"只有一个日期输入，但 `planned_date_start` 和 `planned_date_end` 都被赋成同一个值；UI 却处处暗示它是一个区间（原型显示"计划：05-01 ~ 05-15"） | `templates/plans/form.html:66、161`；`app/routes/plans.py:72-73` |
| P25 | 输入日期后整行被 JS 自动重排，用户正在填的内容会跳走，且无法撤销 | `templates/plans/form.html:231-242、252` |
| P26 | 状态筛选下拉切换时会丢掉 `search` 参数 | `templates/plans/list.html:20` |
| P27 | 发布弹窗未勾选任何接收人时仍会发布计划，只是不通知任何人；用户以为"取消选择=取消发布" | `app/routes/plans.py:289-307` |

## 三、设计目标与原则

1. **每一处状态文字都不可点，每一处可点的都是动作词。** 状态一律用徽章（无 hover 位移、无边框、cursor 默认），动作一律用按钮（有边框/背景、hover 有反馈、cursor pointer）。
2. **每个计划项都有唯一且显式的"完成它"入口，且从计划页一跳直达。**
3. **进度分三个层次呈现**：计划总进度（领导）、我的任务进度（员工）、单条任务状态（明细行）。
4. **术语收敛**：统一为 `草稿 → 已发布 → 已完成`；动作统一为 `发布`、`标记完成`、`删除`。彻底移除"归档"一词。
5. **不破坏已有数据**，数据库变更必须可回滚、可重复执行。

## 四、方案设计

### 4.1 第一档：语义与交互纠正

#### 4.1.1 状态徽章 / 动作按钮彻底分家

新增两组 CSS 类到 `static/css/components.css`，并在模板中强制区分使用：

- `.cmp-badge--status-*`：`cursor: default; user-select: none;`，移除任何 hover 效果，左侧统一带一个状态圆点。
- `.cmp-btn--action`：明确按钮外观（边框 + 背景），`:hover` 有 `translateY(-1px)` 与阴影，`:active` 有按下态。

状态视觉规范（唯一真源，列表页与详情页共用同一个宏）：

| 状态 | 文案 | 颜色 | 图标 |
|---|---|---|---|
| draft | 草稿 | 灰 | `bi-pencil` |
| published | 进行中 | 蓝 | `bi-play-circle` |
| archived | 已完成 | 绿 | `bi-check-circle-fill` |

> 说明：`published` 的中文从"已发布"改为"进行中"。理由：员工看到"已发布"不知道和自己有什么关系；"进行中"直接对应"还要做"的心智，和 R2 一致。底层状态值 `published` 不变。

新增 `templates/macros/status.html`，提供 `plan_status_badge(status)` 与 `item_status_badge(item)` 两个宏，替换掉现在散落在三个模板里的硬编码徽章。

#### 4.1.2 "归档"改为"标记完成"并加确认

- 按钮文案：`<i class="bi bi-check2-circle"></i> 标记完成`（列表页与详情页一致）。
- 点击后弹出确认框，内容明确说明不可逆：**"标记完成后计划将结束，员工端不再显示待办任务。已完成 12/48 项，剩余 36 项将标记为未完成。确认继续？"**
- 后端 `archive()` 增加一处：确认时若仍有 pending 项，在 flash 中告知"计划已结束，其中 N 项未完成"（`app/routes/plans.py:335`）。
- 删除按钮保留确认；草稿卡片也补上删除入口，不用再点进详情页。

#### 4.1.3 修复错误信息

| 编号 | 修法 |
|---|---|
| P19 | `completed_items` 改为实时计算后写入：在 `confirm_item`、维护记录创建/编辑、`_save_items` 后统一调用 `_recalc_plan_progress(plan)`，或者更稳妥——**直接删掉该字段的读取**，通知文案改为在 `archive()` 内用 `MaintenancePlanItem.query` 实时统计。建议后者（少一处可失效的冗余字段） |
| P20 | 详情页列头"设备名称"改为"设备位号"，并在每个位号徽章下方以 12px 灰字显示设备名称（数据已有 `device_name`） |
| P21 | "状态"列改为：**状态徽章在前，逾期以红色小角标追加在后面**，如"⏱ 已完成 · ⚠ 逾期 3 天"，两者并存 |
| P26 | 状态筛选改为受控 `onchange` 提交表单，保留当前 `search` 值 |
| P27 | 未勾选任何接收人时，`发布` 按钮改为二次确认"当前未选择通知对象，发布后员工端将看不到此计划。确认发布？" |

#### 4.1.4 计划时间改为显式区间

- 表单列头拆成**「计划开始」+「计划结束」**两个 `<input type="date">`。
- 保留 `planned_date_start/planned_date_end` 两字段，`_save_items` 不再把二者赋同一个值。
- 兼容：编辑旧数据时若 `start == end`，第二个输入框保持同值，用户可自行拉开。
- 逾期判定**仍然以 `planned_date_end` 为准**，但在详情页把该列头标注为「计划结束（截止）」，让语义自解释。
- 详情页、列表页、预警页统一显示为 `2026-05-01 ~ 2026-05-15`；过期未完成的显示 `2026-05-15（已逾期 3 天）`。

#### 4.1.5 表单交互修正

- 移除 `sortByDate()` 的自动重排；改为表格工具栏上一个显式的**「按计划结束日期排序」**按钮，点击后排序并 toast 提示"已按日期排序"。
- 位号选择器：勾选集合改为按行隔离（每次打开弹窗时，用当前行的 `_devs` 初始化勾选态；关闭时清空）。
- "全选"只作用于当前可见（未被搜索/装置过滤隐藏）的行。
- `pickerConfirm` 增加 `if (!activeRow) { 提示"请先选择要添加到的行"; return; }`。
- "检修项目"列宽 150px → 200px；"项目负责人/检修负责人"由 textarea 改为单行 input（`quality_acceptance` 保留 textarea，它是真多值）。
- 去掉 `.form-control::placeholder { line-height: 6.5em }` 这个把占位符垂直居中的 hack（`templates/plans/form.html:20-23`）。

### 4.2 第二档：员工端任务与预警视图（核心）

这一档直接解决反馈 1 和 2。

#### 4.2.1 新增"我的检修任务"页面

- 路由：`GET /my/plan-tasks`，函数 `plans.my_tasks()`。
- 数据：当前用户为接收人的所有 `published` 计划下的 `pending` 项，**按 `planned_date_end` 升序**。不按计划分组——员工要的是"下一个要干什么"，不是"哪个计划"。
- 顶部预警统计三卡（对应原型）：`已逾期 N 项` / `7 天内到期 N 项` / `30 天内到期 N 项`。
- 每条任务卡片包含：**剩余天数或逾期天数（最大号字体）**、位号 + 设备名称、装置名称、所属计划标题、计划区间、以及一个主按钮：
  - 阀门/仪表类 → **`去创建维护记录`**，链接 `url_for('valves.maintenance_create', plan_item_id=item.id)`。
  - 当前无法建维护记录的类型 → **`直接标记完成`**（复用 `confirm_item`）。
- 空态：`当前没有待完成的检修任务`。

#### 4.2.2 维护记录新建页支持从计划项直接进入

- `maintenance_create()` 接收 `plan_item_id` 查询参数：预选好设备、展开"归属计划"区块、把下拉选中该计划项。
- 计划项下拉的说明文案修正：`归属年度计划` → **`关联检修计划（完成并保存后，计划进度自动推进）`**；删除"年度保养"字样。
- **下拉列表只列出与当前用户相关的计划项**（接收人包含自己），不再列出全厂待办。
- **同时修 P4**：设备选择器数据源从 `get_all_valve_models()` 改为所有已审批仪表（复用 `plans._approved_devices()` 同一份注册表遍历逻辑，抽成公共函数）。否则计划里的非阀门仪表永远无法通过维护记录完成。

#### 4.2.3 保存后给正向反馈

`maintenance_create()` 提交成功后，若关联了 `plan_item_id`，flash 改为：

> **检修记录已保存，计划项 XV-301 已完成（本计划进度 32/48）**

这样员工每次完成都知道自己在推动什么，直接回应反馈 2。

#### 4.2.4 列表页按角色分流

- **员工**：页面标题下先渲染一条预警横幅（复用原型 `plans-employee-list.html` 的样式）："您有 2 项已逾期、3 项即将到期，点击查看 →"，点击进入 `/my/plan-tasks`。卡片上的进度改为**"我的进度 3/5"**，不显示全计划口径数字。
- **领导/管理员**：统计四卡保留，卡片进度条加粗到 10px，并**草稿也显示"共 N 项 · 待发布"**（不显示完成率，因为还没开始）。
- 侧边栏角标（`app/__init__.py:59-74`）改为按 `plan_recipients` 过滤当前用户，保证角标数字与"我的检修任务"页面第一条统计一致。

#### 4.2.5 侧边栏导航调整

`检修计划` 保持指向 `/plans`（作为总览），新增 `检修预警` 菜单项（仅员工/管理员可见）指向 `/my/plan-tasks`，带红色角标。这对应原型 `plans-employee-early-warning.html` 的导航结构。

### 4.3 第三档：结构重构

#### 4.3.1 详情页信息架构重排

现在详情页是"一张大表 + 顶部装饰性统计"，重排为三层：

```
┌─────────────────────────────────────────────┐
│ 第一层：计划头                              │
│  标题 · 状态徽章 · 计划区间 · 创建人/时间    │
│  大号进度：32/48 已完成（进度条 10px）      │
│  [我的任务 5 项]  [标记完成]  [删除]        │
├─────────────────────────────────────────────┤
│ 第二层：任务视图（默认展开）                │
│  员工：我的任务卡片列表（同 4.2.1 组件）    │
│  领导：按状态分组（逾期 / 待办 / 已完成）   │
├─────────────────────────────────────────────┤
│ 第三层：计划明细表（默认折叠，供查阅）      │
│  保留现有只读大表，折叠按钮"展开完整明细"   │
└─────────────────────────────────────────────┘
```

关键点：**只读大表从"主视图"降级为"参考视图"**。这是反馈 1 的根治——现在员工打开详情页面对的是 11 列、1200px 宽的表，找不到自己该做什么。

- 草稿计划也显示第一层（进度显示为 `0/48 · 未发布`）。
- 环形图移除（三格统计已经足够，环形图占 1/3 宽度却只表达一个百分比）。

#### 4.3.2 显式的"任务组 / 任务项"两级模型（可选，风险项）

当前用 `MaintenancePlanItem.group_id`（Integer，无外键）隐式表达"一行 = 一组设备 + 一套检修参数"，导致：

- `_load_rows()` 靠 `group_id` 反推分组（`app/routes/plans.py:98-125`）；
- 编辑时全删重建，`group_id` 被按新行序重编号（P22）；
- 无法表达"一组的计划区间是区间"（因为每组所有 item 的 start/end 都被写成同一个值）。

**方案 A（低风险，未采用）**：不动表结构，只改写入逻辑（增量 UPDATE 而非全删重建）。

**方案 B（彻底，已采用）**：新增 `maintenance_plan_groups` 表承载组级字段（区间、检修项目、方案、安全措施、负责人等），`MaintenancePlanItem` 只保留设备 + 状态 + 关联，并由任务组的 `category` 区分阀门/其他仪表。

**评审决定：采用方案 B。** 理由是当前仍是测试版、风险可控，而 A 无法表达"阀门与仪表分别成组"这一新增需求，也无法让组区间成为真正的区间语义。

落地后的模型关系：

```
MaintenancePlan 1 ── n MaintenancePlanGroup 1 ── n MaintenancePlanItem
                          │
                          ├─ category = valve | instrument
                          ├─ planned_date_start / planned_date_end（区间）
                          └─ 检修项目 / 方案 / 安全措施 / 负责人 / 质量验收 / 备注
```

`MaintenancePlanItem` 上仍保留一份 `planned_date_start/end` 冗余，写入时与所属任务组保持一致；这样逾期判定与预警查询不必每次都 join 组表。组内计划项与组区间的日期一致性由 `_save_rows` 保证，迁移脚本在回填后也做了一次对齐。

> 已知取舍：`MaintenancePlanItem.category` 未落库，而是通过 `group.category` 获取。这样避免了同一条明细出现两个类别字段而不一致，代价是列表页按类别过滤时需要 join 组表。


#### 4.3.3 列表页性能

`app/routes/plans.py:146-152` 的逐个查询改为一次聚合查询：

```python
from sqlalchemy import func, case
rows = db.session.query(
    MaintenancePlanItem.plan_id,
    func.count(MaintenancePlanItem.id),
    func.sum(case((MaintenancePlanItem.status == "completed", 1), else_=0)),
).group_by(MaintenancePlanItem.plan_id).all()
```

逾期数仍需 Python 侧按 `_is_overdue` 规则计算（涉及完成时间比较），但改为一次性取回所有相关 item 后内存计算，避免 N+1。

## 五、实施步骤

| 阶段 | 任务 | 主要文件 | 预估 |
|---|---|---|---|
| S1 | 新增状态徽章/动作按钮 CSS 与宏；三处模板替换 | `static/css/components.css`、`templates/macros/status.html`、`templates/plans/*.html` | 小 |
| S2 | 修 P19~P27 的错误信息与交互（归档→标记完成、确认弹窗、列头、状态列、筛选保留搜索、发布二次确认、start/end 区间、移除自动排序、选择器隔离） | `app/routes/plans.py`、`templates/plans/form.html`、`list.html`、`detail.html` | 中 |
| S3 | 新增 `/my/plan-tasks` 路由 + 模板 + 侧边栏入口 + 角标按接收人过滤 | `app/routes/plans.py`、`templates/plans/my_tasks.html`、`templates/base.html`、`app/__init__.py` | 中 |
| S4 | 维护记录新建页支持 `plan_item_id` 直达、下拉文案与数据源修正、保存后进度反馈 | `app/routes/valves/attachments.py`、`templates/maintenance/create.html` | 中 |
| S5 | 详情页三层重排 + 列表页角色分流 + N+1 修复 | `templates/plans/detail.html`、`list.html`、`app/routes/plans.py` | 大 |
| S6 | 方案 B：新增任务组表、组级字段上移、编辑改增量更新 | `app/models.py`、`app/routes/plans.py`、`migrations/migrate_plan_groups.py` | 大 |
| S7 | 测试补齐与回归 | `tests/test_maintenance_plan.py`、`tests/test_plans_ux_flow.py` | 中 |

## 六、数据库变更与迁移

### 结构变更

| 变更 | 对象 | 说明 |
|---|---|---|
| 新增表 | `maintenance_plan_groups` | 承载组级字段：`category`、计划区间、检修项目/方案/安全措施/负责人/质量验收/备注、`sort_order` |
| 改外键 | `maintenance_plan_items.group_id` | 由无外键的整数改为指向 `maintenance_plan_groups.id` |
| 删列 | `maintenance_plan_items` 的 7 个组级字段 | `maintenance_project`、`maintenance_scheme`、`safety_measures`、`project_leader`、`maintenance_leader`、`quality_acceptance`、`remark` |
| 删列 | `maintenance_plans.completed_items` | 从未被写入过，归档通知文案曾因此永远显示 0 |
| 保留列 | `maintenance_plan_items.planned_date_start/end` | 冗余保留，与所属任务组一致，供逾期判定与预警查询直接使用 |

### 迁移脚本

`migrations/migrate_plan_groups.py`，用法：

```bash
uv run python migrations/migrate_plan_groups.py            # 迁移项目根目录 valves.db
uv run python migrations/migrate_plan_groups.py <db路径>    # 迁移指定库
```

兼容两种历史结构：

- **A：已有 `group_id` 且计划项上有组级字段**（表单化之后的版本）→ 按 `(plan_id, group_id)` 建组，回填组级字段；
- **B：无 `group_id`、也无组级字段**（更早的版本）→ 计划内明细视为一组，用该类别明细的最早/最晚日期作为组区间，再按阀门/仪表拆分。

脚本特性：

- **幂等**：组表已有数据即跳过回填；删列步骤独立判断，任一步中断后重跑可补齐。
- **空操作安全**：计划表不存在或已是新结构时直接返回，不做任何改动。
- **防串号**：新组先落在临时 ID 区间（+1000000）再回落，避免与尚未处理的旧 `group_id` 撞号。
- **兜底校验**：迁移末尾断言"不存在未挂组的计划项"，不通过则整体回滚并报错。
- **只增不删**：不删除任何计划、计划项或维护记录；已关联的 `maintenance_id` 全部保留。

### 迁移验证结果

| 验证对象 | 结果 |
|---|---|
| 合成的旧结构库（含混合类别组、跨计划同号组） | 12 项挂组、混合组正确拆分、维护记录关联保留、跨计划不串组 |
| 真实历史备份 `valves.db.bak.20260804200856`（无 `group_id` 的最早结构） | 3 个计划 / 12 个计划项 → 4 个任务组（计划 3 的阀门与仪表正确拆成 2 组），0 个未挂组项 |
| 连续执行 2~3 次 | 第二次起全部跳过，数据不变 |
| 新结构有数据的库 | 空操作，数据完好 |
| 应用模型 vs 数据库 | 三张表的列集合完全一致，外键正确 |

### 安全措施

- 迁移前按项目规则备份：`cp valves.db valves.db.bak.$(date +%Y%m%d%H%M%S)`。
- 所有改动在独立功能分支 `feature/plans-ux-redesign` 上进行，是否合并由用户决定。

## 七、验收标准

1. 计划详情页中，**任一状态的计划项都能在同一页找到"完成它"的操作**，且不需要用户自己猜要去哪个模块。
2. 页面上**所有状态文字不可点击、所有可点击元素都是动作词**；不存在"已完成"按钮。
3. 全站不再出现"归档"二字。
4. 员工登录后，从侧边栏角标 → 我的检修任务 → 创建维护记录 → 返回，**全程 ≤ 3 次点击**，且保存后能看到计划进度变化。
5. 计划列表在 50 个计划、每个 100 项数据量下无 N+1 查询（用 SQLAlchemy 事件计数器验证查询数不随计划数线性增长）。
6. `tests/test_maintenance_plan.py` 全部通过，并新增覆盖：区间日期写入、归档通知完成数正确、"我的检修任务"权限隔离、编辑草稿不破坏 `maintenance_id` 关联。
7. 领导与员工的同一计划详情页，进度数字口径各自正确（领导看全量、员工看本人）。

## 八、风险与待确认项

| 风险 | 说明 | 缓解 |
|---|---|---|
| "已发布"改叫"进行中" | 改变既有术语，老用户可能不习惯 | 底层状态值未变，仅展示文案；如需回退只改 `PLAN_STATUS_LABELS` 一处 |
| 维护记录设备范围扩大 | 从"仅阀门"扩到"全部已审批仪表"（否则计划里的仪表项无法通过维护记录完成） | 已回归 `tests/` 中维护记录相关用例 |
| `_save_rows` 增量更新 | 分组匹配比全删重建复杂，边界情况（设备增删、行被移除）易出错 | 已修复两处真实缺陷：① 先 flush 后赋值触发 NOT NULL；② 孤儿计划项在组存活判定之前被删导致组被误清空。已用测试固定 |
| 详情页重排 | 改动最大的模板，可能影响领导既有查表习惯 | 完整明细表默认折叠、可一键展开，11 列信息全部保留 |

## 九、遗留事项（本次未处理）

1. **`tests/test_permissions.py` 有 25 个用例在本次改动前就无法通过**（`Valve` 未导入的 `NameError`、共享文件库导致的 `database is locked`）。已顺手修复其中的 `NameError` 与测试库隔离问题，但仍未全部通过，属既有历史问题，建议单独立项。
2. **`tests/test_auth.py`、`tests/test_index.py` 在 Python 3.12 下无法收集**（`b'中文'` 字面量语法限制），属既有问题。
3. `MaintenancePlanItem` 上保留了 `planned_date_start/end` 冗余列，与任务组区间需要保持同步。当前由 `_save_rows` 与迁移脚本负责，但缺少数据库级约束，后续若要彻底消除冗余需要改造逾期判定逻辑。

