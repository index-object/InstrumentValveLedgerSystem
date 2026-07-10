from typing import Optional

from app.devices import DeviceTypeRegistry


def resolve_device(unit_name: str, tag_no: str) -> Optional[list[tuple[str, int, dict]]]:
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

    return matches if matches else None
