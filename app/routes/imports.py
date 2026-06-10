from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, session, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import db, Ledger
from app.devices import DeviceTypeRegistry
from app.utils.importer import safe_read_excel
import os
import uuid

imports = Blueprint("imports", __name__)


def detect_device_type(sheet_name):
    # 尝试直接以 code 匹配
    cfg = DeviceTypeRegistry.get(sheet_name)
    if cfg:
        return cfg

    # 尝试以展示名称匹配
    for c in DeviceTypeRegistry.all():
        if c.name == sheet_name or c.name.lower() == sheet_name.lower():
            return c

    # 尝试 code/name 的小写包含匹配
    for c in DeviceTypeRegistry.all():
        if sheet_name.lower() in (c.code or "").lower() or sheet_name.lower() in (c.name or "").lower():
            return c

    return None


@imports.route("/imports")
@login_required
def index():
    return render_template("imports/import.html")


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

    filename = secure_filename(file.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in (".xlsx", ".xls"):
        flash("仅支持 .xlsx / .xls 文件")
        return redirect(url_for("imports.index"))

    uid = uuid.uuid4().hex
    saved_name = f"import_{uid}{ext}"
    upload_folder = current_app.config.get("UPLOAD_FOLDER")
    saved_path = os.path.join(upload_folder, saved_name)
    file.save(saved_path)

    try:
        sheets_data = safe_read_excel(saved_path)
    except Exception as e:
        flash(f"文件读取失败: {e}")
        try:
            os.remove(saved_path)
        except:
            pass
        return redirect(url_for("imports.index"))

    raw_data = sheets_data
    preview = []
    unmatched = []
    for sd in sheets_data:
        cfg = detect_device_type(sd["sheet"])
        if cfg:
            preview.append({
                "sheet": sd["sheet"],
                "rows": sd["row_count"],
                "columns": sd["columns"],
                "sample": sd["sample"],
                "detected_type": cfg.code,
                "detected_name": cfg.name,
            })
        else:
            unmatched.append(sd["sheet"])

    session["multi_import_file"] = saved_name
    session["multi_import_raw"] = raw_data

    if unmatched:
        all_types = [{"code": t.code, "name": t.name} for t in DeviceTypeRegistry.all()]
        return render_template(
            "imports/import.html",
            unmatched=unmatched,
            all_types=all_types,
            filename=filename,
        )

    session["multi_import_preview"] = preview
    session["multi_import_filename"] = filename
    return redirect(url_for("imports.preview"))


@imports.route("/imports/preview")
@login_required
def preview():
    preview_data = session.get("multi_import_preview")
    if not preview_data:
        flash("没有预览数据，请重新上传")
        return redirect(url_for("imports.index"))
    filename = session.get("multi_import_filename", request.args.get("filename", "导入文件"))
    return render_template(
        "imports/import_preview.html",
        preview=preview_data,
        filename=filename,
    )


@imports.route("/imports/save-mapping", methods=["POST"])
@login_required
def save_mapping():
    raw_data = session.get("multi_import_raw")
    if not raw_data:
        flash("会话过期，请重新上传")
        return redirect(url_for("imports.index"))

    mappings = {}
    for key, value in request.form.items():
        if key.startswith("mapping_"):
            sheet_name = key[len("mapping_"):]
            if value:
                mappings[sheet_name] = value

    session["import_mappings"] = mappings

    # Rebuild preview with updated types
    preview = []
    for sd in raw_data:
        cfg = None
        if sd["sheet"] in mappings:
            cfg = DeviceTypeRegistry.get(mappings[sd["sheet"]])
        if not cfg:
            cfg = detect_device_type(sd["sheet"])
        preview.append({
            "sheet": sd["sheet"],
            "rows": sd["row_count"],
            "columns": sd["columns"],
            "sample": sd["sample"],
            "detected_type": cfg.code if cfg else None,
            "detected_name": cfg.name if cfg else None,
        })
    session["multi_import_preview"] = preview
    return redirect(url_for("imports.preview"))


@imports.route("/imports/execute", methods=["POST"])
@login_required
def execute():
    saved_name = session.get("multi_import_file")
    if not saved_name:
        flash("找不到已上传的文件，请重新上传")
        return redirect(url_for("imports.index"))

    upload_folder = current_app.config.get("UPLOAD_FOLDER")
    saved_path = os.path.join(upload_folder, saved_name)
    if not os.path.exists(saved_path):
        flash("临时文件丢失，请重新上传")
        return redirect(url_for("imports.index"))

    # 读取文件
    try:
        sheets_data = safe_read_excel(saved_path)
    except Exception as e:
        flash(f"文件读取失败: {e}")
        return redirect(url_for("imports.index"))

    # 读取用户映射
    mappings = session.get("import_mappings") or {}

    # 解析合并配置和台账名称
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

    for sd in sheets_data:
        sheet_name = sd["sheet"]

        # 确定类型：优先使用用户映射
        cfg = None
        if sheet_name in mappings and mappings[sheet_name]:
            cfg = DeviceTypeRegistry.get(mappings[sheet_name])
        if not cfg:
            cfg = detect_device_type(sheet_name)
        if not cfg:
            per_sheet.append({"sheet": sheet_name, "created": 0, "skipped": True})
            continue

        type_code = cfg.code

        # 确定 Ledger
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
                ledger.描述 = f"由用户 {current_user.username} 导入于导入功能创建"
                ledger.类型 = type_code
                ledger.created_by = current_user.id
                ledger.status = "draft"
                db.session.add(ledger)
                db.session.flush()
            if merge_config.get(sheet_name):
                type_ledgers[type_code] = ledger

        # 逐行创建设备记录
        created = 0
        model_cls = cfg.model_class
        for row in sd["rows"]:
            if not model_cls:
                continue
            inst = model_cls()
            inst.ledger_id = ledger.id
            inst.created_by = current_user.id
            inst.status = "draft"
            for col, val in row.items():
                if hasattr(inst, col) and val:
                    try:
                        setattr(inst, col, val)
                    except Exception:
                        pass
            db.session.add(inst)
            created += 1

        per_sheet.append({"sheet": sheet_name, "created": created, "skipped": False})
        total_created += created

    db.session.commit()

    # 清理
    try:
        os.remove(saved_path)
    except:
        pass
    for key in ("multi_import_file", "multi_import_preview", "multi_import_raw",
                 "import_mappings", "multi_import_filename"):
        session.pop(key, None)

    flash(f"导入完成：共创建 {total_created} 条记录")
    return redirect(url_for("ledgers.list"))
