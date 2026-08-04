# coding=utf-8
"""检修计划填表化迁移：为 maintenance_plan_items 新增文本字段与分组标识。

新增列：
  maintenance_project  检修项目
  maintenance_scheme   检修方案
  safety_measures      主要安全管控措施
  project_leader       项目负责人
  maintenance_leader   检修负责人
  quality_acceptance   质量验收
  remark               备注
  group_id             表单行分组标识（同行的多个位号共享）

仅追加可空列，无数据丢失。幂等：重复执行自动跳过已存在的列。
"""
import sqlite3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "valves.db")

NEW_COLUMNS = {
    "maintenance_project": "TEXT",
    "maintenance_scheme": "TEXT",
    "safety_measures": "TEXT",
    "project_leader": "TEXT",
    "maintenance_leader": "TEXT",
    "quality_acceptance": "TEXT",
    "remark": "TEXT",
    "group_id": "INTEGER",
}


def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for col, typ in NEW_COLUMNS.items():
        try:
            c.execute(f"ALTER TABLE maintenance_plan_items ADD COLUMN {col} {typ}")
            print(f"已添加列: {col}")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print(f"列已存在，跳过: {col}")
            else:
                raise
    conn.commit()
    conn.close()
    print("迁移完成")


if __name__ == "__main__":
    main()
