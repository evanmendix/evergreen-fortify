from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

CONFIG_DIR = PROJECT_ROOT / "config"
CACHE_DIR = PROJECT_ROOT / ".cache"
DATA_DIR = PROJECT_ROOT / "產出資料"
REPORTS_DIR = DATA_DIR / "Fortify報告整理"
SOLUTIONS_DIR = DATA_DIR / "Issue修復共筆"

PROJECT_CACHE_DIR = CACHE_DIR  # 保持兼容性，指向新的 .cache 目录


def get_yaml_path():
    yaml_filename = "config.yaml"
    return str((CONFIG_DIR / yaml_filename).resolve())


def get_user_yaml_path():
    yaml_filename = "user_config.yaml"
    return str((CONFIG_DIR / yaml_filename).resolve())
