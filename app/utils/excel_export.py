# coding=utf-8
"""Excel 导出响应的公共封装。

统一处理 xlsx 编码、中文文件名与下载响应头，让各导出入口只关心
"导出哪些数据"，不再各自拼装。文件名使用 RFC 6266 的
``filename*=UTF-8''`` 形式，保留中文台账名，同时给旧浏览器留 ASCII 回退。
"""

from urllib.parse import quote

from flask import make_response
from flask_login import current_user

from app.models import User

STATUS_LABELS = {
    "draft": "草稿",
    "pending": "待审批",
    "approved": "已审批",
    "rejected": "已驳回",
}


def build_excel_response(df, filename_base):
    """把 DataFrame 包成浏览器可下载的 xlsx 响应。"""
    from io import BytesIO

    buffer = BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)

    output = make_response(buffer.read())
    safe_name = "".join(
        ch for ch in filename_base if ch not in '\\/:*?"<>|\r\n'
    ).strip() or "export"
    output.headers["Content-Disposition"] = (
        f"attachment; filename=export.xlsx; filename*=UTF-8''{quote(safe_name)}.xlsx"
    )
    output.headers["Content-Type"] = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    return output


def user_labels(user_ids):
    """批量取用户显示名，避免逐行查询。"""
    ids = {uid for uid in user_ids if uid}
    if not ids:
        return {}
    users = User.query.filter(User.id.in_(ids)).all()
    return {u.id: (u.real_name or u.username) for u in users}


def exporter_label():
    """当前导出人的显示名（用于文件名与"导出人"列）。"""
    return current_user.real_name or current_user.username
