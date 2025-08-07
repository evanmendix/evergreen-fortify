import os
import shutil
import subprocess
import time
from pathlib import Path
from ..utils.config_loader import get_config
from ..utils.get_filepath import PROJECT_ROOT

# 從設定檔載入 Azure DevOps 設定
config = get_config()
ado_config = config.get_azure_devops_config()
organization = ado_config["organization"]
project = ado_config["project"]
pat = ado_config["personal_access_token"]

if not pat:
    raise ValueError("找不到 Azure DevOps PAT。請在 config/config.yaml 中設定 azure_devops.personal_access_token")

# 專案資料目錄
PROJECTS_DIR = PROJECT_ROOT / "專案資料"


def run_git_command(command, cwd=None, check=True):
    """
    執行 Git 命令並回傳結果
    """
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            capture_output=True,
            text=True,
            check=check
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.CalledProcessError as e:
        return False, e.stdout.strip() if e.stdout else "", e.stderr.strip() if e.stderr else str(e)


def get_repo_url(repo_name):
    """
    根據專案名稱產生 Azure DevOps Git URL
    """
    return f"https://{pat}@dev.azure.com/{organization}/{project}/_git/{repo_name}"


def ensure_branch_exists(repo_path, branch_name, base_branch="evergreen/main"):
    """
    確保指定分支存在，如果不存在則從 base_branch 建立
    """
    print(f"    -> 檢查分支 '{branch_name}' 是否存在...")
    
    # 先取得所有遠端分支
    success, stdout, stderr = run_git_command("git fetch --all", cwd=repo_path)
    if not success:
        print(f"    [WARN] 取得遠端分支失敗: {stderr}")
    
    # 檢查遠端是否有目標分支
    success, stdout, stderr = run_git_command(f"git ls-remote --heads origin {branch_name}", cwd=repo_path)
    
    if success and stdout.strip():
        # 遠端有此分支，切換到此分支
        print(f"    -> 遠端分支 '{branch_name}' 存在，切換中...")
        success, stdout, stderr = run_git_command(f"git checkout -B {branch_name} origin/{branch_name}", cwd=repo_path)
        if success:
            print(f"    [SUCCESS] 已切換到分支 '{branch_name}'")
            return True
        else:
            print(f"    [ERROR] 切換到分支 '{branch_name}' 失敗: {stderr}")
            return False
    else:
        # 遠端沒有此分支，從 base_branch 建立
        print(f"    -> 遠端分支 '{branch_name}' 不存在，從 '{base_branch}' 建立...")
        
        # 先確保 base_branch 存在並是最新的
        success, stdout, stderr = run_git_command(f"git checkout -B {base_branch} origin/{base_branch}", cwd=repo_path)
        if not success:
            print(f"    [ERROR] 切換到基礎分支 '{base_branch}' 失敗: {stderr}")
            return False
        
        # 從 base_branch 建立新分支
        success, stdout, stderr = run_git_command(f"git checkout -b {branch_name}", cwd=repo_path)
        if success:
            print(f"    [SUCCESS] 已從 '{base_branch}' 建立並切換到分支 '{branch_name}'")
            
            # 推送新分支到遠端
            success, stdout, stderr = run_git_command(f"git push -u origin {branch_name}", cwd=repo_path)
            if success:
                print(f"    [SUCCESS] 已推送新分支 '{branch_name}' 到遠端")
            else:
                print(f"    [WARN] 推送新分支失敗: {stderr}")
            return True
        else:
            print(f"    [ERROR] 建立分支 '{branch_name}' 失敗: {stderr}")
            return False


def fix_directory_permissions(directory_path):
    """
    修正目錄權限，確保目標使用者可以正常存取
    """
    try:
        # 優先使用環境變數指定的使用者
        target_user = os.getenv('FORTIFY_TARGET_USER')
        
        if not target_user:
            # 嘗試多種方式偵測實際使用者
            # 方法1: 檢查 USERPROFILE 路徑
            user_profile = os.getenv('USERPROFILE', '')
            if user_profile and '\\Users\\' in user_profile:
                import re
                match = re.search(r'\\Users\\([^\\]+)', user_profile)
                if match:
                    potential_user = match.group(1)
                    if potential_user.lower() not in ['administrator', 'admin', 'public']:
                        target_user = potential_user
            
            # 方法2: 檢查當前工作目錄是否在某個使用者目錄下
            if not target_user:
                current_dir = os.getcwd()
                if '\\Users\\' in current_dir:
                    match = re.search(r'\\Users\\([^\\]+)', current_dir)
                    if match:
                        potential_user = match.group(1)
                        if potential_user.lower() not in ['administrator', 'admin', 'public']:
                            target_user = potential_user
            
            # 方法3: 檢查專案目錄的父目錄結構
            if not target_user:
                project_path = str(PROJECT_ROOT)
                if '\\Users\\' in project_path:
                    match = re.search(r'\\Users\\([^\\]+)', project_path)
                    if match:
                        potential_user = match.group(1)
                        if potential_user.lower() not in ['administrator', 'admin', 'public']:
                            target_user = potential_user
            
            # 方法4: 使用 whoami 命令的原始使用者（如果可用）
            if not target_user:
                try:
                    # 嘗試從登錄檔或其他來源取得原始使用者
                    import subprocess
                    result = subprocess.run(['whoami'], capture_output=True, text=True, shell=True)
                    if result.returncode == 0:
                        whoami_result = result.stdout.strip()
                        if '\\' in whoami_result:
                            potential_user = whoami_result.split('\\')[-1]
                            if potential_user.lower() not in ['administrator', 'admin']:
                                target_user = potential_user
                except:
                    pass
        
        if not target_user:
            # 最後的備案：給予 Users 群組權限
            print(f"    [INFO] 無法確定特定使用者，將給予 Users 群組完整權限")
            target_user = "Users"
        
        print(f"    [INFO] 正在為 '{target_user}' 修正目錄權限...")
        
        # 使用 icacls 命令修正權限
        icacls_command = f'icacls "{directory_path}" /grant "{target_user}:(OI)(CI)F" /t /q'
        
        success, stdout, stderr = run_git_command(icacls_command, check=False)
        if success:
            print(f"    [SUCCESS] 已修正目錄權限，'{target_user}' 現在可以完整存取")
            return True
        else:
            print(f"    [WARN] 修正權限失敗: {stderr}")
            # 如果失敗，嘗試給予 Everyone 權限作為最後手段
            fallback_command = f'icacls "{directory_path}" /grant "Everyone:(OI)(CI)F" /t /q'
            success2, stdout2, stderr2 = run_git_command(fallback_command, check=False)
            if success2:
                print(f"    [SUCCESS] 已使用 Everyone 權限作為備案")
                return True
            else:
                print(f"    [ERROR] 所有權限修正方法都失敗")
                return False
    except Exception as e:
        print(f"    [WARN] 修正權限時發生例外: {e}")
        return False


def clone_or_update_project(repo_name):
    """
    Clone 或檢查單一專案（自動切換/建立 fortify 分支）
    """
    print(f"\n--- 處理專案: {repo_name} ---")
    
    repo_path = PROJECTS_DIR / repo_name
    repo_url = get_repo_url(repo_name)
    
    if os.path.exists(repo_path):
        print(f"  [INFO] 專案目錄已存在: {repo_path}")
        # 檢查是否為有效的 Git 倉庫
        if not os.path.exists(os.path.join(repo_path, ".git")):
            print(f"  [ERROR] 目錄存在但不是 Git 倉庫，請手動清理: {repo_path}")
            return False
        print(f"  [SUCCESS] 專案已存在且為有效的 Git 倉庫")
        print(f"  [INFO] 跳過 clone，直接自動切換/建立 fortify 分支 ...")
        auto_checkout_fortify_branch(repo_path)
        return True
    else:
        print(f"  [INFO] 專案目錄不存在，開始 clone...")
        os.makedirs(PROJECTS_DIR, exist_ok=True)
        large_repos = ['imj']
        if repo_name in large_repos:
            print(f"  [INFO] 偵測到大型倉庫，使用優化 clone 策略...")
            success = clone_large_repository(repo_url, repo_path, "evergreen/main")
        else:
            clone_command = f"git clone {repo_url} {repo_path}"
            success, stdout, stderr = run_git_command(clone_command)
            if not success:
                print(f"  [WARN] 一般 clone 失敗: {stderr}")
                print(f"  [INFO] 嘗試使用優化策略...")
                success = clone_large_repository(repo_url, repo_path, "evergreen/main")
        if not success:
            print(f"  [ERROR] 所有 clone 策略都失敗")
            return False
        print(f"  [SUCCESS] 已成功 clone 專案到: {repo_path}")
        fix_directory_permissions(repo_path)
        auto_checkout_fortify_branch(repo_path)
        return True


def clone_large_repository(repo_url, repo_path, target_branch):
    """
    針對大型倉庫的優化 clone 策略
    """
    strategies = [
        ("淺層 clone (深度 1)", f"git clone --depth 1 --branch evergreen/main {repo_url} {repo_path}"),
        ("淺層 clone (深度 10)", f"git clone --depth 10 --branch evergreen/main {repo_url} {repo_path}"),
        ("單一分支 clone", f"git clone --single-branch --branch evergreen/main {repo_url} {repo_path}"),
        ("淺層單一分支", f"git clone --depth 1 --single-branch --branch evergreen/main {repo_url} {repo_path}")
    ]
    
    for strategy_name, clone_command in strategies:
        print(f"    -> 嘗試策略: {strategy_name}")
        
        # 如果目錄已存在，先清理
        if os.path.exists(repo_path):
            try:
                shutil.rmtree(repo_path)
            except Exception as e:
                print(f"    [WARN] 清理目錄失敗: {e}")
                continue
        
        # 設定較長的超時時間
        success, stdout, stderr = run_git_command_with_timeout(clone_command, timeout=600)  # 10分鐘超時
        
        if success:
            print(f"    [SUCCESS] {strategy_name} 成功")
            
            # 如果是淺層 clone，需要取得完整的分支資訊
            if "--depth" in clone_command:
                print(f"    -> 取得完整分支資訊...")
                success, stdout, stderr = run_git_command("git fetch --unshallow", cwd=repo_path, check=False)
                if not success:
                    print(f"    [WARN] 無法取得完整歷史: {stderr}")
                    # 不是致命錯誤，繼續執行
            
            return True
        else:
            print(f"    [FAIL] {strategy_name} 失敗: {stderr}")
    
    return False


def run_git_command_with_timeout(command, cwd=None, timeout=300):
    """
    執行 Git 命令並設定超時時間
    """
    try:
        import subprocess
        result = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", f"命令執行超時 ({timeout} 秒)"
    except subprocess.CalledProcessError as e:
        return False, e.stdout.strip() if e.stdout else "", e.stderr.strip() if e.stderr else str(e)
    except Exception as e:
        return False, "", str(e)


def auto_checkout_fortify_branch(repo_path):
    """
    自動切換到第一個 evergreen/ 下名稱包含 fortify 的分支，
    若不存在則從 evergreen/main 建立 evergreen/fortify 並切換。
    """
    # 取得所有遠端分支
    success, stdout, stderr = run_git_command("git ls-remote --heads origin", cwd=repo_path)
    if not success or not stdout.strip():
        print(f"    [WARN] 取得遠端分支資訊失敗: {stderr}")
        return False
    branches = stdout.strip().splitlines()
    target_branch = None
    for branch_line in branches:
        if "refs/heads/" in branch_line:
            branch_name = branch_line.split("refs/heads/")[-1]
            if branch_name.startswith("evergreen/") and "fortify" in branch_name.lower():
                target_branch = branch_name
                break
    if target_branch:
        print(f"    [INFO] 自動切換到已存在分支 '{target_branch}' ...")
        success, _, stderr = run_git_command(f"git checkout -B {target_branch} origin/{target_branch}", cwd=repo_path)
        if success:
            print(f"    [SUCCESS] 已切換到分支 '{target_branch}'")
            return True
        else:
            print(f"    [ERROR] 切換分支失敗: {stderr}")
            return False
    else:
        # 沒有符合的分支，自動建立 evergreen/fortify
        print(f"    [INFO] 未發現 evergreen/ 下含 fortify 的分支，自動建立 'evergreen/fortify' ...")
        base_branch = "evergreen/main"
        # 先確保 base_branch 存在
        success, _, stderr = run_git_command(f"git checkout -B {base_branch} origin/{base_branch}", cwd=repo_path)
        if not success:
            print(f"    [ERROR] 切換到基礎分支 '{base_branch}' 失敗: {stderr}")
            return False
        # 建立新分支
        success, _, stderr = run_git_command(f"git checkout -b evergreen/fortify", cwd=repo_path)
        if not success:
            print(f"    [ERROR] 建立 'evergreen/fortify' 失敗: {stderr}")
            return False
        # 推送到遠端
        success, _, stderr = run_git_command(f"git push -u origin evergreen/fortify", cwd=repo_path)
        if success:
            print(f"    [SUCCESS] 已建立並切換到 'evergreen/fortify' 分支")
            return True
        else:
            print(f"    [WARN] 推送 'evergreen/fortify' 到遠端失敗: {stderr}")
            return False


def clone_all_projects():
    """
    Clone 或檢查負責專案
    """
    print("=== 開始 Clone/檢查負責專案 ===")
    print(f"專案將被 clone 到: {PROJECTS_DIR}")
    
    # 改為只取得負責專案
    config = get_config()
    repos = config.get_repos("main")
    if not repos:
        print("[ERROR] 無法取得負責專案清單")
        return
    
    print(f"找到 {len(repos)} 個負責專案需要處理...")
    
    success_count = 0
    failed_projects = []
    
    for repo in repos:
        repo_name = repo
        try:
            if clone_or_update_project(repo_name):
                success_count += 1
            else:
                failed_projects.append(repo_name)
        except Exception as e:
            print(f"  [ERROR] 處理專案 '{repo_name}' 時發生例外: {e}")
            failed_projects.append(repo_name)
    
    print(f"\n=== 處理完成 ===")
    print(f"成功: {success_count}/{len(repos)} 個專案")
    
    if failed_projects:
        print(f"失敗的專案: {', '.join(failed_projects)}")
    else:
        print("所有負責專案都已成功處理！")


if __name__ == "__main__":
    clone_all_projects()
