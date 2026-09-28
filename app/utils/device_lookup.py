from typing import Optional

from app.devices import DeviceTypeRegistry


def resolve_type_code(value: str) -> Optional[str]:
    """把设备类型编码或显示名统一成类型编码，无法识别返回 ``None``。"""
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    if DeviceTypeRegistry.get(value):
        return value
    for config in DeviceTypeRegistry.all():
        if config.name == value:
            return config.code
    return None


def resolve_device(unit_name: str, tag_no: str,
                   type_hint: str = None) -> Optional[list[tuple[str, int, dict]]]:
    """按（装置名称 + 设备位号）解析设备，返回全部候选。

    :param type_hint: 期望的设备类型编码；命中候选时用于消除同（装置，位号）
        多类型造成的歧义（例如导出的检修记录带回「设备类型」列时）。
    """
    if not unit_name or not tag_no:
        return None
    tag_no = tag_no.strip()
    if tag_no in ("/", "-", "\\", ""):
        return None

    matches = []
    for config in DeviceTypeRegistry.all():
        model = config.model_class
        if not model or not hasattr(model, "位号"):
            continue
        device = model.query.filter(
            model.装置名称 == unit_name,
            model.位号 == tag_no,
            model.status != "draft",
        ).first()
        if device:
            snapshot = {
                "装置名称": getattr(device, "装置名称", "") or "",
                "设备位号": getattr(device, "位号", "") or "",
                "设备名称": getattr(device, "名称", "")
                           or getattr(device, "设备名称", "")
                           or "",
            }
            matches.append((config.code, device.id, snapshot))

    if type_hint and len(matches) > 1:
        preferred = [m for m in matches if m[0] == type_hint]
        if preferred:
            matches = preferred

    return matches if matches else None
