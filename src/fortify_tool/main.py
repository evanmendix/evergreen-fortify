#!/usr/bin/env python3

import sys
import os
import argparse
from pathlib import Path

# 當直接執行時，添加專案路徑支援
if __name__ == "__main__":
    # 取得專案根目錄
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent  # 回到 fortify_report/
    src_dir = project_root / "src"
    
    # 將 src 目錄添加到 Python 路徑的最前面
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

# 統一使用絕對導入（從 src/ 開始）
from fortify_tool.actions.fetch_reports import fetch_reports
from fortify_tool.actions.process_pdfs import process_local_pdfs
from fortify_tool.actions.sync_reports import sync_report_status
from fortify_tool.actions.list_repos import list_repos
from fortify_tool.actions.sync_solutions import main as sync_solutions_main
from fortify_tool.actions.clone_projects import clone_all_projects
from fortify_tool.actions.trigger_pipelines import FortifyPipelineTrigger


def main():
    parser = argparse.ArgumentParser(description="Fortify 報告與結果自動化處理工具")
    subparsers = parser.add_subparsers(dest="action", help="可用的操作")

    subparsers.add_parser("list-repos", help="列出所有專案")
    subparsers.add_parser("fetch-reports", help="從 Fortify 平台下載報告")
    subparsers.add_parser("process-pdfs", help="處理 PDF 報告並拆分")
    subparsers.add_parser("sync-solutions", help="同步解決方案")
    subparsers.add_parser("clone", help="Clone/更新所有專案")
    subparsers.add_parser("all", help="執行完整流程 (clone + fetch + process)")

    trigger_parser = subparsers.add_parser("trigger-pipelines", help="觸發 Fortify Pipeline")
    trigger_group = trigger_parser.add_mutually_exclusive_group(required=True)
    trigger_group.add_argument("--list", action="store_true", help="列出所有可用的 Fortify Pipeline")
    trigger_group.add_argument("--repo", nargs="+", help="指定要觸發的專案名稱")
    trigger_group.add_argument("--all", action="store_true", help="觸發所有可用的 Fortify Pipeline")

    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        return

    try:
        if args.action == "list-repos":
            print("--- 開始執行 [list-repos] 動作 ---")
            repos = list_repos()
            print("目前的專案清單：")
            for repo in repos:
                print(f"- {repo}")
            print("--- [list-repos] 動作執行完畢 ---")
        elif args.action == "fetch-reports":
            print("--- 開始執行 [fetch] 動作 ---")
            fetch_reports()
            print("--- [fetch] 動作執行完畢 ---")
        elif args.action == "process-pdfs":
            print("--- 開始執行 [process] 動作 ---")
            process_local_pdfs()
            print("--- [process] 動作執行完畢 ---")
        elif args.action == "sync-solutions":
            print("--- 開始執行 [sync-solutions] 動作 ---")
            sync_solutions_main()
            print("--- [sync-solutions] 動作執行完畢 ---")
        elif args.action == "clone":
            print("--- 開始執行 [clone] 動作 ---")
            clone_all_projects()
            print("--- [clone] 動作執行完畢 ---")
        elif args.action == "trigger-pipelines":
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
        elif args.action == "all":
            print("執行完整流程...")
            print("--- 開始執行 [clone] 動作 ---")
            clone_all_projects()
            print("--- [clone] 動作執行完畢 ---")
            print("--- 開始執行 [fetch] 動作 ---")
            fetch_reports()
            print("--- [fetch] 動作執行完畢 ---")
            print("--- 開始執行 [process] 動作 ---")
            process_local_pdfs()
            print("--- [process] 動作執行完畢 ---")
            print("--- 開始執行 [sync] 動作 ---")
            sync_report_status()
            print("--- [sync] 動作執行完畢 ---")
        else:
            print(f"未知的操作: {args.action}")
    except Exception as e:
        print(f"執行時發生錯誤: {e}")


if __name__ == "__main__":
    main()
