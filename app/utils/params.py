from functools import wraps
from flask import request, abort


def expects_params(*required, optional=None):
    """声明路由期望的查询参数，缺失时返回 400

    Args:
        *required: 必需的查询参数名
        optional: 可选的查询参数名列表

    Usage:
        @expects_params('from', optional=['search', 'status'])
        def my_view():
            ...
    """
    if optional is None:
        optional = []

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            for param in required:
                if param not in request.args:
                    abort(400, f"缺少必需参数: {param}")
            return f(*args, **kwargs)
        return wrapper
    return decorator
