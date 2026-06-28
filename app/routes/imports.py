from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, session, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import db, Ledger, ValveAttachment, SheetMapping
from app.devices import DeviceTypeRegistry
from app.import_engine import ImportEngine
from app.utils.duplicate_check import check_duplicate
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


def _skip_duplicate_for_tag(tag):
    """位号为 / 或 \\ 时不参与重复验证"""
    return not tag or tag.strip() in ("/", "-", "\\")


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
    skipped = session.pop("import_skipped", None)
    return render_template("imports/import.html", skipped=skipped)


def _build_preview(result):
    """从 ImportResult 构建预览数据和未匹配列表，增加重复检测"""
    preview = []
    unmatched = []
    for sr in result.sheets:
        if sr.type_code and sr.type_code not in ("summary", "cover"):
            config = DeviceTypeRegistry.get(sr.type_code)
            model_cls = config.model_class if config else None
            duplicates = []
            display_fields = config.get_fields_flat() if config else []
            if model_cls and hasattr(model_cls, "装置名称") and hasattr(model_cls, "位号"):
                for record in sr.records:
                    unit = getattr(record, "装置名称", None) or ""
                    tag = getattr(record, "位号", None) or ""
                    if tag and not _skip_duplicate_for_tag(tag):
                        existing = model_cls.query.filter(
                            model_cls.装置名称 == unit,
                            model_cls.位号 == tag,
                            model_cls.created_by == current_user.id,
                        ).first()
                        if existing:
                            existing_data = {}
                            for col_name in display_fields:
                                val = getattr(existing, col_name, None)
                                if val is not None and val != "":
                                    existing_data[col_name] = str(val)
                            new_data = {}
                            for col_name in display_fields:
                                val = getattr(record, col_name, None)
                                if val is not None and val != "":
                                    new_data[col_name] = str(val)
                            all_keys = list(dict.fromkeys(list(new_data.keys()) + list(existing_data.keys())))
                            duplicates.append({
                                "装置名称": unit,
                                "位号": tag,
                                "existing_data": existing_data,
                                "new_data": new_data,
                                "all_keys": [k for k in all_keys if k not in ("装置名称", "位号")],
                            })
            # 检测同批次内重复（相同装置名称+位号的多行数据）
            tag_groups = {}
            for idx, record in enumerate(sr.records):
                tag = getattr(record, "位号", None) or ""
                if _skip_duplicate_for_tag(tag):
                    continue
                unit = getattr(record, "装置名称", None) or ""
                batch_key = f"{unit}|{tag}"
                if batch_key not in tag_groups:
                    tag_groups[batch_key] = []
                tag_groups[batch_key].append(idx)
            batch_conflicts = []
            for batch_key, indices in tag_groups.items():
                if len(indices) > 1:
                    rows = []
                    for idx in indices:
                        record = sr.records[idx]
                        row_data = {}
                        for col_name in display_fields:
                            val = getattr(record, col_name, None)
                            if val is not None and val != "":
                                row_data[col_name] = str(val)
                        rows.append({"row_index": idx, "data": row_data})
                    parts = batch_key.split("|", 1)
                    batch_conflicts.append({
                        "key": batch_key,
                        "装置名称": parts[0],
                        "位号": parts[1] if len(parts) > 1 else "",
                        "rows": rows,
                    })
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
                "batch_conflicts": batch_conflicts,
                "batch_conflict_count": len(batch_conflicts),
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

    has_conflicts = any(p.get("batch_conflict_count", 0) > 0 for p in preview)
    session.pop("import_conflict_choices", None)
    if has_conflicts:
        return redirect(url_for("imports.conflicts"))

    return redirect(url_for("imports.preview"))


@imports.route("/imports/preview")
@login_required
def preview():
    saved_path = _get_saved_path()
    if not saved_path:
        flash("没有预览数据，请重新上传")
        return redirect(url_for("imports.index"))

    engine = get_engine()
    mappings = session.get("import_mappings") or {}
    try:
        result = engine.import_file(saved_path, type_overrides=mappings)
    except Exception as e:
        flash(f"文件读取失败: {e}")
        return redirect(url_for("imports.index"))

    # 应用同批次重复的用户选择
    conflict_choices = session.get("import_conflict_choices", {})
    for sr in result.sheets:
        sheet_choices = conflict_choices.get(sr.sheet_name, {})
        if sheet_choices:
            keep_indices = set()
            for idx, record in enumerate(sr.records):
                tag = getattr(record, "位号", None) or ""
                if _skip_duplicate_for_tag(tag):
                    keep_indices.add(idx)
                    continue
                unit = getattr(record, "装置名称", None) or ""
                batch_key = f"{unit}|{tag}"
                if batch_key in sheet_choices:
                    if idx == sheet_choices[batch_key]:
                        keep_indices.add(idx)
                else:
                    keep_indices.add(idx)
            sr.records = [r for i, r in enumerate(sr.records) if i in keep_indices]
            sr.row_count = len(sr.records)

    preview, unmatched = _build_preview(result)

    # 为已手动映射但未自动匹配的 sheet 创建预览条目
    for sheet_name in unmatched:
        if sheet_name in mappings:
            mapped_code = mappings[sheet_name]
            cfg = DeviceTypeRegistry.get(mapped_code)
            if cfg:
                for sr in result.sheets:
                    if sr.sheet_name == sheet_name:
                        model_cls = cfg.model_class if cfg else None
                        duplicates = []
                        display_fields = cfg.get_fields_flat() if cfg else []
                        if model_cls and hasattr(model_cls, "装置名称") and hasattr(model_cls, "位号"):
                            for record in sr.records:
                                unit = getattr(record, "装置名称", None) or ""
                                tag = getattr(record, "位号", None) or ""
                                if tag and not _skip_duplicate_for_tag(tag):
                                    existing = model_cls.query.filter(
                                        model_cls.装置名称 == unit,
                                        model_cls.位号 == tag,
                                        model_cls.created_by == current_user.id,
                                    ).first()
                                    if existing:
                                        existing_data = {}
                                        for col_name in display_fields:
                                            val = getattr(existing, col_name, None)
                                            if val is not None and val != "":
                                                existing_data[col_name] = str(val)
                                        new_data = {}
                                        for col_name in display_fields:
                                            val = getattr(record, col_name, None)
                                            if val is not None and val != "":
                                                new_data[col_name] = str(val)
                                        all_keys = list(dict.fromkeys(list(new_data.keys()) + list(existing_data.keys())))
                                        duplicates.append({
                                            "装置名称": unit,
                                            "位号": tag,
                                            "existing_data": existing_data,
                                            "new_data": new_data,
                                            "all_keys": [k for k in all_keys if k not in ("装置名称", "位号")],
                                        })
                        preview.append({
                            "sheet": sr.sheet_name,
                            "rows": sr.row_count,
                            "headers": sr.headers,
                            "sample": sr.sample_rows,
                            "type_key": sr.type_key,
                            "detected_type": cfg.code,
                            "detected_name": cfg.name,
                            "accessory_count": sr.accessory_count,
                            "duplicates": duplicates,
                            "duplicate_count": len(duplicates),
                            "new_count": sr.row_count - len(duplicates),
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

    engine = get_engine()
    try:
        result = engine.import_file(saved_path, type_overrides=mappings)
    except Exception:
        return redirect(url_for("imports.preview"))
    preview, _ = _build_preview(result)
    has_conflicts = any(p.get("batch_conflict_count", 0) > 0 for p in preview)
    session.pop("import_conflict_choices", None)
    if has_conflicts:
        return redirect(url_for("imports.conflicts"))
    return redirect(url_for("imports.preview"))


@imports.route("/imports/conflicts")
@login_required
def conflicts():
    saved_path = _get_saved_path()
    if not saved_path:
        flash("没有待处理的文件，请重新上传")
        return redirect(url_for("imports.index"))

    engine = get_engine()
    mappings = session.get("import_mappings") or {}
    try:
        result = engine.import_file(saved_path, type_overrides=mappings)
    except Exception as e:
        flash(f"文件读取失败: {e}")
        return redirect(url_for("imports.index"))

    preview, _ = _build_preview(result)
    conflicts_data = []
    for p in preview:
        if p["batch_conflict_count"] > 0:
            conflicts_data.append({
                "sheet": p["sheet"],
                "detected_name": p["detected_name"],
                "conflicts": p["batch_conflicts"],
            })
    if not conflicts_data:
        return redirect(url_for("imports.preview"))
    return render_template("imports/resolve_conflicts.html",
                           conflicts_data=conflicts_data,
                           filename=session.get("import_filename", "导入文件"),
                           errors=session.get("import_errors", []))


@imports.route("/imports/resolve-conflicts", methods=["POST"])
@login_required
def resolve_conflicts():
    saved_path = _get_saved_path()
    if not saved_path:
        flash("会话过期，请重新上传")
        return redirect(url_for("imports.index"))

    choices = {}
    for key, value in request.form.items():
        if key.startswith("choice_"):
            remainder = key[len("choice_"):]
            if "__" in remainder:
                sheet_name, batch_key = remainder.split("__", 1)
                if sheet_name not in choices:
                    choices[sheet_name] = {}
                choices[sheet_name][batch_key] = int(value)
    session["import_conflict_choices"] = choices
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

        if merge_config.get(sheet_name):
            if type_code in type_ledgers:
                ledger = type_ledgers[type_code]
            else:
                ledger = Ledger.query.filter_by(
                    类型=type_code, created_by=current_user.id
                ).first()
                ledger_was_created = False
                if not ledger:
                    ledger = Ledger()
                    ledger.名称 = ledger_name_overrides.get(sheet_name, sheet_name)
                    ledger.描述 = f"由用户 {current_user.username} 导入于 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                    ledger.类型 = type_code
                    ledger.created_by = current_user.id
                    ledger.status = "draft"
                    db.session.add(ledger)
                    db.session.flush()
                    ledger_was_created = True
                type_ledgers[type_code] = ledger
        else:
            ledger_name = ledger_name_overrides.get(sheet_name, sheet_name)
            ledger = Ledger.query.filter_by(
                名称=ledger_name, 类型=type_code, created_by=current_user.id
            ).first()
            ledger_was_created = False
            if not ledger:
                ledger_was_created = True
                ledger = Ledger()
                ledger.名称 = ledger_name
                ledger.描述 = f"由用户 {current_user.username} 导入于 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                ledger.类型 = type_code
                ledger.created_by = current_user.id
                ledger.status = "draft"
                db.session.add(ledger)
                db.session.flush()

        dedup_mode = dedup_modes.get(sheet_name, "skip")
        created = 0
        skipped = 0
        updated = 0

        config = DeviceTypeRegistry.get(type_code)
        model_cls = config.model_class if config else None

        # 中止模式：预检所有记录
        if dedup_mode == "abort" and model_cls:
            abort_duplicates = []
            for record in sr.records:
                unit = getattr(record, "装置名称", None) or ""
                tag = getattr(record, "位号", None) or ""
                if tag and check_duplicate(model_cls, unit, tag, created_by=current_user.id):
                    abort_duplicates.append(f"{unit}/{tag}")
            if abort_duplicates:
                flash(f"[{sheet_name}] 发现 {len(abort_duplicates)} 条重复记录，导入已中止")
                if ledger_was_created:
                    db.session.delete(ledger)
                continue

        # 从 session 读取同批次重复的用户选择
        batch_choices = session.get("import_conflict_choices", {}).get(sheet_name, {})

        # 写入记录
        seen_tags = {}
        skipped_details = []
        for idx, record in enumerate(sr.records):
            record.ledger_id = ledger.id
            record.created_by = current_user.id
            record.status = "draft"

            tag = getattr(record, '位号', None)
            if tag:
                tag = tag.strip()
            if _skip_duplicate_for_tag(tag):
                continue

            unit = getattr(record, "装置名称", None) or ""
            batch_key = f"{unit}|{tag}"

            # 同批次重复：只保留用户选择的那一行
            if batch_key in batch_choices:
                if idx != batch_choices[batch_key]:
                    skipped += 1
                    skipped_details.append({"位号": tag, "装置名称": unit, "原因": "用户选择了其他重复行"})
                    continue
            elif batch_key in seen_tags:
                skipped += 1
                skipped_details.append({"位号": tag, "装置名称": unit, "原因": "同批次内重复"})
                continue
            seen_tags[batch_key] = True

            if model_cls and check_duplicate(model_cls, unit, tag, created_by=current_user.id):
                if dedup_mode == "skip":
                    skipped += 1
                    skipped_details.append({"位号": tag, "装置名称": unit, "原因": "数据库中已存在"})
                    continue
                elif dedup_mode == "overwrite":
                    existing = model_cls.query.filter(
                        model_cls.装置名称 == unit,
                        model_cls.位号 == tag,
                        model_cls.created_by == current_user.id,
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

        if created == 0 and ledger_was_created:
            db.session.delete(ledger)

        per_sheet.append({"sheet": sheet_name, "created": created, "skipped": skipped, "updated": updated, "skipped_sheet": False, "skipped_details": skipped_details})
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

    all_skipped_details = []
    for s in per_sheet:
        all_skipped_details.extend(s.get("skipped_details", []))
    parts = [f"创建 {total_created} 条"]
    if total_skipped:
        parts.append(f"跳过 {total_skipped} 条")
    if total_updated:
        parts.append(f"更新 {total_updated} 条")
    flash(f"导入完成：{'，'.join(parts)}")
    if all_skipped_details:
        session["import_skipped"] = all_skipped_details
    return redirect(url_for("imports.index"))
