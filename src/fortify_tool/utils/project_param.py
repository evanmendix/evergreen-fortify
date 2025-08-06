import yaml
from fortify_tool.utils.get_filepath import get_yaml_path, get_user_yaml_path

def read_yaml():
    path = get_yaml_path()
    with open(path, encoding="utf8") as f:
        data = yaml.safe_load(f)
        return data


def read_user_yaml():
    """讀取使用者設定檔案

    Returns:
        dict: 使用者設定資料
    """
    path = get_user_yaml_path()
    with open(path, encoding="utf8") as f:
        data = yaml.safe_load(f)
        return data

