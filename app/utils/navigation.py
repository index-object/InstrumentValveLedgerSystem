"""
导航上下文管理模块

统一管理页面间的跳转链，确保"从哪里进入就返回到哪里"。
"""

from flask import request, url_for, redirect
from functools import wraps
from app.devices import DeviceTypeRegistry


# 需要自动传播的查询参数白名单
PROPAGATE_PARAMS = {'from', 'search', 'status', 'page', 'per_page', 'tab'}


# 定义所有合法的入口点及其返回目标
NAVIGATION_CONTEXTS = {
    'all': {
        'name': '全部台账',
        'list_endpoint': 'ledgers.list',
        'list_label': '台账列表',
    },
    'mine': {
        'name': '我的台账',
        'list_endpoint': 'valves.my_ledgers',
        'list_label': '我的台账',
    },
    'approvals': {
        'name': '审批中心',
        'list_endpoint': 'approvals.index',
        'list_label': '审批中心',
    },
    'maintenance': {
        'name': '维修记录',
        'list_endpoint': 'valves.maintenance_list',
        'list_label': '维修记录',
    },
    'statistics': {
        'name': '数据统计',
        'list_endpoint': 'statistics.index',
        'list_label': '数据统计',
    },
}


def url_with_params(endpoint, **kwargs):
    """生成 URL 并自动携带当前请求中的参数

    自动从当前请求中获取所有查询参数（白名单 + 列筛选等），
    如果 kwargs 中已显式提供则使用 kwargs 的值覆盖。

    Args:
        endpoint: Flask 路由端点
        **kwargs: 其他 URL 参数

    Returns:
        str: 带参数的 URL
    """
    for key in request.args:
        if key not in kwargs:
            values = request.args.getlist(key)
            if len(values) == 1:
                kwargs[key] = values[0]
            elif len(values) > 1:
                kwargs[key] = values
    return url_for(endpoint, **kwargs)


def get_from_param(request_obj=None):
    """
    获取当前的 from 参数值

    Args:
        request_obj: Flask request 对象，默认使用全局 request

    Returns:
        str: from 参数值，默认为 'all'
    """
    if request_obj is None:
        request_obj = request
    return request_obj.args.get('from', 'all')


def get_context(from_param=None):
    """
    获取导航上下文信息

    Args:
        from_param: from 参数值，默认从当前请求获取

    Returns:
        dict: 上下文信息字典
    """
    if from_param is None:
        from_param = get_from_param()
    return NAVIGATION_CONTEXTS.get(from_param, NAVIGATION_CONTEXTS['all'])


def get_back_url(from_param=None):
    """
    获取返回按钮的目标 URL（返回到来源列表页，带当前列表参数）

    Args:
        from_param: from 参数值

    Returns:
        str: 目标 URL
    """
    if from_param is None:
        from_param = get_from_param()

    ctx = get_context(from_param)

    kwargs = {}
    for key in request.args:
        if key == 'from':
            continue
        values = request.args.getlist(key)
        if len(values) == 1:
            kwargs[key] = values[0]
        elif len(values) > 1:
            kwargs[key] = values

    return url_for(ctx['list_endpoint'], **kwargs)


def url_with_from(endpoint, from_param=None, **kwargs):
    """
    生成带 from 参数的 URL

    Args:
        endpoint: Flask 路由端点
        from_param: from 参数值，默认从当前请求获取
        **kwargs: 其他 URL 参数

    Returns:
        str: 带 from 参数的 URL
    """
    if from_param is None:
        from_param = get_from_param()

    # 确保 from 参数被正确传递
    kwargs['from'] = from_param
    return url_for(endpoint, **kwargs)


def redirect_to_list(from_param=None):
    """
    重定向到来源列表页

    Args:
        from_param: from 参数值

    Returns:
        Flask redirect 响应
    """
    if from_param is None:
        from_param = get_from_param()

    ctx = get_context(from_param)
    return redirect(url_for(ctx['list_endpoint']))


def redirect_to_detail(endpoint, id, from_param=None, **kwargs):
    """
    重定向到详情页并保持上下文

    Args:
        endpoint: 详情页路由端点
        id: 记录 ID
        from_param: from 参数值
        **kwargs: 其他 URL 参数

    Returns:
        Flask redirect 响应
    """
    if from_param is None:
        from_param = get_from_param()

    kwargs['id'] = id
    kwargs['from'] = from_param
    return redirect(url_for(endpoint, **kwargs))


def redirect_to_ledger_detail(ledger_id, from_param=None):
    """
    重定向到台账合集详情页并保持上下文

    Args:
        ledger_id: 台账合集 ID
        from_param: from 参数值

    Returns:
        Flask redirect 响应
    """
    if from_param is None:
        from_param = get_from_param()

    return redirect(url_for('ledgers.detail', id=ledger_id, **{'from': from_param}))


def redirect_to_valve_detail(valve, from_param=None):
    """
    重定向到台账详情页并保持上下文

    Args:
        valve: Valve 对象
        from_param: from 参数值

    Returns:
        Flask redirect 响应
    """
    if from_param is None:
        from_param = get_from_param()

    # 根据阀门是否有 ledger 决定使用哪个路由
    if valve.ledger_id:
        return redirect(url_for(
            'ledgers.valve_detail',
            ledger_id=valve.ledger_id,
            id=valve.id,
            **{'from': from_param}
        ))
    else:
        return redirect(url_for('valves.detail', id=valve.id, **{'from': from_param}))


# 模板上下文处理器
def inject_navigation():
    """
    为所有模板注入导航相关的全局变量和函数
    """
    return {
        'NAVIGATION_CONTEXTS': NAVIGATION_CONTEXTS,
        'PROPAGATE_PARAMS': PROPAGATE_PARAMS,
        'get_from_param': get_from_param,
        'get_context': get_context,
        'get_back_url': get_back_url,
        'url_with_from': url_with_from,
        'url_with_params': url_with_params,
        'get_device_types': DeviceTypeRegistry.exclude_valve,
        'get_device_type_config': DeviceTypeRegistry.get,
    }