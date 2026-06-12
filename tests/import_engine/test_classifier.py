import os
import yaml
import pytest

from app.import_engine.classifier import SheetClassifier, TypeConfig


def _make_type_config(key, code, name, keywords, signatures, weight=10):
    return TypeConfig(
        key=key,
        code=code,
        name=name,
        sheet_keywords=keywords,
        column_signatures=signatures,
        weight=weight,
    )


class TestSheetClassifier:
    def test_exact_match_highest_priority(self):
        classifier = SheetClassifier()
        classifier.register(
            _make_type_config("flow", "flow_meter", "流量计", ["流量计"], ["量程KPa"])
        )
        classifier.register(
            _make_type_config("valve", "valve", "调节阀", ["调节阀"], ["Cv值"])
        )
        result = classifier.classify("调节阀")
        assert result is not None
        assert result.type_code == "valve"
        assert result.score == 10

    def test_keyword_match_second_priority(self):
        classifier = SheetClassifier()
        classifier.register(
            _make_type_config("flow", "flow_meter", "流量计", ["流量计", "远传流量"], [])
        )
        classifier.register(
            _make_type_config("pressure", "pressure", "压力", ["压力表", "远传压力"], [])
        )
        result = classifier.classify("就地压力表")
        assert result is not None
        assert result.type_code == "pressure"
        assert result.score == 7

    def test_column_signature_match_third_priority(self):
        classifier = SheetClassifier()
        classifier.register(
            _make_type_config(
                "valve", "control_valve", "调节阀",
                ["调节阀"], ["Cv值", "执行机构", "弹簧范围"]
            )
        )
        result = classifier.classify("未知Sheet名", headers=["设备名称", "Cv值", "位号"])
        assert result is not None
        assert result.type_code == "control_valve"
        assert result.score == 5

    def test_no_match_returns_none(self):
        classifier = SheetClassifier()
        classifier.register(
            _make_type_config("valve", "valve", "阀门", ["调节阀"], ["Cv值"])
        )
        result = classifier.classify("完全不相关")
        assert result is None

    def test_lower_score_loses(self):
        classifier = SheetClassifier()
        classifier.register(
            _make_type_config("v1", "valve", "阀门", ["调节阀"], [], weight=7)
        )
        classifier.register(
            _make_type_config("v2", "valve2", "阀门2", [], ["Cv值"], weight=5)
        )
        result = classifier.classify("调节阀", headers=["Cv值", "位号"])
        assert result is not None
        assert result.type_code == "valve"
        assert result.score == 10

    def test_summary_sheet_exact_match(self):
        classifier = SheetClassifier()
        classifier.register(
            _make_type_config("summary", "summary", "汇总",
                              ["汇总", "仪表等级划分汇总表", "汇总表"], [])
        )
        result = classifier.classify("仪表等级划分汇总表")
        assert result is not None
        assert result.type_code == "summary"

    def test_cover_sheet_exact_match(self):
        classifier = SheetClassifier()
        classifier.register(
            _make_type_config("cover", "cover", "首页", ["首页", "封面", "目录"], [])
        )
        result = classifier.classify("首页")
        assert result is not None
        assert result.type_code == "cover"

    def test_multiple_headers_with_mixed_matches(self):
        classifier = SheetClassifier()
        classifier.register(
            _make_type_config(
                "pressure", "pressure", "压力",
                ["压力"], ["MPa", "全不锈钢压力表"]
            )
        )
        result = classifier.classify("未知", headers=["位号", "MPa", "测量范围"])
        assert result is not None
        assert result.type_code == "pressure"

    def test_full_classification_with_real_config(self):
        config_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "app", "import_engine", "config", "types.yaml",
        )
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        classifier = SheetClassifier()
        for type_key, type_cfg in config["types"].items():
            classifier.register_from_dict(type_key, type_cfg)

        test_cases = [
            ("调节阀", "valve"),
            ("切断阀", "valve"),
            ("开关阀", "valve"),
            ("压力变送器", "pressure_transmitter"),
            ("就地压力表", "local_pressure_gauge"),
            ("温度", "temperature"),
            ("就地温度", "local_temperature"),
            ("流量计", "flow_meter"),
            ("液位计", "level_transmitter"),
            ("就地液位计", "local_level"),
            ("汇总", "summary"),
            ("仪表等级划分汇总表", "summary"),
        ]

        for sheet_name, expected_code in test_cases:
            result = classifier.classify(sheet_name)
            assert result is not None, (
                f"Sheet '{sheet_name}' 未能分类，期望 {expected_code}"
            )
            assert result.type_code == expected_code, (
                f"Sheet '{sheet_name}' 分类为 {result.type_code}，期望 {expected_code}"
            )

    def test_same_code_multiple_configs(self):
        classifier = SheetClassifier()
        classifier.register(
            _make_type_config("control_valve", "valve", "调节阀", ["调节阀"], [])
        )
        classifier.register(
            _make_type_config("onoff_valve", "valve", "开关阀", ["开关阀", "切断阀"], [])
        )
        r1 = classifier.classify("调节阀")
        assert r1 is not None and r1.type_code == "valve"
        r2 = classifier.classify("切断阀")
        assert r2 is not None and r2.type_code == "valve"
