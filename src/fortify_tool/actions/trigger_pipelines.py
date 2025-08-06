"""
Fortify Pipeline 觸發工具

提供快速批次觸發 Azure DevOps Fortify Pipeline 的功能，支援：
- 自動發現可用的 Fortify Pipeline
- 批次或單一專案觸發
- 即時狀態監控
- 詳細的執行報告
"""

import os
import requests
import json
import time
from typing import List, Dict, Optional, Tuple
from ..utils.config_loader import get_config
import argparse


class FortifyPipelineTrigger:
    def __init__(self):
        """初始化 Pipeline 觸發器，從 YAML 設定檔載入設定"""
        self.config = get_config()
        
        # 從設定檔載入 Azure DevOps 設定
        ado_config = self.config.get_azure_devops_config()
        self.organization = ado_config["organization"]
        self.project = ado_config["project"]
        self.ado_pat = ado_config["personal_access_token"]
        
        if not self.ado_pat:
            print("錯誤：找不到 Azure DevOps PAT。")
            print("請在 config/config.yaml 中設定 azure_devops.personal_access_token")
            print("或設定環境變數 AZURE_DEVOPS_PAT")
            raise ValueError("找不到 Azure DevOps PAT")
        
        # 從設定檔載入 Pipeline 設定
        pipeline_config = self.config.get_pipeline_config()
        self.branch_priority = pipeline_config["branch_priority"]
        self.naming_pattern = pipeline_config["naming_pattern"]
        
        # API 基礎 URL
        self.base_url = f"https://dev.azure.com/{self.organization}/{self.project}/_apis"
        
        # 設定 HTTP headers
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {self._encode_pat(self.ado_pat)}"
        }
    
    def _encode_pat(self, pat: str) -> str:
        """編碼 Azure DevOps PAT"""
        import base64
        return base64.b64encode(f":{pat}".encode()).decode()
    
    def find_fortify_branch(self, repo_name: str) -> Optional[str]:
        """
        動態尋找 evergreen 路徑下名稱帶有 fortify 的分支
        
        Args:
            repo_name: Repository 名稱
            
        Returns:
            找到的 Fortify 分支名稱，如果沒找到則返回 None
        """
        # 先取得 Repository 資訊
        url = f"{self.base_url}/git/repositories?api-version=7.1-preview.1"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            repos = response.json().get("value", [])
            target_repo = None
            
            for repo in repos:
                if repo.get("name") == repo_name:
                    target_repo = repo
                    break
            
            if not target_repo:
                print(f"⚠️  找不到 Repository '{repo_name}'")
                return None
            
            repo_id = target_repo.get("id")
            
            # 取得分支清單
            branches_url = f"{self.base_url}/git/repositories/{repo_id}/refs?filter=heads/evergreen/&api-version=7.1-preview.1"
            
            branches_response = requests.get(branches_url, headers=self.headers)
            branches_response.raise_for_status()
            
            branches = branches_response.json().get("value", [])
            
            # 尋找 evergreen 路徑下帶有 fortify 的分支
            fortify_branches = []
            for branch in branches:
                branch_name = branch.get("name", "").replace("refs/heads/", "")
                if "evergreen" in branch_name and "fortify" in branch_name.lower():
                    fortify_branches.append(branch_name)
            
            if fortify_branches:
                # 優先選擇 evergreen/fortify，否則選擇第一個找到的
                if "evergreen/fortify" in fortify_branches:
                    return "evergreen/fortify"
                else:
                    return fortify_branches[0]
            
            # 如果沒找到 fortify 分支，嘗試使用 evergreen/main 作為備選
            for branch in branches:
                branch_name = branch.get("name", "").replace("refs/heads/", "")
                if branch_name == "evergreen/main":
                    print(f"⚠️  未找到 Fortify 分支，使用備選分支: evergreen/main")
                    return "evergreen/main"
            
            return None
            
        except Exception as e:
            print(f"❌ 尋找 Fortify 分支時發生錯誤: {e}")
            return None
    
    def discover_fortify_pipelines(self) -> Dict[str, int]:
        """自動發現所有可用的 Fortify Pipeline"""
        url = f"{self.base_url}/pipelines?api-version=7.1-preview.1"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            pipelines = response.json().get("value", [])
            fortify_pipelines = {}
            
            for pipeline in pipelines:
                name = pipeline.get("name", "")
                if "-evergreen-fortify" in name:
                    repo_name = name.replace("-evergreen-fortify", "")
                    fortify_pipelines[repo_name] = pipeline.get("id")
            
            return fortify_pipelines
            
        except requests.exceptions.RequestException as e:
            print(f"❌ 無法取得 Pipeline 清單: {e}")
            return {}
    
    def find_pipeline_id(self, repo_name: str) -> Optional[int]:
        """根據 Repo 名稱尋找對應的 Pipeline ID"""
        expected_pipeline_name = f"{repo_name}-evergreen-fortify"
        url = f"{self.base_url}/pipelines?api-version=7.1-preview.1"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            pipelines = response.json().get("value", [])
            for pipeline in pipelines:
                if pipeline.get("name") == expected_pipeline_name:
                    return pipeline.get("id")
            
            return None
            
        except requests.exceptions.RequestException as e:
            print(f"❌ 搜尋 Pipeline '{expected_pipeline_name}' 時發生錯誤: {e}")
            return None
    
    def trigger_pipeline_run(self, pipeline_id: int, repo_name: str, branch_name: str = None) -> Tuple[bool, Optional[str]]:
        """觸發指定的 Pipeline 並回傳執行結果"""
        # 如果沒有指定分支，使用動態尋找的分支
        if not branch_name:
            branch_name = self.find_fortify_branch(repo_name)
            if not branch_name:
                return False, f"找不到適合的 Fortify 分支"
        
        url = f"{self.base_url}/pipelines/{pipeline_id}/runs?api-version=7.1-preview.1"
        
        body = {
            "resources": {
                "repositories": {
                    "self": {
                        "refName": f"refs/heads/{branch_name}"
                    }
                }
            }
        }
        
        print(f"   使用分支: {branch_name}")
        
        try:
            response = requests.post(url, headers=self.headers, data=json.dumps(body))
            response.raise_for_status()
            
            response_data = response.json()
            run_url = response_data.get("_links", {}).get("web", {}).get("href")
            run_id = response_data.get("id")
            
            return True, run_url
            
        except requests.exceptions.HTTPError as err:
            error_msg = f"HTTP {err.response.status_code}: {err.response.text}"
            return False, error_msg
        except Exception as e:
            return False, str(e)
    
    def get_pipeline_status(self, pipeline_id: int, run_id: int) -> Optional[str]:
        """取得 Pipeline 執行狀態"""
        url = f"{self.base_url}/pipelines/{pipeline_id}/runs/{run_id}?api-version=7.1-preview.1"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            run_data = response.json()
            return run_data.get("state")
            
        except requests.exceptions.RequestException:
            return None
    
    def list_available_pipelines(self):
        """列出所有可用的 Fortify Pipeline"""
        print("🔍 正在搜尋可用的 Fortify Pipeline...")
        pipelines = self.discover_fortify_pipelines()
        
        if not pipelines:
            print("❌ 未找到任何 Fortify Pipeline")
            return
        
        print(f"\n📋 找到 {len(pipelines)} 個可用的 Fortify Pipeline:")
        print("-" * 50)
        for repo_name, pipeline_id in sorted(pipelines.items()):
            print(f"  • {repo_name:<20} (ID: {pipeline_id})")
        print("-" * 50)
    
    def trigger_single_pipeline(self, repo_name: str):
        """觸發單一專案的 Fortify Pipeline"""
        print(f"🚀 正在為專案 '{repo_name}' 觸發 Fortify Pipeline...")
        
        pipeline_id = self.find_pipeline_id(repo_name)
        if not pipeline_id:
            print(f"❌ 找不到專案 '{repo_name}' 的 Fortify Pipeline")
            print(f"   預期 Pipeline 名稱: {repo_name}-evergreen-fortify")
            return False
        
        branch_name = self.find_fortify_branch(repo_name)
        
        success, result = self.trigger_pipeline_run(pipeline_id, repo_name, branch_name)
        
        if success:
            print(f"✅ 成功觸發！Pipeline 已開始執行")
            print(f"   查看進度: {result}")
            return True
        else:
            print(f"❌ 觸發失敗: {result}")
            return False
    
    def trigger_multiple_pipelines(self, repo_names: List[str]):
        """批次觸發多個專案的 Fortify Pipeline"""
        print(f"🚀 正在批次觸發 {len(repo_names)} 個專案的 Fortify Pipeline...")
        print("=" * 60)
        
        results = []
        for i, repo_name in enumerate(repo_names, 1):
            print(f"\n[{i}/{len(repo_names)}] 處理專案: {repo_name}")
            print("-" * 40)
            
            success = self.trigger_single_pipeline(repo_name)
            results.append((repo_name, success))
            
            # 避免過於頻繁的 API 呼叫
            if i < len(repo_names):
                time.sleep(1)
        
        # 顯示執行摘要
        print("\n" + "=" * 60)
        print("📊 執行摘要:")
        successful = sum(1 for _, success in results if success)
        failed = len(results) - successful
        
        print(f"   ✅ 成功: {successful} 個")
        print(f"   ❌ 失敗: {failed} 個")
        
        if failed > 0:
            print("\n❌ 失敗的專案:")
            for repo_name, success in results:
                if not success:
                    print(f"   • {repo_name}")
        
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Fortify Pipeline 觸發工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例:
  python trigger_pipelines.py --list                    # 列出所有可用的 Pipeline
  python trigger_pipelines.py --repo imc                # 觸發單一專案
  python trigger_pipelines.py --repo imc ina iim        # 觸發多個專案
  python trigger_pipelines.py --all                     # 觸發所有可用的 Pipeline
        """
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="列出所有可用的 Fortify Pipeline")
    group.add_argument("--repo", nargs="+", help="指定要觸發的專案名稱")
    group.add_argument("--all", action="store_true", help="觸發所有可用的 Fortify Pipeline")
    
    args = parser.parse_args()
    
    try:
        trigger = FortifyPipelineTrigger()
        
        if args.list:
            trigger.list_available_pipelines()
        
        elif args.repo:
            if len(args.repo) == 1:
                trigger.trigger_single_pipeline(args.repo[0])
            else:
                trigger.trigger_multiple_pipelines(args.repo)
        
        elif args.all:
            pipelines = trigger.discover_fortify_pipelines()
            if pipelines:
                repo_names = list(pipelines.keys())
                trigger.trigger_multiple_pipelines(repo_names)
            else:
                print("❌ 未找到任何可用的 Fortify Pipeline")
    
    except ValueError as e:
        print(f"❌ 設定錯誤: {e}")
    except KeyboardInterrupt:
        print("\n⚠️  使用者中斷執行")
    except Exception as e:
        print(f"❌ 發生未預期的錯誤: {e}")


if __name__ == "__main__":
    main()
