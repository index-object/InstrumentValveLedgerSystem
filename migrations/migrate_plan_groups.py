# coding=utf-8
"""检修计划结构重构迁移：引入任务组表，计划项按阀门/仪表分类挂组。

背景
----
原实现把"一行表单 = 一组设备 + 一套检修参数"表达为
`maintenance_plan_items.group_id`（无外键的整数），导致：

* 编辑草稿时全删重建，group_id 按新行序重编号，已关联的维护记录错位；
* 组级字段（检修项目/方案/安全措施/负责人/日期区间）散落在每个计划项上，
  无法表达"一组的计划区间是一个区间"；
* 阀门（需维护记录完成）与其他仪表（确认即完成）混在同一行里，完成路径不清。

本脚本完成：

1. 新建任务组表 `maintenance_plan_groups`，承载组级字段；
2. 原分组生成任务组记录，回填组级字段与日期区间；
3. 按设备类别（阀门 / 其他仪表）拆分混合组，每类各成一个任务组；
4. 计划项改挂任务组外键；
5. 删除已上移到任务组的冗余列，以及从未被写入过的 `completed_items` 列。

兼容两种历史结构
----------------
A. 有 group_id 且有计划项级组级字段（表单化之后的版本）：按 (plan_id, group_id) 分组；
B. 无 group_id（更早的版本，且组级字段也不存在）：计划内全部明细视为一组，
   用该类别明细的最早开始/最晚结束作为组区间，再按阀门/仪表拆分。

幂等：重复执行自动跳过已完成的步骤。
安全：仅新增表/列、删除冗余列；不删除任何计划、计划项或维护记录。
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "valves.db")

# 阀门类型：需要关联维护记录才能完成；其余为"其他仪表"，确认即完成
VALVE_TYPES = ("control_valve", "onoff_valve", "electric_valve")

# 从计划项上移到任务组的列
GROUP_COLUMNS = [
    "maintenance_project",
    "maintenance_scheme",
    "safety_measures",
    "project_leader",
    "maintenance_leader",
    "quality_acceptance",
    "remark",
]

ITEM_DROP_COLUMNS = [*GROUP_COLUMNS]
PLAN_DROP_COLUMNS = ["completed_items"]

CREATE_GROUPS_TABLE = """
CREATE TABLE IF NOT EXISTS maintenance_plan_groups (
    id INTEGER NOT NULL PRIMARY KEY,
    plan_id INTEGER NOT NULL,
    category VARCHAR(20) NOT NULL DEFAULT 'valve',
    planned_date_start DATE NOT NULL,
    planned_date_end DATE NOT NULL,
    maintenance_project TEXT,
    maintenance_scheme TEXT,
    safety_measures TEXT,
    project_leader VARCHAR(50),
    maintenance_leader VARCHAR(50),
    quality_acceptance TEXT,
    remark TEXT,
    sort_order INTEGER,
    created_at DATETIME,
    FOREIGN KEY(plan_id) REFERENCES maintenance_plans (id)
)
"""


def table_exists(cur, name):
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None


def columns(cur, table):
    cur.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cur.fetchall()]


def row_count(cur, table):
    if not table_exists(cur, table):
        return 0
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    return cur.fetchone()[0]


def _valve_filter(category):
    placeholders = ",".join("?" * len(VALVE_TYPES))
    if category == "valve":
        return f"device_type IN ({placeholders})"
    return f"device_type NOT IN ({placeholders})"


def migrate_group_table(cur, report):
    """建组表、按原分组建组、按类别拆组、计划项挂外键。

    返回 True 表示本次执行了数据回填。
    """
    if not table_exists(cur, "maintenance_plan_items"):
        report.append("跳过分组迁移：maintenance_plan_items 表不存在（空库，由 create_all 建表）")
        return False

    cols = columns(cur, "maintenance_plan_items")
    has_group_id = "group_id" in cols
    has_group_fields = "maintenance_project" in cols

    cur.execute(CREATE_GROUPS_TABLE)

    # 幂等判断：组表已有数据就认为回填已完成
    if row_count(cur, "maintenance_plan_groups") > 0:
        report.append("跳过分组数据回填：任务组已存在")
        return False

    if has_group_id:
        cur.execute(
            "SELECT DISTINCT plan_id, group_id FROM maintenance_plan_items ORDER BY plan_id, group_id"
        )
        legacy_keys = cur.fetchall()
    else:
        # 更早的结构没有分组标识：每个计划视为一组，随后按类别拆分。
        # 必须先 fetchall 再 ALTER TABLE——执行新语句会丢弃上一个查询的结果集。
        cur.execute("SELECT DISTINCT plan_id, NULL FROM maintenance_plan_items ORDER BY plan_id")
        legacy_keys = cur.fetchall()
        report.append("检测到无 group_id 的历史结构：按计划分组后按阀门/仪表拆分")
        cur.execute("ALTER TABLE maintenance_plan_items ADD COLUMN group_id INTEGER")
        has_group_id = True

    # 新组先落在临时 ID 区间，避免新建的组 ID 与"尚未处理的旧 group_id"撞号，
    # 否则 UPDATE ... WHERE group_id=? 会误伤其他组的计划项。全部建完后统一回落到正常 ID。
    cur.execute("SELECT COALESCE(MAX(id), 0) FROM maintenance_plan_groups")
    id_offset = cur.fetchone()[0] + 1000000
    staged = []  # (临时id, plan_id, category, group_values)

    sort_order = {}
    mixed_groups = 0

    for plan_id, old_gid in legacy_keys:
        if old_gid is None:
            cur.execute("SELECT DISTINCT device_type FROM maintenance_plan_items WHERE plan_id=?", (plan_id,))
        else:
            cur.execute(
                "SELECT DISTINCT device_type FROM maintenance_plan_items WHERE plan_id=? AND group_id=?",
                (plan_id, old_gid),
            )
        types = [r[0] for r in cur.fetchall()]
        has_valve = any(t in VALVE_TYPES for t in types)
        has_instrument = any(t not in VALVE_TYPES for t in types)
        categories = [c for c, hit in (("valve", has_valve), ("instrument", has_instrument)) if hit] or ["valve"]
        if len(categories) > 1:
            mixed_groups += 1

        if old_gid is None:
            scope_sql, scope_params = "plan_id=?", (plan_id,)
        else:
            scope_sql, scope_params = "plan_id=? AND group_id=?", (plan_id, old_gid)

        # 先把该组下各分类的源行全部读出，再统一写回。
        # 若边读边写，先处理的类别会把 group_id 整体改走，另一类别就查不到源行。
        sources = {}
        for category in categories:
            if has_group_fields:
                cur.execute(
                    f"""SELECT {', '.join(GROUP_COLUMNS)}, planned_date_start, planned_date_end
                        FROM maintenance_plan_items
                        WHERE {scope_sql} AND {_valve_filter(category)}
                        ORDER BY id LIMIT 1""",
                    (*scope_params, *VALVE_TYPES),
                )
            else:
                cur.execute(
                    f"""SELECT MIN(planned_date_start), MAX(planned_date_end)
                        FROM maintenance_plan_items
                        WHERE {scope_sql} AND {_valve_filter(category)}""",
                    (*scope_params, *VALVE_TYPES),
                )
            source = cur.fetchone()
            if source is not None:
                sources[category] = source

        for category in categories:
            source = sources.get(category)
            if source is None:
                continue
            if has_group_fields:
                group_values = list(source[: len(GROUP_COLUMNS)])
                date_start, date_end = source[len(GROUP_COLUMNS)], source[len(GROUP_COLUMNS) + 1]
            else:
                # 旧结构没有组级字段：用该类别明细的最早/最晚日期作为组区间
                date_start, date_end = source
                group_values = [None] * len(GROUP_COLUMNS)
            if date_start is None:
                continue

            sort_order[plan_id] = sort_order.get(plan_id, 0) + 1
            temp_id = id_offset + len(staged) + 1
            placeholders = ", ".join("?" * len(GROUP_COLUMNS))
            cur.execute(
                f"""INSERT INTO maintenance_plan_groups
                    (id, plan_id, category, planned_date_start, planned_date_end,
                     {', '.join(GROUP_COLUMNS)}, sort_order, created_at)
                    VALUES (?, ?, ?, ?, ?, {placeholders}, ?, datetime('now'))""",
                (temp_id, plan_id, category, date_start, date_end, *group_values, sort_order[plan_id]),
            )
            staged.append((temp_id, plan_id, category, group_values))

            if old_gid is None:
                cur.execute(
                    f"UPDATE maintenance_plan_items SET group_id=? "
                    f"WHERE plan_id=? AND {_valve_filter(category)}",
                    (temp_id, plan_id, *VALVE_TYPES),
                )
            else:
                cur.execute(
                    f"UPDATE maintenance_plan_items SET group_id=? "
                    f"WHERE plan_id=? AND group_id=? AND {_valve_filter(category)}",
                    (temp_id, plan_id, old_gid, *VALVE_TYPES),
                )

    # 临时 ID 回落到正常自增区间（组 ID 表内唯一，回落不会碰撞）
    for temp_id, plan_id, _cat, _vals in staged:
        cur.execute("UPDATE maintenance_plan_groups SET id=? WHERE id=?", (temp_id - id_offset, temp_id))
        cur.execute(
            "UPDATE maintenance_plan_items SET group_id=? WHERE group_id=? AND plan_id=?",
            (temp_id - id_offset, temp_id, plan_id),
        )

    # 组级日期与计划项冗余日期对齐（计划项上保留一份，供逾期判定直接使用）
    cur.execute(
        """UPDATE maintenance_plan_items
           SET planned_date_start=(SELECT g.planned_date_start FROM maintenance_plan_groups g WHERE g.id=group_id),
               planned_date_end=(SELECT g.planned_date_end FROM maintenance_plan_groups g WHERE g.id=group_id)
           WHERE group_id IS NOT NULL"""
    )

    report.append(
        f"已创建任务组 {len(staged)} 个（原分组 {len(legacy_keys)} 个，其中混合类别拆分组 {mixed_groups} 个）"
    )
    # 兜底校验：不允许存在未挂组的计划项，否则新代码会读不到所属任务组
    cur.execute("SELECT COUNT(*) FROM maintenance_plan_items WHERE group_id IS NULL")
    orphans = cur.fetchone()[0]
    if orphans:
        raise RuntimeError(f"迁移校验失败：仍有 {orphans} 个计划项未挂到任务组")
    return True


def migrate_drop_columns(cur, report):
    """删除已上移/已废弃的冗余列。"""
    if table_exists(cur, "maintenance_plan_items"):
        cols = columns(cur, "maintenance_plan_items")
        for col in ITEM_DROP_COLUMNS:
            if col in cols:
                cur.execute(f"ALTER TABLE maintenance_plan_items DROP COLUMN {col}")
                report.append(f"已删除 maintenance_plan_items.{col}")

    if table_exists(cur, "maintenance_plans"):
        cols = columns(cur, "maintenance_plans")
        for col in PLAN_DROP_COLUMNS:
            if col in cols:
                cur.execute(f"ALTER TABLE maintenance_plans DROP COLUMN {col}")
                report.append(f"已删除 maintenance_plans.{col}")


def _plan_schema_is_current(cur):
    """判断计划相关表是否已是重构后的新结构（此时迁移应为空操作）"""
    if not table_exists(cur, "maintenance_plan_groups"):
        return False
    group_cols = columns(cur, "maintenance_plan_groups")
    item_cols = columns(cur, "maintenance_plan_items") if table_exists(cur, "maintenance_plan_items") else []
    plan_cols = columns(cur, "maintenance_plans") if table_exists(cur, "maintenance_plans") else []
    return (
        "category" in group_cols
        and "group_id" in item_cols
        and "maintenance_project" not in item_cols
        and "completed_items" not in plan_cols
    )


def main(db_path=None):
    db_path = db_path or DB_PATH
    if not os.path.exists(db_path):
        print(f"数据库不存在，无需迁移：{db_path}")
        return 0

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=OFF")
    cur = conn.cursor()
    report = []
    try:
        if not table_exists(cur, "maintenance_plans"):
            # 计划表尚未创建，交由应用启动时的 create_all 建表
            print("计划相关表尚未创建，无需迁移（启动应用会自动建表）")
            return 0

        if _plan_schema_is_current(cur):
            print("计划相关表已是新结构，无需迁移")
            return 0

        if row_count(cur, "maintenance_plans") == 0 and row_count(cur, "maintenance_plan_items") == 0:
            # 旧结构的空表：直接重建，避免残留列影响 create_all
            report.append("检测到旧结构空表，重建计划相关表（由应用启动时 create_all 建表）")
            cur.execute("DROP TABLE IF EXISTS maintenance_plan_items")
            cur.execute("DROP TABLE IF EXISTS maintenance_plan_groups")
            cur.execute("DROP TABLE IF EXISTS maintenance_plans")
            conn.commit()
            print("旧结构空表已清理，请启动应用由 create_all 重建表结构")
            for line in report:
                print(" -", line)
            return 0

        # 先回填、后删列：回填需要读取计划项上的组级字段。
        # 两步各自做幂等判断，任意一步中断后重跑都能补齐剩余步骤。
        migrate_group_table(cur, report)
        migrate_drop_columns(cur, report)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"迁移完成：{db_path}")
    for line in report:
        print(" -", line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
