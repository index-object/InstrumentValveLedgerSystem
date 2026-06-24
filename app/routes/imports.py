from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, session, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import db, Ledger, ValveAttachment, SheetMapping
from app.devices import DeviceTypeRegistry
from app.import_engine import ImportEngine
from datetime import datetime
import os
import uuid

imports = Blueprint("imports", __name__)

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = ImportEngine()
    return _engine


def _infer_attachment_type(name: str) -> str:
    keywords = {
        "定位器": ["定位器"],
        "电磁阀": ["电磁阀"],
        "过滤器": ["过滤器"],
        "减压阀": ["减压阀"],
        "保位阀": ["保位阀"],
        "放大器": ["放大器"],
        "转换器": ["转换器"],
        "限位开关": ["限位开关"],
        "位置变送器": ["位置变送器"],
    }
    for att_type, kw_list in keywords.items():
        for kw in kw_list:
            if kw in name:
                return att_type
    return name


@imports.route("/imports")
@login_required
def index():
    return render_template("imports/import.html")


def _build_preview(result):
    """从 ImportResult 构建预览数据和未匹配列表，增加重复检测"""
    preview = []
    unmatched = []
    for sr in result.sheets:
        if sr.type_code and sr.type_code not in ("summary", "cover"):
            config = DeviceTypeRegistry.get(sr.type_code)
            model_cls = config.model_class if config else None
            duplicates = []
            if model_cls and hasattr(model_cls, "装置名称") and hasattr(model_cls, "位号"):
                from app.utils.duplicate_check import check_duplicate
                for record in sr.records:
                    unit = getattr(record, "装置名称", None) or ""
                    tag = getattr(record, "位号", None) or ""
                    if tag and check_duplicate(model_cls, unit, tag):
                        duplicates.append({"装置名称": unit, "位号": tag})
            preview.append({
                "sheet": sr.sheet_name,
                "rows": sr.row_count,
                "headers": sr.headers,
                "sample": sr.sample_rows,
                "type_key": sr.type_key,
                "detected_type": sr.type_code,
                "detected_name": sr.type_name,
                "accessory_count": sr.accessory_count,
                "duplicates": duplicates,
                "duplicate_count": len(duplicates),
                "new_count": sr.row_count - len(duplicates),
            })
        elif not sr.type_code:
            unmatched.append(sr.sheet_name)
    return preview, unmatched


def _get_saved_path():
    """获取 session 中保存的文件路径，不存在时返回 None"""
    saved_name = session.get("import_file")
    if not saved_name:
        return None
    upload_folder = current_app.config.get("UPLOAD_FOLDER")
    path = os.path.join(upload_folder, saved_name)
    return path if os.path.exists(path) else None


@imports.route("/imports/upload", methods=["POST"])
@login_required
def upload():
    if "file" not in request.files:
        flash("请选择文件")
        return redirect(url_for("imports.index"))

    file = request.files["file"]
    if file.filename == "":
        flash("请选择文件")
        return redirect(url_for("imports.index"))

    filename = file.filename
    ext = os.path.splitext(filename)[1].lower()
    if ext not in (".xlsx", ".xls"):
        flash("仅支持 .xlsx / .xls 文件")
        return redirect(url_for("imports.index"))

    uid = uuid.uuid4().hex
    saved_name = f"import_{uid}{ext}"
    upload_folder = current_app.config.get("UPLOAD_FOLDER")
    saved_path = os.path.join(upload_folder, saved_name)
    file.save(saved_path)

    engine = get_engine()
    try:
        result = engine.import_file(saved_path)
    except Exception as e:
        flash(f"文件读取失败: {e}")
        try:
            os.remove(saved_path)
        except Exception:
            pass
        return redirect(url_for("imports.index"))

    preview, unmatched = _build_preview(result)

    session["import_file"] = saved_name
    session["import_filename"] = filename
    session["import_errors"] = result.errors
    session.pop("import_mappings", None)

    # 查记忆表，自动填充已学习的映射
    if unmatched:
        existing = SheetMapping.query.filter(
            SheetMapping.sheet_name.in_(unmatched)
        ).all()
        auto_mappings = {m.sheet_name: m.type_code for m in existing}
        new_unmatched = []
        for name in unmatched:
            if name in auto_mappings:
                if "import_mappings" not in session:
                    session["import_mappings"] = {}
                session["import_mappings"][name] = auto_mappings[name]
            else:
                new_unmatched.append(name)
        unmatched = new_unmatched

    if unmatched:
        all_types = [{"code": t.code, "name": t.name} for t in DeviceTypeRegistry.all()]
        unmatched_preview = []
        for sr in result.sheets:
            if sr.sheet_name in unmatched:
                unmatched_preview.append({
                    "sheet": sr.sheet_name,
                    "headers": sr.headers,
                    "sample": sr.sample_rows,
                })
        return render_template(
            "imports/import.html",
            matched_preview=preview,
            unmatched_preview=unmatched_preview,
            all_types=all_types,
            filename=filename,
            errors=result.errors,
        )

    return redirect(url_for("imports.preview"))


@imports.route("/imports/preview")
@login_required
def preview():
    saved_path = _get_saved_path()
    if not saved_path:
        flash("没有预览数据，请重新上传")
        return redirect(url_for("imports.index"))

    engine = get_engine()
    try:
        result = engine.import_file(saved_path)
    except Exception as e:
        flash(f"文件读取失败: {e}")
        return redirect(url_for("imports.index"))

    preview, unmatched = _build_preview(result)
    mappings = session.get("import_mappings") or {}

    # 为已手动映射但未自动匹配的 sheet 创建预览条目
    for sheet_name in unmatched:
        if sheet_name in mappings:
            mapped_code = mappings[sheet_name]
            cfg = DeviceTypeRegistry.get(mapped_code)
            if cfg:
                for sr in result.sheets:
                    if sr.sheet_name == sheet_name:
                        preview.append({
                            "sheet": sr.sheet_name,
                            "rows": sr.row_count,
                            "headers": sr.headers,
                            "sample": sr.sample_rows,
                            "type_key": sr.type_key,
                            "detected_type": cfg.code,
                            "detected_name": cfg.name,
                            "accessory_count": sr.accessory_count,
                        })
                        break

    for item in preview:
        sheet_mapping = mappings.get(item["sheet"]) or mappings.get(item["type_key"])
        if sheet_mapping:
            cfg = DeviceTypeRegistry.get(sheet_mapping)
            if cfg:
                item["detected_type"] = cfg.code
                item["detected_name"] = cfg.name

    filename = session.get("import_filename", "导入文件")
    errors = session.get("import_errors", [])
    return render_template(
        "imports/import_preview.html",
        preview=preview,
        filename=filename,
        errors=errors,
    )


@imports.route("/imports/save-mapping", methods=["POST"])
@login_required
def save_mapping():
    saved_path = _get_saved_path()
    if not saved_path:
        flash("会话过期，请重新上传")
        return redirect(url_for("imports.index"))

    mappings = {}
    for key, value in request.form.items():
        if key.startswith("mapping_"):
            sheet_name = key[len("mapping_"):]
            if value:
                mappings[sheet_name] = value

    session["import_mappings"] = mappings

    for sheet_name, type_code in mappings.items():
        existing = SheetMapping.query.filter_by(sheet_name=sheet_name).first()
        if existing:
            existing.type_code = type_code
            existing.updated_at = datetime.utcnow()
        else:
            mapping = SheetMapping(
                sheet_name=sheet_name,
                type_code=type_code,
                created_by=current_user.id,
            )
            db.session.add(mapping)
    db.session.commit()

    return redirect(url_for("imports.preview"))


@imports.route("/imports/execute", methods=["POST"])
@login_required
def execute():
    saved_name = session.get("import_file")
    if not saved_name:
        flash("找不到已上传的文件，请重新上传")
        return redirect(url_for("imports.index"))

    upload_folder = current_app.config.get("UPLOAD_FOLDER")
    saved_path = os.path.join(upload_folder, saved_name)
    if not os.path.exists(saved_path):
        flash("临时文件丢失，请重新上传")
        return redirect(url_for("imports.index"))

    engine = get_engine()
    mappings = session.get("import_mappings") or {}
    try:
        result = engine.import_file(saved_path, type_overrides=mappings)
    except Exception as e:
        flash(f"文件读取失败: {e}")
        return redirect(url_for("imports.index"))

    merge_config = {}
    ledger_name_overrides = {}
    dedup_modes = {}
    for key, value in request.form.items():
        if key.startswith("merge_"):
            sheet_name = key[len("merge_"):]
            if value == "1":
                merge_config[sheet_name] = True
        elif key.startswith("ledger_name_"):
            sheet_name = key[len("ledger_name_"):]
            if value:
                ledger_name_overrides[sheet_name] = value.strip()
        elif key.startswith("dedup_mode_"):
            sheet_name = key[len("dedup_mode_"):]
            dedup_modes[sheet_name] = value

    total_created = 0
    total_skipped = 0
    total_updated = 0
    per_sheet = []
    type_ledgers = {}

    for sr in result.sheets:
        sheet_name = sr.sheet_name

        type_code = sr.type_code
        if sheet_name in mappings:
            type_code = mappings[sheet_name]
        elif sr.type_key and sr.type_key in mappings:
            type_code = mappings[sr.type_key]

        if not type_code or type_code in ("summary", "cover"):
            per_sheet.append({"sheet": sheet_name, "created": 0, "skipped": True})
            continue

        if merge_config.get(sheet_name) and type_code in type_ledgers:
            ledger = type_ledgers[type_code]
        else:
            ledger_name = ledger_name_overrides.get(sheet_name, sheet_name)
            ledger = Ledger.query.filter_by(
                名称=ledger_name, 类型=type_code, created_by=current_user.id
            ).first()
            if not ledger:
                ledger = Ledger()
                ledger.名称 = ledger_name
                ledger.描述 = f"由用户 {current_user.username} 导入于 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                ledger.类型 = type_code
                ledger.created_by = current_user.id
                ledger.status = "draft"
                db.session.add(ledger)
                db.session.flush()
            if merge_config.get(sheet_name):
                type_ledgers[type_code] = ledger

        dedup_mode = dedup_modes.get(sheet_name, "skip")
        created = 0
        skipped = 0
        updated = 0

        from app.utils.duplicate_check import check_duplicate
        config = DeviceTypeRegistry.get(type_code)
        model_cls = config.model_class if config else None

        # 中止模式：预检所有记录
        if dedup_mode == "abort" and model_cls:
            abort_duplicates = []
            for record in sr.records:
                unit = getattr(record, "装置名称", None) or ""
                tag = getattr(record, "位号", None) or ""
                if tag and check_duplicate(model_cls, unit, tag):
                    abort_duplicates.append(f"{unit}/{tag}")
            if abort_duplicates:
                flash(f"[{sheet_name}] 发现 {len(abort_duplicates)} 条重复记录，导入已中止")
                continue

        # 写入记录
        seen_tags = {}
        for record in sr.records:
            record.ledger_id = ledger.id
            record.created_by = current_user.id
            record.status = "draft"

            tag = getattr(record, '位号', None)
            if tag:
                tag = tag.strip()
            if not tag or tag in ('/', '-'):
                continue

            unit = getattr(record, "装置名称", None) or ""

            # 同批次内去重
            batch_key = f"{unit}|{tag}"
            if batch_key in seen_tags:
                skipped += 1
                continue
            seen_tags[batch_key] = True

            if model_cls and check_duplicate(model_cls, unit, tag):
                if dedup_mode == "skip":
                    skipped += 1
                    continue
                elif dedup_mode == "overwrite":
                    existing = model_cls.query.filter(
                        model_cls.装置名称 == unit,
                        model_cls.位号 == tag,
                        model_cls.status != "draft",
                    ).first()
                    if existing:
                        for col in model_cls.__table__.columns:
                            col_name = col.name
                            if col_name not in ("id", "ledger_id", "created_by", "created_at", "status", "updated_at", "approved_by", "approved_at"):
                                setattr(existing, col_name, getattr(record, col_name, None))
                        existing.updated_at = datetime.utcnow()
                        updated += 1
                        continue

            db.session.add(record)
            created += 1

        # 阀门附件处理
        from app.devices.valve_helper import VALVE_TYPES
        device_config = DeviceTypeRegistry.get(type_code)
        is_valve_type = device_config and device_config.code in VALVE_TYPES
        if is_valve_type and sr.accessories:
            db.session.flush()
            for record, acc_group in zip(sr.records, sr.accessories):
                if not record.id:
                    continue
                for acc in acc_group:
                    name = acc.get("名称", "")
                    attachment = ValveAttachment(
                        device_type=type_code,
                        device_id=record.id,
                        名称=name,
                        type=_infer_attachment_type(name),
                        型号规格=acc.get("型号规格", ""),
                        生产厂家=acc.get("生产厂家", ""),
                        设备等级=acc.get("设备等级", ""),
                    )
                    db.session.add(attachment)

        per_sheet.append({"sheet": sheet_name, "created": created, "skipped": skipped, "updated": updated, "skipped_sheet": False})
        total_created += created
        total_skipped += skipped
        total_updated += updated

    db.session.commit()

    try:
        os.remove(saved_path)
    except Exception:
        pass
    for key in (
        "import_file", "import_preview", "import_errors",
        "import_mappings", "import_filename",
    ):
        session.pop(key, None)

    parts = [f"创建 {total_created} 条"]
    if total_skipped:
        parts.append(f"跳过 {total_skipped} 条")
    if total_updated:
        parts.append(f"更新 {total_updated} 条")
    flash(f"导入完成：{'，'.join(parts)}")
    return redirect(url_for("imports.index"))
