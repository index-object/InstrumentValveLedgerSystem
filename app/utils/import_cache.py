import os
import glob
from datetime import datetime

IMPORT_FILE_PATTERNS = ["import_*.*", "import_*.xls", "import_*.xlsx",
                        "maintenance_import_*.*", "maintenance_import_*.xls", "maintenance_import_*.xlsx"]


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
