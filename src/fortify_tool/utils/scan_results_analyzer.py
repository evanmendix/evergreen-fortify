"""
掃描結果分析工具

讀取已處理的 Fortify 報告，統計各專案的議題數量和 Source/Sink 統計
整合快取管理，提供分支資訊
"""

import os
import re
import glob
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from .get_filepath import REPORTS_DIR
from .cache_manager import get_cache_manager


class ScanResultsAnalyzer:
    """掃描結果分析器"""
    
    def __init__(self):
        self.reports_dir = REPORTS_DIR / "repo拆分報告"
        self.cache_manager = get_cache_manager()
        
    def get_project_scan_results(self, use_cache: bool = True) -> Dict[str, Dict]:
        """
        取得所有專案的掃描結果統計
        
        Args:
            use_cache: 是否使用快取
            
        Returns:
            Dict: {project_name: {issues: {...}, total_sources: int, total_sinks: int, branch_info: {...}}}
        """
        # 檢查是否使用快取
        if use_cache and self.cache_manager.is_cache_fresh("scan_results", max_age_hours=24):
            cached_results = self.cache_manager.load_scan_results_cache()
            if cached_results.get("projects"):
                return cached_results["projects"]
        
        results = {}
        
        if not self.reports_dir.exists():
            return results
            
        # 遍歷所有專案目錄
        for project_dir in self.reports_dir.iterdir():
            if project_dir.is_dir():
                project_name = project_dir.name.replace("-fortify-result", "")
                project_stats = self._analyze_project_reports(project_dir, project_name)
                if project_stats:
                    results[project_name] = project_stats
        
        # 儲存到快取
        if results:
            self.cache_manager.save_scan_results_cache(results)
                    
        return results
    
    def _analyze_project_reports(self, project_dir: Path, project_name: str) -> Optional[Dict]:
        """
        分析單一專案的報告
        
        Args:
            project_dir: 專案報告目錄
            project_name: 專案名稱
            
        Returns:
            Dict: 專案統計資料
        """
        issues = {}
        total_sources = 0
        total_sinks = 0
        
        # 查找所有 markdown 報告檔案
        md_files = list(project_dir.glob("*.md"))
        
        if not md_files:
            return None
            
        for md_file in md_files:
            # 從檔名提取議題類型
            issue_type = self._extract_issue_type_from_filename(md_file.name)
            if not issue_type:
                continue
                
            # 分析檔案內容
            sources, sinks = self._count_sources_and_sinks(md_file)
            
            if sources > 0 or sinks > 0:
                issues[issue_type] = {
                    "sources": sources,
                    "sinks": sinks,
                    "total": sources + sinks
                }
                total_sources += sources
                total_sinks += sinks
        
        # 取得分支資訊
        branch_info = self._get_branch_info(project_name)
        
        return {
            "issues": issues,
            "total_sources": total_sources,
            "total_sinks": total_sinks,
            "total_issues": len(issues),
            "scan_time": self._get_scan_time(project_dir),
            "branch_info": branch_info
        }
    
    def _extract_issue_type_from_filename(self, filename: str) -> Optional[str]:
        """
        從檔名提取議題類型
        
        Args:
            filename: 檔案名稱，如 "001_Path_Manipulation.md"
            
        Returns:
            str: 議題類型，如 "Path Manipulation"
        """
        # 移除檔案副檔名
        name = filename.replace(".md", "")
        
        # 移除編號前綴 (如 "001_")
        if re.match(r'^\d{3}_', name):
            name = name[4:]
        
        # 將底線替換為空格
        issue_type = name.replace("_", " ")
        
        return issue_type if issue_type else None
    
    def _count_sources_and_sinks(self, md_file: Path) -> Tuple[int, int]:
        """
        計算 markdown 檔案中的 Source 和 Sink 數量
        
        Args:
            md_file: markdown 檔案路徑
            
        Returns:
            Tuple[int, int]: (sources_count, sinks_count)
        """
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            return 0, 0
        
        # 計算 Source: 和 Sink: 的出現次數
        sources_count = len(re.findall(r'^Source:', content, re.MULTILINE))
        sinks_count = len(re.findall(r'^Sink:', content, re.MULTILINE))
        
        return sources_count, sinks_count
    
    def _get_scan_time(self, project_dir: Path) -> Optional[str]:
        """
        取得專案的掃描時間（從目錄修改時間推估）
        
        Args:
            project_dir: 專案目錄
            
        Returns:
            str: 掃描時間字串
        """
        try:
            # 取得目錄的最後修改時間
            import datetime
            timestamp = project_dir.stat().st_mtime
            dt = datetime.datetime.fromtimestamp(timestamp)
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return None
    
    def _get_branch_info(self, project_name: str) -> Dict:
        """
        取得專案的分支資訊
        
        Args:
            project_name: 專案名稱
            
        Returns:
            Dict: 分支資訊
        """
        # 優先從 Pipeline 快取中取得分支資訊（更可靠）
        pipeline_info = self.cache_manager.get_project_pipeline_info(project_name)
        if pipeline_info and "source_branch" in pipeline_info:
            branch_name = pipeline_info["source_branch"].replace("refs/heads/", "")
            return {
                "branch_name": branch_name,
                "pipeline_id": pipeline_info.get("pipeline_id"),
                "last_updated": pipeline_info.get("last_updated")
            }
        
        # 其次從分支快取中取得
        cached_branch_info = self.cache_manager.get_project_branch_info(project_name)
        if cached_branch_info:
            return {
                "branch_name": cached_branch_info.get("branch_name", "未知"),
                "pipeline_id": cached_branch_info.get("pipeline_id"),
                "last_updated": cached_branch_info.get("last_updated")
            }
        
        # 預設值
        return {
            "branch_name": "未知",
            "pipeline_id": None,
            "last_updated": None
        }
    
    def get_summary_statistics(self) -> Dict:
        """
        取得總體統計資料
        
        Returns:
            Dict: 總體統計
        """
        all_results = self.get_project_scan_results()
        
        if not all_results:
            return {
                "total_projects": 0,
                "total_issues": 0,
                "total_sources": 0,
                "total_sinks": 0,
                "issue_types": {}
            }
        
        total_projects = len(all_results)
        total_issues = 0
        total_sources = 0
        total_sinks = 0
        issue_types = defaultdict(int)
        
        for project_data in all_results.values():
            total_issues += project_data["total_issues"]
            total_sources += project_data["total_sources"]
            total_sinks += project_data["total_sinks"]
            
            for issue_type in project_data["issues"].keys():
                issue_types[issue_type] += 1
        
        return {
            "total_projects": total_projects,
            "total_issues": total_issues,
            "total_sources": total_sources,
            "total_sinks": total_sinks,
            "issue_types": dict(issue_types)
        }


def get_scan_results_analyzer() -> ScanResultsAnalyzer:
    """取得掃描結果分析器實例"""
    return ScanResultsAnalyzer()
