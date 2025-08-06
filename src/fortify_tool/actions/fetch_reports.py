import os
import requests
from requests.auth import HTTPBasicAuth
import json
from datetime import datetime, timezone, timedelta
from ..utils.get_filepath import PROJECT_CACHE_DIR, REPORTS_DIR
from ..utils.config_loader import get_config

# 從設定檔載入 Azure DevOps 設定
config = get_config()
ado_config = config.get_azure_devops_config()
organization = ado_config["organization"]
project = ado_config["project"]
pat = ado_config["personal_access_token"]

if not pat:
    raise ValueError("找不到 Azure DevOps PAT。請在 config/config.yaml 中設定 azure_devops.personal_access_token")

headers = {"Accept": "application/json"}
auth = HTTPBasicAuth('', pat)

os.makedirs(PROJECT_CACHE_DIR, exist_ok=True)
STATE_FILE = PROJECT_CACHE_DIR / 'fortify_download_state.json'


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_first_value_id(url):
    resp = requests.get(url, auth=auth, headers=headers)
    if resp.status_code == 200 and resp.json().get("count", 0) > 0:
        return resp.json()["value"][0]["id"]
    return None


def get_fortify_pipeline_id(repo):
    """根據 repo 名稱尋找對應的 Fortify Pipeline ID"""
    expected_pipeline_name = f"{repo}-evergreen-fortify"
    url = f"https://dev.azure.com/{organization}/{project}/_apis/pipelines?api-version=7.1-preview.1"
    
    try:
        response = requests.get(url, auth=auth, headers=headers)
        response.raise_for_status()
        
        pipelines = response.json().get("value", [])
        for pipeline in pipelines:
            if pipeline.get("name") == expected_pipeline_name:
                return pipeline.get("id")
        
        return None
        
    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] 搜尋 Pipeline '{expected_pipeline_name}' 時發生錯誤: {e}")
        return None


def get_latest_build_info(definition_id, branch_names=None):
    """
    獲取指定 pipeline definition 在多個分支的最新成功 build 資訊
    
    Args:
        definition_id: Pipeline definition ID
        branch_names: 要查找的分支名稱列表，如果為 None 則動態查找 Fortify 分支
    
    Returns:
        tuple: (build_id, result, finish_time)
    """
    # 先嘗試查找所有分支的最新建置（不限制分支）
    url = f"https://dev.azure.com/{organization}/{project}/_apis/build/builds?definitions={definition_id}&statusFilter=completed&resultFilter=succeeded,partiallySucceeded&$top=20&api-version=7.0"
    
    try:
        resp = requests.get(url, auth=auth, headers=headers)
        resp.raise_for_status()
        
        if resp.json().get("count", 0) > 0:
            builds = resp.json()["value"]
            
            if branch_names is None:
                # 動態查找 Fortify 相關分支（與 trigger_pipelines.py 邏輯一致）
                fortify_branches = []
                other_evergreen_branches = []
                
                for build in builds:
                    build_branch = build.get("sourceBranch", "").replace("refs/heads/", "")
                    if "evergreen" in build_branch:
                        if "fortify" in build_branch.lower():
                            if build_branch not in fortify_branches:
                                fortify_branches.append(build_branch)
                        elif build_branch not in other_evergreen_branches:
                            other_evergreen_branches.append(build_branch)
                
                # 設定分支優先順序：先 Fortify 分支，再其他 evergreen 分支
                branch_names = fortify_branches + other_evergreen_branches
                print(f"  [INFO] 動態發現分支: Fortify={fortify_branches}, 其他={other_evergreen_branches}")
            
            # 按分支優先順序查找
            for branch_name in branch_names:
                for build in builds:
                    build_branch = build.get("sourceBranch", "").replace("refs/heads/", "")
                    if build_branch == branch_name:
                        print(f"  [INFO] 找到建置於分支 '{branch_name}': Build ID {build.get('id')}, 結果: {build.get('result')}")
                        return build.get("id"), build.get("result"), build.get("finishTime")
            
            # 如果沒找到指定分支，使用最新的建置
            latest_build = builds[0]
            build_branch = latest_build.get("sourceBranch", "").replace("refs/heads/", "")
            print(f"  [INFO] 使用最新建置於分支 '{build_branch}': Build ID {latest_build.get('id')}, 結果: {latest_build.get('result')}")
            return latest_build.get("id"), latest_build.get("result"), latest_build.get("finishTime")
            
    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] 查詢建置資訊時發生錯誤: {e}")
    
    return None, None, None


def get_pdf_url_from_artifact(build_id, repo_name, pdf_keyword="fortify-result.pdf"):
    artifact_url = f"https://dev.azure.com/{organization}/{project}/_apis/build/builds/{build_id}/artifacts?api-version=7.0"
    resp = requests.get(artifact_url, auth=auth, headers=headers)
    if resp.status_code == 200:
        for artifact in resp.json().get("value", []):
            if artifact.get("name", "").lower() == "fortify":
                container_id = artifact.get("resource", {}).get("data")
                if not container_id:
                    continue
                parts = container_id.strip("#/ ").split("/", 1)
                if len(parts) == 2:
                    cid, folder = parts
                    list_url = f"https://dev.azure.com/{organization}/_apis/resources/Containers/{cid}?itemPath={folder}&includeDownloadTickets=true&api-version=7.0-preview"
                    files_resp = requests.get(list_url, auth=auth, headers=headers)
                    if files_resp.status_code == 200:
                        files_data = files_resp.json()
                        files = files_data.get("value", [])
                        for f in files:
                            path = f.get("path", "")
                            if f.get("itemType") == "file" and f"fia-sdt-{repo_name.lower()}-fortify-result" in path.lower() and path.endswith(".pdf"):
                                return f.get("contentLocation")
    return None


def download_pdf(url, output_path):
    try:
        response = requests.get(url, auth=auth, stream=True)
        response.raise_for_status()
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"  [SUCCESS] 已成功下載 PDF 至: {output_path}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] 下載 PDF 失敗: {e}")
        return False


def cleanup_old_pdf(repo_name, current_output_dir):
    """
    清理其他分類目錄中的同名 PDF 檔案，避免專案狀態變更時產生重複檔案。
    """
    base_dir = REPORTS_DIR / '完整Fortify報告'
    fixed_dir = os.path.join(base_dir, '已修復專案')
    unfixed_dir = os.path.join(base_dir, '待修復專案')
    
    file_name = f"{repo_name}-fortify-result.pdf"
    
    # 檢查需要清理的目錄（除了當前要存放的目錄）
    dirs_to_check = []
    if current_output_dir != fixed_dir:
        dirs_to_check.append(fixed_dir)
    if current_output_dir != unfixed_dir:
        dirs_to_check.append(unfixed_dir)
    
    for check_dir in dirs_to_check:
        old_file_path = os.path.join(check_dir, file_name)
        if os.path.exists(old_file_path):
            try:
                os.remove(old_file_path)
                print(f"  [CLEANUP] 已清理舊檔案: {old_file_path}")
            except OSError as e:
                print(f"  [WARN] 清理舊檔案失敗 {old_file_path}: {e}")


def fetch_reports():
    base_dir = REPORTS_DIR / '完整Fortify報告'
    fixed_dir = os.path.join(base_dir, '已修復專案')
    unfixed_dir = os.path.join(base_dir, '待修復專案')
    os.makedirs(fixed_dir, exist_ok=True)
    os.makedirs(unfixed_dir, exist_ok=True)
    print(f"報告將分類下載至: {os.path.abspath(base_dir)}")

    state = load_state()
    # 只取得負責專案
    config = get_config()
    repos = config.get_repos("main")
    print(f"共 {len(repos)} 個負責專案，開始查詢 Fortify PDF 下載連結...")
    for repo_original in repos:
        repo = repo_original.lower()
        print(f"--- 正在處理 repo: {repo} (原始: {repo_original}) ---")
        pipeline_id = get_fortify_pipeline_id(repo)
        if pipeline_id:
            latest_build_id, result, finish_time_str = get_latest_build_info(pipeline_id)
            if not latest_build_id:
                print(f"  [INFO] 專案 '{repo}' 沒有成功的建置紀錄。")
                continue

            repo_name = repo
            last_downloaded_build = state.get(repo_name)

            finish_time_local_str = ""
            if finish_time_str:
                finish_time = datetime.fromisoformat(finish_time_str.replace('Z', '+00:00'))
                finish_time_local = finish_time.astimezone(timezone(timedelta(hours=8)))
                finish_time_local_str = finish_time_local.strftime('%Y-%m-%d %H:%M:%S %Z')

            if str(latest_build_id) == str(last_downloaded_build):
                print(f"  [SKIP] {repo_name}: build id 未變動({latest_build_id})。")
                if finish_time_local_str:
                    print(f"    -> 當前版本完成時間: {finish_time_local_str}")
                continue

            print(f"  [UPDATE] 發現新版本 (Build ID: {latest_build_id})，準備下載...")
            if finish_time_local_str:
                print(f"    -> Pipeline 完成時間: {finish_time_local_str}")

            if result == 'succeeded':
                output_dir = fixed_dir
                print(f"  [INFO] {repo}: Build ({latest_build_id}) 完全成功，歸類為『已修復專案』。")
            elif result == 'partiallySucceeded':
                output_dir = unfixed_dir
                print(f"  [INFO] {repo}: Build ({latest_build_id}) 部分成功，歸類為『待修復專案』。")
            else:
                print(f"  [WARN] {repo}: Build ({latest_build_id}) 狀態為 '{result}'，跳過處理。")
                continue

            pdf_url = get_pdf_url_from_artifact(latest_build_id, repo_name)
            if pdf_url:
                print(f"  [INFO] 找到 PDF 下載連結...")
                file_name = f"{repo}-fortify-result.pdf"
                output_path = os.path.join(output_dir, file_name)
                
                # 在下載前清理其他目錄中的舊檔案
                cleanup_old_pdf(repo, output_dir)
                
                if download_pdf(pdf_url, output_path):
                    state[repo_name] = latest_build_id
                    save_state(state)
                    print(f"  [INFO] 已更新 {repo_name} 的狀態到 {STATE_FILE}")
            else:
                print(f"  [WARN] {repo}: 找不到 Fortify PDF")
        else:
            print(f"  [WARN] {repo}: 沒有對應的 Fortify pipeline")

    print(f"\n[INFO] 所有負責專案處理完畢。")
