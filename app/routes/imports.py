from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, session, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import db, Ledger, Valve, ValveAttachment, SheetMapping
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
    """从 ImportResult 构建预览数据和未匹配列表"""
    preview = []
    unmatched = []
    for sr in result.sheets:
        if sr.type_code and sr.type_code not in ("summary", "cover"):
            preview.append({
                "sheet": sr.sheet_name,
                "rows": sr.row_count,
                "headers": sr.headers,
                "sample": sr.sample_rows,
                "type_key": sr.type_key,
                "detected_type": sr.type_code,
                "detected_name": sr.type_name,
                "accessory_count": sr.accessory_count,
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
        return render_template(
            "imports/import.html",
            unmatched=unmatched,
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
    try:
        result = engine.import_file(saved_path)
    except Exception as e:
        flash(f"文件读取失败: {e}")
        return redirect(url_for("imports.index"))

    mappings = session.get("import_mappings") or {}

    merge_config = {}
    ledger_name_overrides = {}
    for key, value in request.form.items():
        if key.startswith("merge_"):
            sheet_name = key[len("merge_"):]
            if value == "1":
                merge_config[sheet_name] = True
        elif key.startswith("ledger_name_"):
            sheet_name = key[len("ledger_name_"):]
            if value:
                ledger_name_overrides[sheet_name] = value.strip()

    total_created = 0
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

        # 写入记录
        created = 0
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

            # 对有位号且数据库有 UNIQUE 约束的表，检查重复
            tag_unique = False
            table = getattr(record.__class__, '__table__', None)
            if table and '位号' in table.c:
                tag_unique = table.c['位号'].unique
            if tag_unique:
                if tag in seen_tags:
                    continue
                seen_tags[tag] = True
                existing = record.__class__.query.filter_by(位号=tag).first()
                if existing:
                    continue

            db.session.add(record)
            created += 1

        # 阀门附件处理
        device_config = DeviceTypeRegistry.get(type_code)
        is_valve_type = device_config and device_config.model_class and device_config.model_class.__name__ == "Valve"
        if is_valve_type and sr.accessories:
            db.session.flush()
            acc_idx = 0
            for record in sr.records:
                if not record.id:
                    continue
                while acc_idx < len(sr.accessories):
                    acc = sr.accessories[acc_idx]
                    acc_idx += 1
                    name = acc.get("名称", "")
                    attachment = ValveAttachment(
                        valve_id=record.id,
                        名称=name,
                        type=_infer_attachment_type(name),
                        型号规格=acc.get("型号规格", ""),
                        生产厂家=acc.get("生产厂家", ""),
                        设备等级=acc.get("设备等级", ""),
                    )
                    db.session.add(attachment)

        per_sheet.append({"sheet": sheet_name, "created": created, "skipped": False})
        total_created += created

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

    flash(f"导入完成：共创建 {total_created} 条记录")
    return redirect(url_for("imports.index"))
