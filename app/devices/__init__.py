class DeviceTypeConfig:
    """一种仪表类型的完整配置"""
    def __init__(self, code, name, model_class, icon="fa-cog",
                 field_groups=None, filterable_fields=None,
                 import_column_map=None, color_scheme=None):
        self.code = code
        self.name = name
        self.model_class = model_class
        self.icon = icon
        self.field_groups = field_groups or []
        self.filterable_fields = filterable_fields or []
        self.import_column_map = import_column_map or {}
        self.color_scheme = color_scheme or ['#f1f5f9','#e2e8f0','#475569','#cbd5e1']

    def get_fields_flat(self):
        """获取所有字段列表（拍平分组）"""
        fields = []
        for group in self.field_groups:
            fields.extend(group["fields"])
        return fields


class DeviceTypeRegistry:
    _types = {}

    @classmethod
    def register(cls, config):
        cls._types[config.code] = config

    @classmethod
    def get(cls, code):
        return cls._types.get(code)

    @classmethod
    def all(cls):
        return list(cls._types.values())

    @classmethod
    def exclude_valve(cls):
        """获取除 valve 外的所有类型（用于导航菜单）"""
        return [t for t in cls._types.values() if t.code != "valve"]
