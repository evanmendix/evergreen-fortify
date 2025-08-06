from ..utils.config_loader import get_config


def list_repos():
    """
    取得並印出 repo 名稱列表（改為從 config.yaml 取得）。
    """
    config = get_config()
    repos = config.get_repos("all")
    return repos


if __name__ == "__main__":
    list_repos()
