import os
import re
import glob
import json
import time
import uuid
from datetime import datetime

IMPORT_FILE_PATTERNS = ["import_*.*", "import_*.xls", "import_*.xlsx",
                        "maintenance_import_*.*", "maintenance_import_*.xls", "maintenance_import_*.xlsx"]

# 预览/结果等中间数据存服务器端，会话里只放 token。
# 文件名以下划线开头，get_import_cache_files 会跳过，不会出现在导入缓存页。
SCRATCH_PREFIX = "_scratch_"
SCRATCH_SUFFIX = ".json"
SCRATCH_MAX_AGE_HOURS = 24
_SCRATCH_TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")


def get_import_cache_files(upload_folder):
    seen = set()
    files = []
    for pattern in IMPORT_FILE_PATTERNS:
        for path in glob.glob(os.path.join(upload_folder, pattern)):
            name = os.path.basename(path)
            if name.startswith("_") or name in seen:
                continue
            seen.add(name)
            stat = os.stat(path)
            files.append({
                "name": name,
                "path": path,
                "size": stat.st_size,
                "mtime": datetime.fromtimestamp(stat.st_mtime),
            })
    files.sort(key=lambda f: f["mtime"], reverse=True)
    return files


def cleanup_import_cache(upload_folder, max_keep):
    files = get_import_cache_files(upload_folder)
    if len(files) <= max_keep:
        return 0
    deleted = 0
    for f in files[max_keep:]:
        try:
            os.remove(f["path"])
            deleted += 1
        except OSError:
            pass
    return deleted


# ========== 服务器端中间数据（scratch） ==========
#
# Flask 默认会话是签名 Cookie，单个 Cookie 的实际上限约 4KB（Werkzeug 上限
# 4093 字节）。把解析出来的整份记录塞进会话，文件稍大就会让浏览器静默丢弃
# 整个 Cookie，下一步再读会话就只剩「找不到已上传的文件」。
# 因此这里把中间数据写到服务器端，会话里只保留一个随机 token。


def _scratch_path(upload_folder, token):
    return os.path.join(upload_folder, f"{SCRATCH_PREFIX}{token}{SCRATCH_SUFFIX}")


def _valid_scratch_token(token):
    """token 必须是 uuid4().hex，既保证不会重名，也杜绝路径穿越。"""
    return isinstance(token, str) and bool(_SCRATCH_TOKEN_RE.match(token))


def save_scratch(upload_folder, data):
    """把中间数据写入服务器端，返回放进会话的随机 token。"""
    token = uuid.uuid4().hex
    path = _scratch_path(upload_folder, token)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
    return token


def load_scratch(upload_folder, token):
    """按 token 读回中间数据；token 非法或文件缺失/损坏时返回 None。"""
    if not _valid_scratch_token(token):
        return None
    try:
        with open(_scratch_path(upload_folder, token), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def delete_scratch(upload_folder, token):
    """删除中间数据，失败时静默忽略（过期数据由 cleanup_scratch 兜底）。"""
    if not _valid_scratch_token(token):
        return
    try:
        os.remove(_scratch_path(upload_folder, token))
    except OSError:
        pass


def cleanup_scratch(upload_folder, max_age_hours=SCRATCH_MAX_AGE_HOURS):
    """清理超过保留时长的中间数据（用户放弃预览的残留）。"""
    deadline = time.time() - max_age_hours * 3600
    deleted = 0
    for path in glob.glob(os.path.join(upload_folder, f"{SCRATCH_PREFIX}*{SCRATCH_SUFFIX}")):
        try:
            if os.path.getmtime(path) < deadline:
                os.remove(path)
                deleted += 1
        except OSError:
            pass
    return deleted
