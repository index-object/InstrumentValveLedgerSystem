import os
from dataclasses import dataclass, field
from typing import Any, Optional

import yaml

from app.import_engine.classifier import SheetClassifier, TypeConfig
from app.import_engine.extractor import DataExtractor, SheetData
from app.import_engine.mapper import ColumnMapper
from app.import_engine.loader import DataLoader
from app.models import Valve


@dataclass
class SheetImportResult:
    sheet_name: str
    type_key: Optional[str] = None
    type_code: Optional[str] = None
    type_name: Optional[str] = None
    row_count: int = 0
    accessory_count: int = 0
    records: list = field(default_factory=list)
    accessories: list[dict] = field(default_factory=list)
    headers: list[str] = field(default_factory=list)
    sample_rows: list[dict] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class ImportResult:
    sheets: list[SheetImportResult] = field(default_factory=list)
    total_records: int = 0
    errors: list[str] = field(default_factory=list)
    summary_data: Optional[SheetData] = None


class ImportEngine:
    CONFIG_DIR = os.path.join(os.path.dirname(__file__), "config")

    def __init__(self):
        self._classifier = SheetClassifier()
        self._extractor = DataExtractor()
        self._mapper: Optional[ColumnMapper] = None
        self._loader = DataLoader()
        self._types_config: dict = {}
        self._model_cache: dict[str, type] = {}
        self._load_configs()

    def _load_configs(self) -> None:
        types_path = os.path.join(self.CONFIG_DIR, "types.yaml")
        synonyms_path = os.path.join(self.CONFIG_DIR, "synonyms.yaml")

        with open(types_path, encoding="utf-8") as f:
            types_data = yaml.safe_load(f)

        with open(synonyms_path, encoding="utf-8") as f:
            synonyms_data = yaml.safe_load(f)

        self._types_config = types_data.get("types", {})
        synonyms = synonyms_data.get("synonyms", {})

        self._mapper = ColumnMapper(synonyms)

        for type_key, cfg in self._types_config.items():
            self._classifier.register_from_dict(type_key, cfg)

    def _get_model_class(self, model_class_name: Optional[type | str]) -> Optional[type]:
        if not model_class_name:
            return None
        if isinstance(model_class_name, type):
            return model_class_name
        if model_class_name in self._model_cache:
            return self._model_cache[model_class_name]

        try:
            from app.devices.types import (
                PressureTransmitter,
                LocalPressureGauge,
                Temperature,
                LocalTemperature,
                FlowMeter,
                LevelTransmitter,
                LocalLevel,
                ShaftInstrument,
            )
            from app.models import Valve

            model_map: dict[str, type] = {
                "PressureTransmitter": PressureTransmitter,
                "LocalPressureGauge": LocalPressureGauge,
                "Temperature": Temperature,
                "LocalTemperature": LocalTemperature,
                "FlowMeter": FlowMeter,
                "LevelTransmitter": LevelTransmitter,
                "LocalLevel": LocalLevel,
                "ShaftInstrument": ShaftInstrument,
                "Valve": Valve,
            }
            cls = model_map.get(model_class_name)
            if cls:
                self._model_cache[model_class_name] = cls
            return cls
        except ImportError:
            return None

    def import_file(self, filepath: str) -> ImportResult:
        result = ImportResult()

        try:
            sheets_data = self._extractor.read_excel(filepath)
        except Exception as e:
            result.errors.append(f"文件读取失败: {e}")
            return result

        for sd in sheets_data:
            sheet_result = self._process_sheet(sd)
            result.sheets.append(sheet_result)
            if sheet_result.error:
                result.errors.append(
                    f"[{sheet_result.sheet_name}] {sheet_result.error}"
                )
            else:
                result.total_records += sheet_result.row_count

        return result

    def _process_sheet(self, sd: SheetData) -> SheetImportResult:
        sheet_result = SheetImportResult(sheet_name=sd.sheet_name)

        if not sd.headers:
            return sheet_result

        classification = self._classifier.classify(
            sd.sheet_name, headers=sd.headers
        )

        if classification is None:
            return sheet_result

        type_key = classification.type_key
        type_cfg = self._types_config.get(type_key, {})

        if classification.type_code in ("summary", "cover"):
            if classification.type_code == "summary":
                sheet_result.type_key = type_key
                sheet_result.type_code = "summary"
                sheet_result.type_name = type_cfg.get("name", "汇总表")
                sheet_result.headers = sd.headers
            return sheet_result

        model_class_name = type_cfg.get("model_class")
        model_cls = self._get_model_class(model_class_name) if model_class_name else None

        if not model_cls:
            sheet_result.error = f"未找到模型类: {model_class_name}"
            return sheet_result

        column_mapping = type_cfg.get("column_mapping", {})
        mapped_rows = self._mapper.map_rows(sd.rows, column_mapping)

        preserve = model_cls is Valve
        records = self._loader.create_records(model_cls, mapped_rows, preserve_order=preserve)

        sheet_result.type_key = type_key
        sheet_result.type_code = classification.type_code
        sheet_result.type_name = type_cfg.get("name", "")
        sheet_result.row_count = len(records)
        sheet_result.accessory_count = len(sd.accessories)
        sheet_result.records = records
        sheet_result.accessories = sd.accessories
        sheet_result.headers = sd.headers
        sheet_result.sample_rows = sd.rows[:5] if sd.rows else []

        return sheet_result
