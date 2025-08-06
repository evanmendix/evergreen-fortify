#!/usr/bin/env python3
"""
測試 Pipeline 發現和分支選擇功能

此腳本用於驗證：
1. Azure DevOps API 連線和權限
2. Pipeline 自動發現功能
3. 分支選擇邏輯
4. 實際的 Pipeline 命名規則
"""

import sys
import os
import requests

# 添加 src 目錄到 Python 路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from fortify_tool.utils.config_loader import get_config


def test_config_loading():
    """測試設定檔載入"""
    print("🔧 測試設定檔載入...")
    
    try:
        config = get_config()
        ado_config = config.get_azure_devops_config()
        
        print(f"  組織: {ado_config['organization']}")
        print(f"  專案: {ado_config['project']}")
        print(f"  PAT 狀態: {'已設定' if ado_config['personal_access_token'] else '未設定'}")
        
        if not ado_config['personal_access_token']:
            print("❌ 找不到 Azure DevOps PAT")
            print("請在 config/config.yaml 中設定 azure_devops.personal_access_token")
            return False
            
        print("✅ 設定檔載入成功")
        return True
        
    except Exception as e:
        print(f"❌ 設定檔載入失敗: {e}")
        return False


class PipelineDiscoveryTest:
    def __init__(self):
        """初始化測試類別"""
        config = get_config()
        ado_config = config.get_azure_devops_config()
        
        self.organization = ado_config['organization']
        self.project = ado_config['project']
        self.ado_pat = ado_config['personal_access_token']
        
        if not self.ado_pat:
            print("❌ 找不到 Azure DevOps PAT")
            print("請在 config/config.yaml 中設定 azure_devops.personal_access_token")
            return
        
        print(f"✅ 找到 PAT，組織: {self.organization}, 專案: {self.project}")
    
    def get_auth_headers(self):
        """建立認證標頭"""
        import base64
        credentials = base64.b64encode(f":{self.ado_pat}".encode()).decode()
        return {
            "Content-Type": "application/json",
            "Authorization": f"Basic {credentials}",
        }
    
    def test_api_connection(self):
        """測試 API 連線和權限"""
        print("\n🔍 測試 Azure DevOps API 連線...")
        
        url = f"https://dev.azure.com/{self.organization}/{self.project}/_apis/pipelines?api-version=7.1-preview.1"
        
        try:
            response = requests.get(url, headers=self.get_auth_headers())
            print(f"   HTTP 狀態碼: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ API 連線成功")
                return True
            elif response.status_code == 401:
                print("❌ 認證失敗 - 請檢查 PAT 是否正確")
                return False
            elif response.status_code == 403:
                print("❌ 權限不足 - 請確認 PAT 有 Build (read and execute) 權限")
                return False
            else:
                print(f"❌ API 呼叫失敗: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 連線錯誤: {e}")
            return False
    
    def discover_all_pipelines(self):
        """發現所有 Pipeline 並分析命名規則"""
        print("\n🔍 發現所有可用的 Pipeline...")
        
        url = f"https://dev.azure.com/{self.organization}/{self.project}/_apis/pipelines?api-version=7.1-preview.1"
        
        try:
            response = requests.get(url, headers=self.get_auth_headers())
            response.raise_for_status()
            
            pipelines = response.json().get("value", [])
            print(f"   找到 {len(pipelines)} 個 Pipeline")
            
            # 分析所有 Pipeline
            fortify_pipelines = []
            other_pipelines = []
            
            for pipeline in pipelines:
                name = pipeline.get("name", "")
                pipeline_id = pipeline.get("id")
                
                if "fortify" in name.lower():
                    fortify_pipelines.append((name, pipeline_id))
                else:
                    other_pipelines.append((name, pipeline_id))
            
            # 顯示 Fortify 相關的 Pipeline
            if fortify_pipelines:
                print(f"\n✅ 找到 {len(fortify_pipelines)} 個 Fortify 相關的 Pipeline:")
                for name, pid in fortify_pipelines:
                    print(f"   • {name} (ID: {pid})")
            else:
                print("\n❌ 未找到任何 Fortify 相關的 Pipeline")
            
            # 顯示其他 Pipeline（前10個）
            if other_pipelines:
                print(f"\n📋 其他 Pipeline (前10個):")
                for name, pid in other_pipelines[:10]:
                    print(f"   • {name} (ID: {pid})")
                if len(other_pipelines) > 10:
                    print(f"   ... 還有 {len(other_pipelines) - 10} 個")
            
            return fortify_pipelines
            
        except Exception as e:
            print(f"❌ 發現 Pipeline 時發生錯誤: {e}")
            return []
    
    def test_pipeline_details(self, pipeline_id, pipeline_name):
        """測試特定 Pipeline 的詳細資訊"""
        print(f"\n🔍 檢查 Pipeline '{pipeline_name}' 的詳細資訊...")
        
        url = f"https://dev.azure.com/{self.organization}/{self.project}/_apis/pipelines/{pipeline_id}?api-version=7.1-preview.1"
        
        try:
            response = requests.get(url, headers=self.get_auth_headers())
            response.raise_for_status()
            
            pipeline_data = response.json()
            
            print(f"   Pipeline ID: {pipeline_data.get('id')}")
            print(f"   Pipeline 名稱: {pipeline_data.get('name')}")
            print(f"   資料夾: {pipeline_data.get('folder')}")
            
            # 檢查 repository 資訊
            if 'configuration' in pipeline_data:
                config = pipeline_data['configuration']
                if 'repository' in config:
                    repo = config['repository']
                    print(f"   Repository: {repo.get('name')}")
                    print(f"   Repository ID: {repo.get('id')}")
                    print(f"   預設分支: {repo.get('defaultBranch')}")
            
            return True
            
        except Exception as e:
            print(f"❌ 取得 Pipeline 詳細資訊時發生錯誤: {e}")
            return False
    
    def test_branch_availability(self, repo_name):
        """測試指定 Repository 的可用分支"""
        print(f"\n🔍 檢查 {repo_name} Repository 的可用分支...")
        
        # 先取得 Repository 資訊
        url = f"https://dev.azure.com/{self.organization}/{self.project}/_apis/git/repositories?api-version=7.1-preview.1"
        
        try:
            response = requests.get(url, headers=self.get_auth_headers())
            response.raise_for_status()
            
            repos = response.json().get("value", [])
            target_repo = None
            
            for repo in repos:
                if repo.get("name") == repo_name:
                    target_repo = repo
                    break
            
            if not target_repo:
                print(f"❌ 找不到 Repository '{repo_name}'")
                return False
            
            repo_id = target_repo.get("id")
            print(f"   Repository ID: {repo_id}")
            
            # 取得分支清單
            branches_url = f"https://dev.azure.com/{self.organization}/{self.project}/_apis/git/repositories/{repo_id}/refs?filter=heads/&api-version=7.1-preview.1"
            
            branches_response = requests.get(branches_url, headers=self.get_auth_headers())
            branches_response.raise_for_status()
            
            branches = branches_response.json().get("value", [])
            
            print(f"   找到 {len(branches)} 個分支:")
            
            evergreen_branches = []
            other_branches = []
            
            for branch in branches:
                branch_name = branch.get("name", "").replace("refs/heads/", "")
                if "evergreen" in branch_name:
                    evergreen_branches.append(branch_name)
                else:
                    other_branches.append(branch_name)
            
            if evergreen_branches:
                print("   📂 Evergreen 分支:")
                for branch in evergreen_branches:
                    print(f"     • {branch}")
            
            print("   📂 其他分支 (前5個):")
            for branch in other_branches[:5]:
                print(f"     • {branch}")
            
            # 檢查目標分支是否存在
            target_branches = ["evergreen/fortify"]
            fortify_branch_found = False
            
            for target in target_branches:
                if target in evergreen_branches:
                    print(f"   ✅ 找到目標分支: {target}")
                    fortify_branch_found = True
                else:
                    print(f"   ❌ 未找到目標分支: {target}")
            
            # 檢查是否有其他包含 fortify 的 evergreen 分支
            other_fortify_branches = [b for b in evergreen_branches if "fortify" in b.lower() and b != "evergreen/fortify"]
            if other_fortify_branches:
                print("   📂 其他包含 fortify 的 evergreen 分支:")
                for branch in other_fortify_branches:
                    print(f"     • {branch}")
                    fortify_branch_found = True
            
            # 檢查備選分支
            if "evergreen/main" in evergreen_branches:
                print(f"   ℹ️  備選分支可用: evergreen/main")
            
            if fortify_branch_found:
                print("   ✅ 分支選擇策略: 可以找到適合的 Fortify 分支")
            else:
                print("   ⚠️  分支選擇策略: 需要使用備選分支 evergreen/main")
            
            return True
            
        except Exception as e:
            print(f"❌ 檢查分支時發生錯誤: {e}")
            return False
    
    def run_full_test(self):
        """執行完整測試"""
        print("=" * 60)
        print("🧪 Azure DevOps Pipeline 發現與驗證測試")
        print("=" * 60)
        
        if not self.ado_pat:
            return
        
        # 1. 測試 API 連線
        if not self.test_api_connection():
            print("\n❌ API 連線測試失敗，停止後續測試")
            return
        
        # 2. 發現所有 Pipeline
        fortify_pipelines = self.discover_all_pipelines()
        
        if not fortify_pipelines:
            print("\n❌ 未找到 Fortify Pipeline，停止後續測試")
            return
        
        # 3. 測試第一個 Fortify Pipeline 的詳細資訊
        first_pipeline = fortify_pipelines[0]
        pipeline_name, pipeline_id = first_pipeline
        
        self.test_pipeline_details(pipeline_id, pipeline_name)
        
        # 4. 嘗試從 Pipeline 名稱推導 Repository 名稱並測試分支
        if "-evergreen-fortify" in pipeline_name:
            repo_name = pipeline_name.replace("-evergreen-fortify", "")
            print(f"\n🔍 從 Pipeline 名稱推導的 Repository: {repo_name}")
            self.test_branch_availability(repo_name)
        
        print("\n" + "=" * 60)
        print("🏁 測試完成")
        print("=" * 60)


if __name__ == "__main__":
    test = PipelineDiscoveryTest()
    test.run_full_test()
