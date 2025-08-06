"""
YAML 設定檔載入工具

統一管理設定檔的載入，支援：
- 統一設定檔 (config.yaml)
- 環境變數覆蓋
"""

import os
import yaml
from typing import Dict, Any, List, Optional
from pathlib import Path


class ConfigLoader:
    def __init__(self, config_dir: str = None):
        """
        初始化設定載入器
        
        Args:
            config_dir: 設定檔目錄路徑，預設為專案根目錄下的 config
        """
        if config_dir is None:
            # 從當前檔案位置推導專案根目錄
            current_file = Path(__file__)
            project_root = current_file.parent.parent.parent.parent
            config_dir = project_root / "config"
        
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / "config.yaml"
        
        self._config = None
        self._load_config()
    
    def _load_config(self):
        """載入設定檔"""
        # 載入設定檔
        self._config = self._load_yaml_file(self.config_file)
        if not self._config:
            raise FileNotFoundError(f"找不到設定檔: {self.config_file}")
        
        # 套用環境變數覆蓋
        self._apply_env_overrides()
    
    def _load_yaml_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """載入 YAML 檔案"""
        try:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            return None
        except Exception as e:
            print(f"警告：載入設定檔 {file_path} 時發生錯誤: {e}")
            return None
    
    def _apply_env_overrides(self):
        """套用環境變數覆蓋"""
        # Azure DevOps PAT
        pat = os.getenv("AZURE_DEVOPS_PAT")
        if pat:
            if "azure_devops" not in self._config:
                self._config["azure_devops"] = {}
            self._config["azure_devops"]["personal_access_token"] = pat
        
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        取得設定值，支援點記法路徑
        
        Args:
            key_path: 設定路徑，如 "azure_devops.organization"
            default: 預設值
            
        Returns:
            設定值
        """
        keys = key_path.split('.')
        value = self._config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_repos(self, repo_type: str = "main") -> List[str]:
        """
        取得專案清單
        
        Args:
            repo_type: 專案類型，"main" 或 "all"
            
        Returns:
            專案名稱清單
        """
        if repo_type == "all":
            return self.get("repositories.all_repos", [])
        else:
            # 優先使用用戶偏好設定
            user_repos = self.get("preferences.default_repos", [])
            if user_repos:
                return user_repos
            return self.get("repositories.main_repos", [])
    
    def get_azure_devops_config(self) -> Dict[str, str]:
        """取得 Azure DevOps 設定"""
        return {
            "organization": self.get("azure_devops.organization", ""),
            "project": self.get("azure_devops.project", ""),
            "personal_access_token": self.get("azure_devops.personal_access_token", "")
        }
    
    def get_pipeline_config(self) -> Dict[str, Any]:
        """取得 Pipeline 設定"""
        return {
            "branch_priority": self.get("pipeline.branch_priority", ["evergreen/fortify", "evergreen/main"]),
            "naming_pattern": self.get("pipeline.naming_pattern", "{repo_name}-evergreen-fortify")
        }
    
    def get_paths_config(self) -> Dict[str, str]:
        """取得路徑設定"""
        return {
            "output_dir": self.get("paths.output_dir", "產出資料"),
            "reports_dir": self.get("paths.reports_dir", "產出資料/Fortify報告整理"),
            "solutions_dir": self.get("paths.solutions_dir", "產出資料/Issue修復共筆"),
            "projects_dir": self.get("paths.projects_dir", "專案資料")
        }
    
    def get_solutions_urls(self) -> Dict[str, str]:
        """取得解決方案 URL 清單"""
        return self.get("solutions.hackmd_urls", {})
    
    def reload(self):
        """重新載入設定檔"""
        self._load_config()


# 全域設定載入器實例
_config_loader = None

def get_config() -> ConfigLoader:
    """取得全域設定載入器實例"""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader

def reload_config():
    """重新載入設定"""
    global _config_loader
    if _config_loader:
        _config_loader.reload()
    else:
        _config_loader = ConfigLoader()


# 便利函數
def get_repos(repo_type: str = "main") -> List[str]:
    """取得專案清單"""
    return get_config().get_repos(repo_type)

def get_azure_devops_pat() -> str:
    """取得 Azure DevOps PAT"""
    return get_config().get("azure_devops.personal_access_token", "")

def get_azure_devops_config() -> Dict[str, str]:
    """取得 Azure DevOps 設定"""
    return get_config().get_azure_devops_config()

def get_pipeline_config() -> Dict[str, Any]:
    """取得 Pipeline 設定"""
    return get_config().get_pipeline_config()
