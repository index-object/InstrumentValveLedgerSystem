# coding=utf-8
"""导出范围统一口径。

导出功能此前各自为政，绕过了列表页的权限与筛选口径：

* 员工在维护记录、仪表列表里只能看到自己创建的数据，导出却是全量；
* 勾选导出（``ids``）会直接跳过状态与归属过滤，等于给任何登录用户
  开了一个导出他人草稿 / 待审批数据的后门；
* 导出不套用列表页的搜索、状态、列筛选，导出的文件与页面看到的
  数据对不上。

本模块把口径收敛到一处，保证：

1. 导出的数据 = 用户在当前页面能看到的数据；
2. 员工不能导出他人的草稿 / 待审批 / 已驳回数据；
3. 显式传入 ``ids`` 也受同样约束，不能当作越权出口。
"""

from flask_login import current_user
from sqlalchemy import inspect, or_

# 列表页查询串里参与筛选的字段名与这些控制参数重名时必须排除。
# 注意 status 不在此列：它是模型字段，需要按列筛选正常生效。
_CONTROL_PARAMS = {
    "from",
    "ledger_id",
    "device_type",
    "type_code",
    "ids",
    "search",
    "page",
    "per_page",
    "tab",
}

# 全文搜索时排除的技术字段（与台账列表页保持一致）
_SEARCH_EXCLUDED = {
    "id",
    "ledger_id",
    "created_by",
    "approved_by",
    "approved_at",
    "created_at",
    "updated_at",
    "status",
}


def can_view_all_statuses(ledger, from_param):
    """判断当前用户在当前入口下是否可以查看台账内的全部状态数据。

    只有两种情况列表页会展示全部状态：

    * 「审批中心」(``from=approvals``)：仅领导和管理员可进入；
    * 「我的台账」(``from=mine``)：仅台账所有者本人、领导和管理员。

    其他入口（全部台账 / 数据统计）一律只看已审批数据。
    """
    if from_param not in ("mine", "approvals"):
        return False
    if current_user.role in ("leader", "admin"):
        return True
    return (
        from_param == "mine"
        and ledger is not None
        and ledger.created_by == current_user.id
    )


def apply_ledger_scope(query, model, ledger, from_param, args=None):
    """套用台账列表页的可见范围（逐表查询）。

    :param query: 已经过模型筛选的查询对象
    :param model: 当前查询的模型类
    :param ledger: 台账合集对象，可为 ``None``（历史的无台账入口）
    :param from_param: 导航来源参数
    :param args: 当前请求的查询参数，用于判断是否显式筛选了状态
    """
    if ledger is not None:
        query = query.filter(model.ledger_id == ledger.id)

    if can_view_all_statuses(ledger, from_param):
        # 列表页在"我的台账/审批中心"下不看已审批限制，这里也不额外过滤，
        # 逐条导出时再由 can_export_device 按创建者收口。
        return query

    # 列表页一旦显式筛选状态，就不再套用"仅已审批 + 审批快照"的口径
    if args is not None and args.get("status"):
        return query

    if ledger is not None and ledger.approved_snapshot_at:
        return query.filter(
            model.status == "approved",
            model.approved_at <= ledger.approved_snapshot_at,
        )
    return query.filter(model.status == "approved")


def apply_device_list_scope(query, model):
    """套用 ``/device/<type_code>`` 列表页的可见范围。

    仪表列表页对所有非阀门类型生效：员工只能看到自己创建的数据，
    领导和管理员可以看到全部数据。
    """
    if current_user.role == "employee":
        return query.filter(model.created_by == current_user.id)
    return query


def apply_search(query, model, args, broad=True):
    """套用列表页的关键词搜索。

    :param broad: ``True`` 时搜索所有业务字段（台账详情页口径）；
        ``False`` 时只搜索位号 / 设备名称 / 装置名称 / 名称（仪表列表页口径）
    """
    search = (args.get("search") or "").strip()
    if not search:
        return query

    if not broad:
        keyword = f"%{search}%"
        conditions = [
            getattr(model, field).like(keyword)
            for field in ("位号", "设备名称", "装置名称", "名称")
            if hasattr(model, field)
        ]
        return query.filter(or_(*conditions)) if conditions else query

    mapper = inspect(model)
    conditions = [
        getattr(model, key).contains(search)
        for key in mapper.columns.keys()
        if key not in _SEARCH_EXCLUDED
    ]
    return query.filter(or_(*conditions)) if conditions else query


def apply_field_filters(query, model, args):
    """套用列表页侧边/表头的列筛选（同名多值参数）。"""
    columns = set(inspect(model).columns.keys())
    for key in args.keys():
        if key in _CONTROL_PARAMS or key not in columns:
            continue
        values = [v for v in args.getlist(key) if v != ""]
        if values:
            query = query.filter(getattr(model, key).in_(values))
    return query
