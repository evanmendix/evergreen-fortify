"""
增強的 Cache 管理系統

管理 Pipeline 狀態、掃描結果、分支資訊等的本地快取
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from .get_filepath import PROJECT_ROOT


class CacheManager:
    """Cache 管理器"""
    
    def __init__(self):
        self.cache_dir = PROJECT_ROOT / ".cache"
        self.cache_dir.mkdir(exist_ok=True)
        
        # 各種 cache 檔案
        self.download_state_file = self.cache_dir / "fortify_download_state.json"
        self.pipeline_cache_file = self.cache_dir / "pipeline_status_cache.json"
        self.scan_results_cache_file = self.cache_dir / "scan_results_cache.json"
        self.branch_info_cache_file = self.cache_dir / "branch_info_cache.json"
    
    def load_download_state(self) -> Dict[str, int]:
        """載入下載狀態 (舊格式兼容)"""
        try:
            if self.download_state_file.exists():
                with open(self.download_state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}
    
    def save_download_state(self, state: Dict[str, int]):
        """儲存下載狀態 (舊格式兼容)"""
        try:
            with open(self.download_state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            print(f"儲存下載狀態失敗: {e}")
    
    def load_pipeline_cache(self) -> Dict[str, Any]:
        """載入 Pipeline 狀態快取"""
        try:
            if self.pipeline_cache_file.exists():
                with open(self.pipeline_cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {
            "last_updated": None,
            "projects": {}
        }
    
    def save_pipeline_cache(self, cache_data: Dict[str, Any]):
        """儲存 Pipeline 狀態快取"""
        try:
            cache_data["last_updated"] = datetime.now().isoformat()
            with open(self.pipeline_cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"儲存 Pipeline 快取失敗: {e}")
    
    def update_pipeline_project(self, project_name: str, pipeline_data: Dict[str, Any]):
        """更新單一專案的 Pipeline 資訊"""
        cache = self.load_pipeline_cache()
        
        if "projects" not in cache:
            cache["projects"] = {}
        
        cache["projects"][project_name] = {
            **pipeline_data,
            "last_updated": datetime.now().isoformat()
        }
        
        self.save_pipeline_cache(cache)
    
    def load_scan_results_cache(self) -> Dict[str, Any]:
        """載入掃描結果快取"""
        try:
            if self.scan_results_cache_file.exists():
                with open(self.scan_results_cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {
            "last_updated": None,
            "projects": {}
        }
    
    def save_scan_results_cache(self, results: Dict[str, Any]):
        """儲存掃描結果快取"""
        try:
            cache_data = {
                "last_updated": datetime.now().isoformat(),
                "projects": results
            }
            with open(self.scan_results_cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"儲存掃描結果快取失敗: {e}")
    
    def load_branch_info_cache(self) -> Dict[str, Any]:
        """載入分支資訊快取"""
        try:
            if self.branch_info_cache_file.exists():
                with open(self.branch_info_cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {
            "last_updated": None,
            "projects": {}
        }
    
    def save_branch_info_cache(self, branch_data: Dict[str, Any]):
        """儲存分支資訊快取"""
        try:
            cache_data = {
                "last_updated": datetime.now().isoformat(),
                "projects": branch_data
            }
            with open(self.branch_info_cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"儲存分支資訊快取失敗: {e}")
    
    def update_project_branch_info(self, project_name: str, branch_name: str, 
                                  pipeline_id: Optional[str] = None):
        """更新專案分支資訊"""
        cache = self.load_branch_info_cache()
        
        if "projects" not in cache:
            cache["projects"] = {}
        
        cache["projects"][project_name] = {
            "branch_name": branch_name,
            "pipeline_id": pipeline_id,
            "last_updated": datetime.now().isoformat()
        }
        
        # 直接儲存，不要再包一層
        try:
            cache["last_updated"] = datetime.now().isoformat()
            with open(self.branch_info_cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"儲存分支資訊快取失敗: {e}")
    
    def get_project_pipeline_info(self, project_name: str) -> Optional[Dict[str, Any]]:
        """取得專案的 Pipeline 資訊"""
        cache = self.load_pipeline_cache()
        return cache.get("projects", {}).get(project_name)
    
    def get_project_scan_results(self, project_name: str) -> Optional[Dict[str, Any]]:
        """取得專案的掃描結果"""
        cache = self.load_scan_results_cache()
        return cache.get("projects", {}).get(project_name)
    
    def get_project_branch_info(self, project_name: str) -> Optional[Dict[str, Any]]:
        """取得專案的分支資訊"""
        cache = self.load_branch_info_cache()
        return cache.get("projects", {}).get(project_name)
    
    def is_cache_fresh(self, cache_type: str, max_age_hours: int = 1) -> bool:
        """檢查快取是否新鮮"""
        try:
            if cache_type == "pipeline":
                cache = self.load_pipeline_cache()
            elif cache_type == "scan_results":
                cache = self.load_scan_results_cache()
            elif cache_type == "branch_info":
                cache = self.load_branch_info_cache()
            else:
                return False
            
            last_updated = cache.get("last_updated")
            if not last_updated:
                return False
            
            last_update_time = datetime.fromisoformat(last_updated)
            age_hours = (datetime.now() - last_update_time).total_seconds() / 3600
            
            return age_hours < max_age_hours
        except Exception:
            return False
    
    def clear_cache(self, cache_type: Optional[str] = None):
        """清除快取"""
        if cache_type is None or cache_type == "all":
            # 清除所有快取
            for cache_file in [self.pipeline_cache_file, self.scan_results_cache_file, 
                             self.branch_info_cache_file]:
                if cache_file.exists():
                    cache_file.unlink()
        elif cache_type == "pipeline":
            if self.pipeline_cache_file.exists():
                self.pipeline_cache_file.unlink()
        elif cache_type == "scan_results":
            if self.scan_results_cache_file.exists():
                self.scan_results_cache_file.unlink()
        elif cache_type == "branch_info":
            if self.branch_info_cache_file.exists():
                self.branch_info_cache_file.unlink()


# 全域 cache manager 實例
_cache_manager = None

def get_cache_manager() -> CacheManager:
    """取得 cache manager 實例"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager
