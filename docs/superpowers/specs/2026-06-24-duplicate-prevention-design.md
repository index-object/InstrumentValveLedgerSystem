# 数据去重设计方案

## 背景

当前系统的导入功能为追加模式，同类型表中可以反复导入相同的"装置+位号"数据，无法阻止重复记录的产生。手动新增时虽有位号检测，但未考虑装置名称的组合唯一性。

## 目标

- 同类型表中，全局范围内"装置名称(unit_name) + 位号(tag_no)"不允许重复
- 不同设备类型使用独立表，互不影响
- 用户可在导入时选择重复处理方式
- 手动新增时输入即检测

## 方案选择

采用**纯应用层校验**（方案A），不在数据库层加唯一约束。原因：当前项目为单机 SQLite 应用，无外部系统绕开应用层写库的场景，应用层校验足够可靠且零迁移成本。

## 核心设计

### 模块一：通用重复检测工具函数

**文件**: `app/utils/duplicate_check.py`（新建）

```python
def check_duplicate(model_class, unit_name, tag_no, exclude_id=None) -> bool
```

- 查询同类型表中是否存在 `装置名称 == unit_name AND 位号 == tag_no` 的非草稿记录
- `exclude_id` 用于编辑时排除自身
- 不检查草稿状态的记录（与现有行为一致）

### 模块二：导入流程去重

在现有导入流程中增加去重预检和执行逻辑。

#### 预检阶段 (`/imports/preview`)

在 `_build_preview()` 之后，对每个已识别类型的 sheet:

1. 根据 `type_code` 获取对应 `model_class`
2. 查询该表中所有已存在的 `(装置名称, 位号)` 组合（非草稿记录）
3. 遍历本批次 records，标记出重复行
4. 将重复信息传递到模板

#### 预览页面 (`import_preview.html`)

每个 sheet 卡片新增：

- **重复行详情**：可折叠/展开的表格，列出具体重复的数据行（显示装置名称、位号等关键字段）
- **操作选择**：三个单选按钮
  - **跳过重复**（默认）：只导入不重复的行
  - **覆盖更新**：用新数据覆盖已有的记录
  - **中止导入**：有任何重复就整批不导入

#### 执行阶段 (`/imports/execute`)

根据用户选择的模式执行：

| 模式 | 行为 |
|------|------|
| 跳过 | 逐行判断，已存在则 continue，统计已创建/已跳过数量 |
| 覆盖 | 已存在则 UPDATE，不存在则 INSERT，统计已创建/已更新数量 |
| 中止 | 预检时就返回错误，不写入任何数据 |

### 模块三：手动新增/编辑实时检测

#### 后端

修改 `/device/<type_code>/check-tag` 接口（`app/routes/devices.py`）:

- 新增 `装置名称` 查询参数
- 改为调用 `check_duplicate(model_class, 装置名称, 位号, exclude_id)`
- 返回 `{"valid": bool, "message": str}`

#### 前端

修改 `devices/form.html` 的 JS：

- 在 `装置名称` 和 `位号` 输入框都绑定 `blur`/`input` 事件
- 两个字段都有值时触发 `/check-tag` 异步请求
- 有重复时，在对应输入框下方显示红色提示文字
- 编辑页面也生效（自动传入 exclude_id）

## 影响范围

| 文件 | 改动类型 |
|------|---------|
| `app/utils/duplicate_check.py` | 新建 |
| `app/routes/imports.py` | 修改 - 预检 + 执行 |
| `templates/imports/import_preview.html` | 修改 - 展示重复详情 + 选项 |
| `app/routes/devices.py` | 修改 - check-tag 接口 |
| `templates/devices/form.html` | 修改 - JS 实时检测 |

## 不变的部分

- 数据库表结构不变
- 导入引擎的 `DataLoader`、`Classifier`、`Mapper`、`Extractor` 不变
- 设备模型类不变
- 审批流程不变
- Ledger 台账管理逻辑不变
