import os
import shutil
import glob

# Determine the project root dynamically
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '..'))


def sync_report_status():
    print("--- 開始執行 [sync_report_status] 動作 ---")

    unresolved_reports_dir = os.path.join(PROJECT_ROOT, 'data', 'reports', '完整Fortify報告')
    resolved_reports_dir = os.path.join(PROJECT_ROOT, 'data', 'reports', '已修復專案')
    split_reports_base_dir = os.path.join(PROJECT_ROOT, 'data', 'reports', 'repo拆分報告')

    # 1. Get current unresolved projects
    unresolved_pdfs = glob.glob(os.path.join(unresolved_reports_dir, '**', '*.pdf'), recursive=True)
    unresolved_projects_now = {os.path.splitext(os.path.basename(p))[0] for p in unresolved_pdfs}
    print(f"  [INFO] 目前未解決的專案: {len(unresolved_projects_now)} 個")

    # 2. Get current resolved projects
    resolved_pdfs = glob.glob(os.path.join(resolved_reports_dir, '**', '*.pdf'), recursive=True)
    resolved_projects_now = {os.path.splitext(os.path.basename(p))[0] for p in resolved_pdfs}
    print(f"  [INFO] 目前已解決的專案: {len(resolved_projects_now)} 個")

    # 3. Get existing split report projects
    existing_split_report_dirs = []
    if os.path.isdir(split_reports_base_dir):
        existing_split_report_dirs = [d for d in os.listdir(split_reports_base_dir) if
                                      os.path.isdir(os.path.join(split_reports_base_dir, d))]
    split_report_projects_existing = set(existing_split_report_dirs)
    print(f"  [INFO] 現有拆分報告的專案: {len(split_report_projects_existing)} 個")

    # Rule 1: Clean up split reports for projects no longer unresolved
    for project_name in split_report_projects_existing:
        if project_name not in unresolved_projects_now:
            project_split_dir = os.path.join(split_reports_base_dir, project_name)
            if os.path.exists(project_split_dir):
                print(f"  [INFO] 專案 '{project_name}' 已不再是未解決狀態，移除其拆分報告目錄: {project_split_dir}")
                shutil.rmtree(project_split_dir)

    # Rule 2: Remove resolved PDF if it reappears as unresolved
    for project_name in resolved_projects_now:
        if project_name in unresolved_projects_now:
            resolved_pdf_path = os.path.join(resolved_reports_dir, f"{project_name}.pdf")
            if os.path.exists(resolved_pdf_path):
                print(f"  [INFO] 專案 '{project_name}' 重新出現為未解決狀態，移除已解決的 PDF 報告: {resolved_pdf_path}")
                os.remove(resolved_pdf_path)

    print("--- [sync_report_status] 動作執行完畢 ---")
