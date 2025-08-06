#!/usr/bin/env python3
"""
Azure DevOps Pipeline 觸發腳本

此腳本可以批次觸發多個專案的 Fortify 掃描 Pipeline。
現在使用統一的 YAML 設定檔來管理所有設定。
"""

import os
import sys
import requests
import json
import time
from typing import List, Dict, Optional, Tuple
import argparse

# 添加 src 目錄到 Python 路徑以便 import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from fortify_tool.utils.config_loader import get_config


class FortifyPipelineTrigger:
    def __init__(self):
        """初始化 Pipeline 觸發器，從 YAML 設定檔載入設定"""
        self.config = get_config()
        
        # 從設定檔載入 Azure DevOps 設定
        ado_config = self.config.get_azure_devops_config()
        self.organization = ado_config["organization"]
        self.project = ado_config["project"]
        self.pat = ado_config["personal_access_token"]
        
        if not self.pat:
            print("錯誤：找不到 Azure DevOps PAT。")
            print("請在 config/config.yaml 中設定 azure_devops.personal_access_token")
            print("或設定環境變數 AZURE_DEVOPS_PAT")
            sys.exit(1)
        
        # 從設定檔載入 Pipeline 設定
        pipeline_config = self.config.get_pipeline_config()
        self.branch_priority = pipeline_config["branch_priority"]
        self.naming_pattern = pipeline_config["naming_pattern"]
        
        # API 基礎 URL
        self.base_url = f"https://dev.azure.com/{self.organization}/{self.project}/_apis"
        
        # 設定 HTTP headers
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {self._encode_pat(self.pat)}"
        }
    
    def _encode_pat(self, pat: str) -> str:
        """編碼 PAT 為 Base64 格式"""
        import base64
        return base64.b64encode(f":{pat}".encode()).decode()
    
    def discover_pipelines(self) -> List[Dict]:
        """自動發現所有 Fortify Pipeline"""
        print("🔍 正在搜尋所有可用的 Fortify Pipeline...")
        
        try:
            # 取得所有 Pipeline 定義
            url = f"{self.base_url}/build/definitions?api-version=6.0"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            all_pipelines = response.json().get("value", [])
            fortify_pipelines = []
            
            for pipeline in all_pipelines:
                name = pipeline.get("name", "")
                if "fortify" in name.lower():
                    # 提取專案名稱
                    repo_name = self._extract_repo_name(name)
                    if repo_name:
                        fortify_pipelines.append({
                            "repo_name": repo_name,
                            "pipeline_id": pipeline["id"],
                            "pipeline_name": name,
                            "pipeline_url": f"https://dev.azure.com/{self.organization}/{self.project}/_build?definitionId={pipeline['id']}"
                        })
            
            print(f"✅ 找到 {len(fortify_pipelines)} 個 Fortify Pipeline")
            return fortify_pipelines
            
        except requests.exceptions.RequestException as e:
            print(f"❌ 搜尋 Pipeline 時發生錯誤: {e}")
            return []
    
    def _extract_repo_name(self, pipeline_name: str) -> Optional[str]:
        """從 Pipeline 名稱提取專案名稱"""
        # 假設 Pipeline 命名格式為 "{repo_name}-evergreen-fortify"
        if "-evergreen-fortify" in pipeline_name:
            return pipeline_name.replace("-evergreen-fortify", "")
        return None
    
    def get_available_branches(self, repo_name: str) -> List[str]:
        """取得指定 repository 的可用分支"""
        try:
            url = f"{self.base_url}/git/repositories/{repo_name}/refs?filter=heads/&api-version=6.0"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            refs = response.json().get("value", [])
            branches = [ref["name"].replace("refs/heads/", "") for ref in refs]
            return branches
            
        except requests.exceptions.RequestException:
            return []
    
    def select_branch(self, repo_name: str) -> str:
        """根據優先順序選擇分支"""
        available_branches = self.get_available_branches(repo_name)
        
        for preferred_branch in self.branch_priority:
            if preferred_branch in available_branches:
                return preferred_branch
        
        # 如果沒有找到優先分支，使用第一個 evergreen 分支
        evergreen_branches = [b for b in available_branches if b.startswith("evergreen/")]
        if evergreen_branches:
            return evergreen_branches[0]
        
        # 最後 fallback 到 main
        return "main" if "main" in available_branches else "master"
    
    def trigger_pipeline(self, pipeline_id: int, repo_name: str, branch: str) -> bool:
        """觸發指定的 Pipeline"""
        try:
            url = f"{self.base_url}/build/builds?api-version=6.0"
            
            payload = {
                "definition": {"id": pipeline_id},
                "sourceBranch": f"refs/heads/{branch}",
                "reason": "manual"
            }
            
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            
            build_info = response.json()
            build_id = build_info.get("id")
            build_url = f"https://dev.azure.com/{self.organization}/{self.project}/_build/results?buildId={build_id}"
            
            print(f"  ✅ 成功觸發 Pipeline")
            print(f"     Build ID: {build_id}")
            print(f"     查看進度: {build_url}")
            
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"  ❌ 觸發失敗: {e}")
            return False
    
    def trigger_repos(self, repo_names: List[str]) -> Dict[str, bool]:
        """批次觸發指定專案的 Pipeline"""
        if not repo_names:
            print("❌ 沒有指定要觸發的專案")
            return {}
        
        # 發現所有可用的 Pipeline
        pipelines = self.discover_pipelines()
        pipeline_map = {p["repo_name"]: p for p in pipelines}
        
        results = {}
        
        for repo_name in repo_names:
            print(f"\n🚀 處理專案: {repo_name}")
            
            if repo_name not in pipeline_map:
                print(f"  ❌ 找不到對應的 Fortify Pipeline")
                results[repo_name] = False
                continue
            
            pipeline = pipeline_map[repo_name]
            branch = self.select_branch(repo_name)
            
            print(f"  📋 Pipeline: {pipeline['pipeline_name']}")
            print(f"  🌿 分支: {branch}")
            
            success = self.trigger_pipeline(pipeline["pipeline_id"], repo_name, branch)
            results[repo_name] = success
            
            if success:
                time.sleep(2)  # 避免過於頻繁的 API 呼叫
        
        return results
    
    def list_pipelines(self):
        """列出所有可用的 Fortify Pipeline"""
        pipelines = self.discover_pipelines()
        
        if not pipelines:
            print("❌ 沒有找到任何 Fortify Pipeline")
            return
        
        print(f"\n📋 找到 {len(pipelines)} 個可用的 Fortify Pipeline:")
        print("-" * 80)
        
        for pipeline in pipelines:
            print(f"專案: {pipeline['repo_name']}")
            print(f"Pipeline: {pipeline['pipeline_name']}")
            print(f"URL: {pipeline['pipeline_url']}")
            print("-" * 40)
    
    def trigger_all(self) -> Dict[str, bool]:
        """觸發所有可用專案的 Pipeline"""
        pipelines = self.discover_pipelines()
        repo_names = [p["repo_name"] for p in pipelines]
        
        if not repo_names:
            print("❌ 沒有找到任何可用的 Fortify Pipeline")
            return {}
        
        print(f"🚀 準備觸發 {len(repo_names)} 個專案的 Pipeline")
        return self.trigger_repos(repo_names)


def main():
    parser = argparse.ArgumentParser(description="Azure DevOps Fortify Pipeline 觸發工具")
    parser.add_argument("--list", action="store_true", help="列出所有可用的 Fortify Pipeline")
    parser.add_argument("--repo", nargs="+", help="指定要觸發的專案名稱")
    parser.add_argument("--all", action="store_true", help="觸發所有可用專案的 Pipeline")
    
    args = parser.parse_args()
    
    print("--- 開始執行 Azure DevOps Pipeline 觸發腳本 ---")
    
    trigger = FortifyPipelineTrigger()
    
    if args.list:
        trigger.list_pipelines()
    elif args.all:
        results = trigger.trigger_all()
        
        # 顯示執行摘要
        print(f"\n📊 執行摘要:")
        success_count = sum(1 for success in results.values() if success)
        total_count = len(results)
        print(f"成功: {success_count}/{total_count}")
        
        if success_count < total_count:
            failed_repos = [repo for repo, success in results.items() if not success]
            print(f"失敗的專案: {', '.join(failed_repos)}")
    
    elif args.repo:
        results = trigger.trigger_repos(args.repo)
        
        # 顯示執行摘要
        print(f"\n📊 執行摘要:")
        success_count = sum(1 for success in results.values() if success)
        total_count = len(results)
        print(f"成功: {success_count}/{total_count}")
        
        if success_count < total_count:
            failed_repos = [repo for repo, success in results.items() if not success]
            print(f"失敗的專案: {', '.join(failed_repos)}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
