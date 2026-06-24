def check_duplicate(model_class, unit_name, tag_no, exclude_id=None):
    """检查同类型表中是否存在相同的装置名称+位号组合（含草稿）"""
    if not unit_name or not tag_no:
        return False
    q = model_class.query.filter(
        model_class.装置名称 == unit_name,
        model_class.位号 == tag_no,
    )
    if exclude_id:
        q = q.filter(model_class.id != exclude_id)
    return q.first() is not None
