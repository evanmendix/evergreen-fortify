#!/usr/bin/env python3
"""
Fortify 工具 Windows GUI 介面

提供圖形化介面來管理 Fortify 報告處理和 Pipeline 觸發功能。
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import subprocess
import sys
import os
from pathlib import Path
import yaml

# 添加 src 目錄到 Python 路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from fortify_tool.utils.config_loader import get_config
from fortify_tool.actions.trigger_pipelines import FortifyPipelineTrigger


class FortifyGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Fortify 安全掃描工具")
        self.root.geometry("1400x700")
        
        # 載入設定
        self.config = get_config()
        self.config_file_path = Path(__file__).parent / "config" / "config.yaml"
        
        # 建立主要介面
        self.create_widgets()
        
        # 載入初始資料
        self.refresh_config()
    
    def create_widgets(self):
        """建立 GUI 元件"""
        # 建立主要容器 - 水平分割
        main_container = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左側：分頁區域
        left_frame = ttk.Frame(main_container)
        main_container.add(left_frame, weight=2)
        
        # 建立 Notebook (分頁)
        self.notebook = ttk.Notebook(left_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # 分頁 1: Pipeline 管理
        self.pipeline_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.pipeline_frame, text="Pipeline 管理")
        self.create_pipeline_tab()
        
        # 分頁 2: 報告處理
        self.report_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.report_frame, text="報告處理")
        self.create_report_tab()
        
        # 分頁 3: 設定管理
        self.config_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.config_frame, text="設定管理")
        self.create_config_tab()
        
        # 分頁 4: 掃描結果
        self.scan_results_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.scan_results_frame, text="掃描結果")
        self.create_scan_results_tab()
        
        # 右側：輸出區域
        right_frame = ttk.Frame(main_container)
        main_container.add(right_frame, weight=1)
        self.create_output_area(right_frame)
    
    def create_pipeline_tab(self):
        """建立 Pipeline 管理分頁"""
        # 分支要求提醒區域
        branch_info_frame = ttk.LabelFrame(self.pipeline_frame, text="⚠️ 重要提醒")
        branch_info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        branch_info_text = """
🌿 分支要求：請確保要檢查的分支為以下格式之一：
   • evergreen/fortify
   • evergreen/main_fortify_fix_2025
   • evergreen/其他包含 fortify 名稱的分支

💡 系統會自動搜尋並優先使用符合條件的分支進行 Fortify 掃描
        """
        
        branch_info_label = ttk.Label(branch_info_frame, text=branch_info_text.strip(), 
                                     font=("TkDefaultFont", 9), foreground="darkblue")
        branch_info_label.pack(anchor=tk.W, padx=10, pady=5)
        
        # Pipeline 管理與掃描結果整合區域
        main_frame = ttk.LabelFrame(self.pipeline_frame, text="Pipeline 管理 - 負責專案")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 按鈕區域
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(button_frame, text="🔄 更新掃描結果", 
                  command=self.update_scan_results).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="🚀 觸發選中專案", 
                  command=self.trigger_selected_pipelines).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="🚀 觸發所有負責專案", 
                  command=self.trigger_all_main_pipelines).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="📋 查看選中 Build 詳情", 
                  command=self.view_build_details).pack(side=tk.LEFT, padx=2)
        
        # 狀態標籤
        self.scan_status_label = ttk.Label(button_frame, text="")
        self.scan_status_label.pack(side=tk.RIGHT, padx=5)
        
        # 整合的掃描結果與專案選擇表格
        results_display_frame = ttk.Frame(main_frame)
        results_display_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 使用 Treeview 來顯示掃描結果（合併專案選擇功能）
        columns = ("project", "scan_time", "branch", "result", "build_id")
        self.scan_results_tree = ttk.Treeview(results_display_frame, columns=columns, show="headings", height=12)
        
        # 設定欄位標題
        self.scan_results_tree.heading("project", text="專案名稱")
        self.scan_results_tree.heading("scan_time", text="上次掃描時間")
        self.scan_results_tree.heading("branch", text="掃描分支")
        self.scan_results_tree.heading("result", text="掃描結果")
        self.scan_results_tree.heading("build_id", text="Build ID")
        
        # 設定欄位寬度
        self.scan_results_tree.column("project", width=120)
        self.scan_results_tree.column("scan_time", width=150)
        self.scan_results_tree.column("branch", width=200)
        self.scan_results_tree.column("result", width=120)
        self.scan_results_tree.column("build_id", width=100)
        
        # 添加滾動條
        scan_scrollbar = ttk.Scrollbar(results_display_frame, orient=tk.VERTICAL, command=self.scan_results_tree.yview)
        self.scan_results_tree.configure(yscrollcommand=scan_scrollbar.set)
        
        self.scan_results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scan_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 保持與原有邏輯兼容的 pipeline_listbox（隱藏，僅用於內部邏輯）
        self.pipeline_listbox = tk.Listbox(main_frame, selectmode=tk.MULTIPLE)
        # 不顯示這個 listbox，僅用於保持現有代碼兼容性
    
    def create_report_tab(self):
        """建立報告處理分頁"""
        # 功能說明區域
        help_frame = ttk.LabelFrame(self.report_frame, text="📋 功能說明")
        help_frame.pack(fill=tk.X, padx=10, pady=5)
        
        help_text = """
🔄 建議執行順序：
1️⃣ Clone專案至本地  → 取得最新的專案原始碼到本地
2️⃣ 下載報告 → 從 Fortify 平台下載最新的掃描報告
3️⃣ 處理 PDF → 將 PDF 報告拆分成個別問題的 Markdown 檔案
4️⃣ 同步狀態 → 將處理結果同步回 Fortify 平台
5️⃣ 同步解決方案 → 下載最新的修復解決方案

💡 提示：可直接點擊「執行完整工作流程」一次完成所有步驟
        """
        
        help_label = ttk.Label(help_frame, text=help_text.strip(), 
                              font=("TkDefaultFont", 9), foreground="gray")
        help_label.pack(anchor=tk.W, padx=10, pady=5)
        
        # 報告處理區域 - 只針對負責專案
        report_frame = ttk.LabelFrame(self.report_frame, text="報告處理 - 負責專案")
        report_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 第一排按鈕：核心流程
        button_frame1 = ttk.Frame(report_frame)
        button_frame1.pack(fill=tk.X, padx=5, pady=5)
        
        # 為每個按鈕加上詳細說明
        clone_btn = ttk.Button(button_frame1, text="1. Clone專案至本地 ", 
                              command=self.clone_main_projects)
        clone_btn.pack(side=tk.LEFT, padx=2)
        self.create_tooltip(clone_btn, "取得負責專案的最新原始碼\n確保，clone分支為evergreen/目錄下方包含fortify名稱的分支")
        
        download_btn = ttk.Button(button_frame1, text="2. 下載報告", 
                                 command=self.download_main_reports)
        download_btn.pack(side=tk.LEFT, padx=2)
        self.create_tooltip(download_btn, "從 Fortify on Demand 下載最新掃描報告\n自動分類已修復/待修復專案")
        
        process_btn = ttk.Button(button_frame1, text="3. 處理 PDF", 
                                command=self.process_main_pdfs)
        process_btn.pack(side=tk.LEFT, padx=2)
        self.create_tooltip(process_btn, "將 PDF 報告按問題類別拆分\n生成 Markdown 格式的個別問題檔案")
        
        # 第二排按鈕：同步與完整流程
        button_frame2 = ttk.Frame(report_frame)
        button_frame2.pack(fill=tk.X, padx=5, pady=5)
        
        sync_status_btn = ttk.Button(button_frame2, text="4. 同步狀態", 
                                    command=self.sync_main_status)
        sync_status_btn.pack(side=tk.LEFT, padx=2)
        self.create_tooltip(sync_status_btn, "將處理後的報告狀態\n同步回 Fortify on Demand 平台")
        
        sync_solution_btn = ttk.Button(button_frame2, text="5. 同步解決方案", 
                                      command=self.sync_main_solutions)
        sync_solution_btn.pack(side=tk.LEFT, padx=2)
        self.create_tooltip(sync_solution_btn, "從 HackMD 下載最新的\n問題修復解決方案到本地，Google Doc的待商議案例需要手動下載")
        
        # 完整流程按鈕 - 特殊樣式
        full_workflow_btn = ttk.Button(button_frame2, text="🚀 執行完整工作流程", 
                                      command=self.run_main_full_workflow)
        full_workflow_btn.pack(side=tk.RIGHT, padx=10)
        self.create_tooltip(full_workflow_btn, "依序執行所有步驟：\nClone → 下載 → 處理 → 同步狀態")
        
        # 狀態顯示區域
        status_frame = ttk.LabelFrame(self.report_frame, text="📊 處理狀態")
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.report_status_label = ttk.Label(status_frame, 
                                           text="💡 請先確認已設定 PAT 並選擇負責專案，然後開始處理流程",
                                           font=("TkDefaultFont", 9), foreground="blue")
        self.report_status_label.pack(anchor=tk.W, padx=10, pady=5)
        
        # 步驟進度顯示區域
        progress_frame = ttk.Frame(status_frame)
        progress_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        
        # 初始化步驟狀態
        self.workflow_steps = {
            "clone": {"name": "1. Clone專案", "status": "pending", "label": None},
            "download": {"name": "2. 下載報告", "status": "pending", "label": None},
            "process": {"name": "3. 處理PDF", "status": "pending", "label": None},
            "sync_status": {"name": "4. 同步狀態", "status": "pending", "label": None},
            "sync_solution": {"name": "5. 同步解決方案", "status": "pending", "label": None}
        }
        
        # 創建步驟狀態標籤
        for step_key, step_info in self.workflow_steps.items():
            step_label = ttk.Label(progress_frame, text=f"{step_info['name']}: ⏳ 待執行", 
                                 font=("TkDefaultFont", 8), foreground="gray")
            step_label.pack(anchor=tk.W, padx=5, pady=1)
            step_info["label"] = step_label
    
    def create_config_tab(self):
        """建立設定管理分頁"""
        # PAT 設定區域
        pat_frame = ttk.LabelFrame(self.config_frame, text="Azure DevOps PAT 設定")
        pat_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # PAT 輸入區域
        pat_input_frame = ttk.Frame(pat_frame)
        pat_input_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(pat_input_frame, text="Personal Access Token (PAT):").pack(anchor=tk.W, pady=(0, 2))
        
        # PAT 輸入框與按鈕
        pat_entry_frame = ttk.Frame(pat_input_frame)
        pat_entry_frame.pack(fill=tk.X, pady=2)
        
        self.pat_var = tk.StringVar()
        self.pat_entry = ttk.Entry(pat_entry_frame, textvariable=self.pat_var, width=50)
        self.pat_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        # PAT 測試按鈕
        ttk.Button(pat_entry_frame, text="測試連線", 
                  command=self.test_pat_connection).pack(side=tk.RIGHT, padx=2)
        
        # PAT 狀態與說明
        self.pat_status = ttk.Label(pat_input_frame, text="")
        self.pat_status.pack(anchor=tk.W, pady=2)
        
        # PAT 說明
        pat_help = ttk.Label(pat_input_frame, 
                            text="💡 提示：PAT 需要 Build (read and execute) 權限，請至 https://dev.azure.com/chte 建立",
                            foreground="gray", font=("TkDefaultFont", 8))
        pat_help.pack(anchor=tk.W, pady=2)
        
        # PAT 變更監聽
        self.pat_var.trace_add("write", self.on_pat_changed)
        
        # 負責專案管理區域
        project_frame = ttk.LabelFrame(self.config_frame, text="負責專案管理")
        project_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 左側：當前負責專案
        left_frame = ttk.Frame(project_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        ttk.Label(left_frame, text="當前負責專案:").pack(anchor=tk.W)
        self.main_repos_listbox = tk.Listbox(left_frame, selectmode=tk.MULTIPLE)
        self.main_repos_listbox.pack(fill=tk.BOTH, expand=True, pady=2)
        
        # 左側按鈕
        left_buttons = ttk.Frame(left_frame)
        left_buttons.pack(fill=tk.X, pady=2)
        ttk.Button(left_buttons, text="移除選中", 
                  command=self.remove_repos_from_main).pack(side=tk.LEFT, padx=2)
        
        # 中間：操作按鈕
        middle_frame = ttk.Frame(project_frame)
        middle_frame.pack(side=tk.LEFT, padx=10, pady=5)
        
        ttk.Button(middle_frame, text="←\n新增", 
                  command=self.add_repos_to_main).pack(pady=10)
        ttk.Button(middle_frame, text="→\n移除", 
                  command=self.remove_repos_from_main).pack(pady=10)
        
        # 右側：所有可用專案
        right_frame = ttk.Frame(project_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        ttk.Label(right_frame, text="所有可用專案:").pack(anchor=tk.W)
        self.all_repos_listbox = tk.Listbox(right_frame, selectmode=tk.MULTIPLE)
        self.all_repos_listbox.pack(fill=tk.BOTH, expand=True, pady=2)
        
        # 右側按鈕
        right_buttons = ttk.Frame(right_frame)
        right_buttons.pack(fill=tk.X, pady=2)
        ttk.Button(right_buttons, text="新增選中", 
                  command=self.add_all_repos).pack(side=tk.LEFT, padx=2)
        
        # 底部：設定操作
        config_buttons = ttk.Frame(self.config_frame)
        config_buttons.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(config_buttons, text="儲存設定", 
                  command=self.save_config).pack(side=tk.LEFT, padx=2)
        ttk.Button(config_buttons, text="重新載入設定", 
                  command=self.refresh_config).pack(side=tk.LEFT, padx=2)
        ttk.Button(config_buttons, text="開啟設定檔", 
                  command=self.open_config_file).pack(side=tk.LEFT, padx=2)
    
    def create_scan_results_tab(self):
        """建立掃描結果分頁"""
        # 控制按鈕區域
        control_frame = ttk.Frame(self.scan_results_frame)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(control_frame, text="🔄 重新載入掃描結果", 
                  command=self.load_scan_results).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(control_frame, text="🗑️ 清除快取", 
                  command=self.clear_scan_cache).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(control_frame, text="💾 強制重新掃描", 
                  command=self.force_reload_scan_results).pack(side=tk.LEFT, padx=2)
        
        self.scan_results_status = ttk.Label(control_frame, text="")
        self.scan_results_status.pack(side=tk.RIGHT, padx=5)
        
        # 使用 PanedWindow 分割上下區域
        paned = ttk.PanedWindow(self.scan_results_frame, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 上方：專案掃描結果總覽
        top_frame = ttk.LabelFrame(paned, text="專案掃描結果總覽")
        paned.add(top_frame, weight=1)
        
        # 專案結果表格
        project_columns = ("project", "total_issues", "total_sources", "total_sinks", "branch_name", "scan_time")
        self.project_results_tree = ttk.Treeview(top_frame, columns=project_columns, show="headings", height=8)
        
        # 設定欄位標題
        self.project_results_tree.heading("project", text="專案名稱")
        self.project_results_tree.heading("total_issues", text="議題數量")
        self.project_results_tree.heading("total_sources", text="Source 數量")
        self.project_results_tree.heading("total_sinks", text="Sink 數量")
        self.project_results_tree.heading("branch_name", text="掃描分支")
        self.project_results_tree.heading("scan_time", text="處理時間")
        
        # 設定欄位寬度
        self.project_results_tree.column("project", width=100)
        self.project_results_tree.column("total_issues", width=80)
        self.project_results_tree.column("total_sources", width=80)
        self.project_results_tree.column("total_sinks", width=80)
        self.project_results_tree.column("branch_name", width=180)
        self.project_results_tree.column("scan_time", width=130)
        
        # 添加滾動條
        project_scrollbar = ttk.Scrollbar(top_frame, orient=tk.VERTICAL, command=self.project_results_tree.yview)
        self.project_results_tree.configure(yscrollcommand=project_scrollbar.set)
        
        self.project_results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        project_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 綁定選擇事件
        self.project_results_tree.bind("<<TreeviewSelect>>", self.on_project_select)
        
        # 下方：選中專案的詳細議題
        bottom_frame = ttk.LabelFrame(paned, text="專案議題詳情")
        paned.add(bottom_frame, weight=1)
        
        # 議題詳情表格
        issue_columns = ("issue_type", "sources", "sinks", "total")
        self.issue_details_tree = ttk.Treeview(bottom_frame, columns=issue_columns, show="headings", height=8)
        
        # 設定欄位標題
        self.issue_details_tree.heading("issue_type", text="議題類型")
        self.issue_details_tree.heading("sources", text="Source 數量")
        self.issue_details_tree.heading("sinks", text="Sink 數量")
        self.issue_details_tree.heading("total", text="總計")
        
        # 設定欄位寬度
        self.issue_details_tree.column("issue_type", width=300)
        self.issue_details_tree.column("sources", width=100)
        self.issue_details_tree.column("sinks", width=100)
        self.issue_details_tree.column("total", width=100)
        
        # 添加滾動條
        issue_scrollbar = ttk.Scrollbar(bottom_frame, orient=tk.VERTICAL, command=self.issue_details_tree.yview)
        self.issue_details_tree.configure(yscrollcommand=issue_scrollbar.set)
        
        self.issue_details_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        issue_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def create_output_area(self, parent):
        """建立輸出區域"""
        output_frame = ttk.LabelFrame(parent, text="執行輸出")
        output_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        self.output_text = scrolledtext.ScrolledText(output_frame, height=10)
        self.output_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 清除按鈕
        ttk.Button(output_frame, text="清除輸出", 
                  command=self.clear_output).pack(anchor=tk.E, padx=5, pady=2)
    
    def refresh_config(self):
        """重新載入設定"""
        try:
            # 重新載入配置文件（不使用緩存）
            self.config.reload()
            
            # PAT 欄位同步 - 從環境變數讀取
            import os
            pat = os.getenv("AZURE_DEVOPS_PAT", "")
            self.pat_var.set(pat)
            if pat:
                self.pat_status.config(text="✅ PAT 已設定", foreground="green")
            else:
                self.pat_status.config(text="❌ 尚未設定 PAT", foreground="red")
            # 控制功能鎖定
            self.set_feature_lock(not bool(pat))
            
            # 清空並重新載入專案列表
            self.main_repos_listbox.delete(0, tk.END)
            self.all_repos_listbox.delete(0, tk.END)
            # 清空 Treeview 中的掃描結果
            for item in self.scan_results_tree.get_children():
                self.scan_results_tree.delete(item)
            # 清空隱藏的 pipeline_listbox（保持兼容性）
            self.pipeline_listbox.delete(0, tk.END)
            
            # 從 cache 載入 main_repos
            main_repos = self.config.get_repos("main")
            for repo in main_repos:
                self.main_repos_listbox.insert(tk.END, repo)
                # 在隱藏的 listbox 中也添加（保持兼容性）
                self.pipeline_listbox.insert(tk.END, repo)
                # 在 Treeview 中添加專案行，初始狀態為未掃描
                self.scan_results_tree.insert("", "end", values=(repo, "尚未掃描", "-", "-", "-"))
            
            # 從 config.yaml 載入 all_repos
            all_repos = self.config.get_repos("all")
            for repo in all_repos:
                self.all_repos_listbox.insert(tk.END, repo)
            
            self.append_output(f"✅ 設定重新載入完成 - 負責專案: {len(main_repos)}, 所有專案: {len(all_repos)}")
            
            # 重置工作流程狀態
            if hasattr(self, 'workflow_steps'):
                self.reset_workflow_status()
        except Exception as e:
            messagebox.showerror("錯誤", f"重新載入設定失敗：{e}")
            self.append_output(f"❌ 設定載入失敗: {e}")
    
    def add_repos_to_main(self):
        """從所有專案新增到負責專案"""
        selected_indices = self.all_repos_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("警告", "請先選擇要新增的專案")
            return
            
        selected_repos = [self.all_repos_listbox.get(i) for i in selected_indices]
        
        current_main_repos = list(self.main_repos_listbox.get(0, tk.END))
        
        # 過濾已存在的專案
        new_repos = [repo for repo in selected_repos if repo not in current_main_repos]
        
        if not new_repos:
            messagebox.showinfo("資訊", "選擇的專案已經在負責專案清單中")
            return
        
        # 新增到負責專案列表
        for repo in new_repos:
            self.main_repos_listbox.insert(tk.END, repo)
            # 在隱藏的 listbox 中也添加（保持兼容性）
            self.pipeline_listbox.insert(tk.END, repo)
            
        # 從所有專案列表中移除已新增的專案
        for i in reversed(selected_indices):
            self.all_repos_listbox.delete(i)
            
        self.append_output(f"✅ 已新增 {len(new_repos)} 個專案到負責專案: {', '.join(new_repos)}")
    
    def remove_repos_from_main(self):
        """從負責專案移除到所有專案"""
        selected_indices = self.main_repos_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("警告", "請先選擇要移除的專案")
            return
            
        selected_repos = [self.main_repos_listbox.get(i) for i in selected_indices]
        
        if not messagebox.askyesno("確認", f"確定要從負責專案中移除以下專案嗎？\n\n{', '.join(selected_repos)}"):
            return
        
        # 從後往前刪除，避免索引變化
        for i in reversed(selected_indices):
            repo = self.main_repos_listbox.get(i)
            self.main_repos_listbox.delete(i)
            
            # 同時從隱藏的 Pipeline 列表移除
            pipeline_items = list(self.pipeline_listbox.get(0, tk.END))
            if repo in pipeline_items:
                pipeline_index = pipeline_items.index(repo)
                self.pipeline_listbox.delete(pipeline_index)
            
            # 從 Treeview 中移除對應的專案行
            for item in self.scan_results_tree.get_children():
                values = self.scan_results_tree.item(item)['values']
                if values and len(values) > 0 and values[0] == repo:
                    self.scan_results_tree.delete(item)
                    break
            
            # 將移除的專案加回到所有專案列表中
            self.all_repos_listbox.insert(tk.END, repo)
                 
        self.append_output(f"✅ 已從負責專案移除: {', '.join(selected_repos)}")
    
    def remove_main_repos(self):
        """移除選中的負責專案"""
        self.remove_repos_from_main()  # 使用相同邏輯
    
    def add_all_repos(self):
        """新增選中的所有專案到負責專案"""
        self.add_repos_to_main()  # 使用相同邏輯
    
    def save_config(self):
        """儲存專案設定到 cache（不處理 PAT 和 config.yaml）"""
        try:
            # 只儲存 main_repos 到 cache
            current_main_repos = list(self.main_repos_listbox.get(0, tk.END))
            self.config.save_main_repos(current_main_repos)
            
            # 重新載入設定並同步所有 GUI 元件
            self.refresh_config()
            
            messagebox.showinfo("成功", f"專案設定已儲存！\n負責專案: {len(current_main_repos)} 個")
            self.append_output(f"✅ 專案設定已儲存到 cache - 負責專案: {', '.join(current_main_repos)}")
            
        except Exception as e:
            messagebox.showerror("錯誤", f"儲存專案設定失敗：{e}")
            self.append_output(f"❌ 儲存專案設定失敗: {e}")
    
    def trigger_selected_pipelines(self):
        """觸發選中的負責專案 Pipeline"""
        # 從 Treeview 獲取選中的專案
        selected_items = self.scan_results_tree.selection()
        if not selected_items:
            messagebox.showwarning("警告", "請先選擇要觸發的專案")
            return
        
        # 獲取選中專案的名稱
        selected_repos = []
        for item in selected_items:
            values = self.scan_results_tree.item(item)['values']
            if values and len(values) > 0:
                selected_repos.append(values[0])  # 專案名稱在第一欄
        
        if not selected_repos:
            messagebox.showwarning("警告", "沒有有效的專案選擇")
            return
            
        if not messagebox.askyesno("確認", f"確定要觸發以下專案的 Pipeline 嗎？\n\n{', '.join(selected_repos)}"):
            return
        
        self.append_output(f"🚀 開始觸發選中專案的 Pipeline: {', '.join(selected_repos)}")
        
        def run_trigger():
            try:
                # 導入必要的模組
                from fortify_tool.actions.trigger_pipelines import FortifyPipelineTrigger
                
                trigger = FortifyPipelineTrigger()
                trigger.trigger_multiple_pipelines(selected_repos)
                
                self.root.after(0, lambda: self.append_output("✅ Pipeline 觸發請求已完成"))
                
                # 自動更新掃描結果
                self.root.after(2000, self.update_scan_results)  # 2秒後自動更新
                
            except Exception as e:
                error_msg = f"❌ 觸發 Pipeline 時發生錯誤: {e}"
                self.root.after(0, lambda: self.append_output(error_msg))
        
        threading.Thread(target=run_trigger, daemon=True).start()
    
    def trigger_all_main_pipelines(self):
        """觸發所有負責專案 Pipeline"""
        main_repos = self.config.get_repos("main")
        
        if not main_repos:
            messagebox.showwarning("警告", "沒有負責專案可觸發")
            return
            
        if not messagebox.askyesno("確認", f"確定要觸發所有 {len(main_repos)} 個負責專案的 Pipeline 嗎？"):
            return
        
        self.append_output(f"🚀 開始觸發所有負責專案的 Pipeline: {', '.join(main_repos)}")
        
        def run_trigger():
            try:
                # 導入必要的模組
                from fortify_tool.actions.trigger_pipelines import FortifyPipelineTrigger
                
                trigger = FortifyPipelineTrigger()
                trigger.trigger_multiple_pipelines(main_repos)
                
                self.root.after(0, lambda: self.append_output("✅ Pipeline 觸發請求已完成"))
                
                # 自動更新掃描結果
                self.root.after(2000, self.update_scan_results)  # 2秒後自動更新
                
            except Exception as e:
                error_msg = f"❌ 觸發 Pipeline 時發生錯誤: {e}"
                self.root.after(0, lambda: self.append_output(error_msg))
        
        threading.Thread(target=run_trigger, daemon=True).start()
    
    def run_fortify_command_for_main(self, command, description, step_key):
        """針對負責專案執行 Fortify 命令"""
        main_repos = self.config.get_repos("main")
        
        if not main_repos:
            messagebox.showwarning("警告", "沒有設定負責專案")
            return
            
        self.append_output(f"🔧 開始執行 {description} (負責專案: {', '.join(main_repos)})...")
        
        def run_command():
            try:
                cmd = ["uv", "run", "fortify", command]
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=Path(__file__).parent,
                    bufsize=1,
                    universal_newlines=True
                )
                
                for line in iter(process.stdout.readline, ''):
                    self.root.after(0, lambda l=line: self.append_output(l.rstrip()))
                
                process.wait()
                
                if process.returncode == 0:
                    self.root.after(0, lambda: self.append_output(f"✅ {description} 執行完成"))
                    self.root.after(0, lambda: self.update_workflow_step_status(step_key, "success"))
                    if step_key == "full_workflow":
                        # 完整工作流程成功時，標記所有步驟為完成
                        self.root.after(0, lambda: self.mark_all_steps_complete())
                        self.root.after(0, lambda: self.update_report_status("完整工作流程執行完成！", "success"))
                    else:
                        self.root.after(0, lambda: self.update_report_status(f"{description} 執行完成", "success"))
                else:
                    self.root.after(0, lambda: self.append_output(f"❌ {description} 執行失敗"))
                    self.root.after(0, lambda: self.update_workflow_step_status(step_key, "failed"))
                    if step_key == "full_workflow":
                        # 完整工作流程失敗時，標記所有步驟為失敗
                        self.root.after(0, lambda: self.mark_all_steps_failed())
                        self.root.after(0, lambda: self.update_report_status("完整工作流程執行失敗", "error"))
                    else:
                        self.root.after(0, lambda: self.update_report_status(f"{description} 執行失敗", "error"))
                    
            except Exception as e:
                error_msg = f"❌ 執行 {description} 時發生錯誤: {e}"
                self.root.after(0, lambda: self.append_output(error_msg))
                self.root.after(0, lambda: self.update_workflow_step_status(step_key, "failed"))
                self.root.after(0, lambda: self.update_report_status(f"{description} 發生錯誤", "error"))
        
        threading.Thread(target=run_command, daemon=True).start()
    
    def clone_main_projects(self):
        """Clone/更新負責專案"""
        self.update_workflow_step_status("clone", "running")
        self.update_report_status("正在 Clone 負責專案...", "info")
        self.run_fortify_command_for_main("clone", "Clone專案至本地 ", "clone")

    def download_main_reports(self):
        """下載負責專案報告"""
        self.update_workflow_step_status("download", "running")
        self.update_report_status("正在下載 Fortify 報告...", "info")
        self.run_fortify_command_for_main("fetch", "下載報告", "download")

    def process_main_pdfs(self):
        """處理負責專案 PDF"""
        self.update_workflow_step_status("process", "running")
        self.update_report_status("正在處理 PDF 報告...", "info")
        self.run_fortify_command_for_main("process", "處理 PDF", "process")

    def sync_main_status(self):
        """同步負責專案狀態"""
        self.update_workflow_step_status("sync_status", "running")
        self.update_report_status("正在同步狀態到 Fortify 平台...", "info")
        self.run_fortify_command_for_main("sync", "同步狀態", "sync_status")

    def sync_main_solutions(self):
        """同步負責專案解決方案"""
        self.update_workflow_step_status("sync_solution", "running")
        self.update_report_status("正在同步解決方案...", "info")
        self.run_fortify_command_for_main("solutions", "同步解決方案", "sync_solution")

    def run_main_full_workflow(self):
        """執行負責專案完整工作流程"""
        self.reset_workflow_status()
        self.update_report_status("開始執行完整工作流程...", "info")
        
        # 標記所有步驟為執行中（因為 all 命令會依序執行所有步驟）
        for step_key in ["clone", "download", "process", "sync_status", "sync_solution"]:
            self.update_workflow_step_status(step_key, "running")
            
        self.run_fortify_command_for_main("all", "完整工作流程", "full_workflow")
    
    def append_output(self, text):
        """附加輸出到文字區域"""
        self.output_text.insert(tk.END, f"{text}\n")
        self.output_text.see(tk.END)
        self.root.update_idletasks()
    
    def clear_output(self):
        """清除輸出"""
        self.output_text.delete(1.0, tk.END)
    
    def open_config_file(self):
        """開啟設定檔"""
        try:
            if sys.platform.startswith('win'):
                os.startfile(self.config_file_path)
            else:
                subprocess.run(['xdg-open', self.config_file_path])
        except Exception as e:
            messagebox.showerror("錯誤", f"無法開啟設定檔：{e}")
    
    def set_feature_lock(self, locked: bool):
        """PAT 未設定時鎖定 Pipeline/報告分頁與功能"""
        # Pipeline Tab
        for child in self.pipeline_frame.winfo_children():
            try:
                child.configure(state=tk.DISABLED if locked else tk.NORMAL)
            except Exception:
                pass
        # Report Tab
        for child in self.report_frame.winfo_children():
            try:
                child.configure(state=tk.DISABLED if locked else tk.NORMAL)
            except Exception:
                pass
        # 設定分頁永遠可用
        # Notebook 分頁鎖定（僅允許設定分頁）
        if locked:
            self.notebook.tab(0, state="disabled")
            self.notebook.tab(1, state="disabled")
            self.notebook.tab(2, state="normal")
            self.notebook.select(2)
        else:
            self.notebook.tab(0, state="normal")
            self.notebook.tab(1, state="normal")
            self.notebook.tab(2, state="normal")
    
    def on_pat_changed(self, *args):
        """PAT 內容變更時的處理"""
        pat = self.pat_var.get().strip()
        if pat:
            self.pat_status.config(text="⚠️ PAT 已修改，請點擊「儲存設定」以套用變更", foreground="orange")
        else:
            self.pat_status.config(text="❌ 尚未設定 PAT", foreground="red")
        
        # 即時檢查功能鎖定狀態
        self.set_feature_lock(not bool(pat))
    
    def test_pat_connection(self):
        """測試 PAT 連線"""
        pat = self.pat_var.get().strip()
        if not pat:
            self.pat_status.config(text="❌ 請輸入 PAT", foreground="red")
            return
        
        self.pat_status.config(text="🔄 測試連線中...", foreground="blue")
        
        def test_connection():
            try:
                import requests
                from requests.auth import HTTPBasicAuth
                
                # 測試 Azure DevOps API 連線
                organization = self.config.get("azure_devops.organization", "chte")
                project = self.config.get("azure_devops.project", "fia")
                
                # 使用 Build Definitions API 來測試，這需要 Build (read) 權限
                url = f"https://dev.azure.com/{organization}/{project}/_apis/build/definitions?api-version=6.0&$top=1"
                auth = HTTPBasicAuth('', pat)
                
                response = requests.get(url, auth=auth, timeout=10)
                
                if response.status_code == 200:
                    # 測試成功，儲存到 .env 文件
                    self.save_pat_to_env(pat)
                    self.root.after(0, lambda: self.pat_status.config(
                        text="✅ PAT 測試成功並已儲存", foreground="green"))
                    self.root.after(0, lambda: self.set_feature_lock(False))
                    self.root.after(0, lambda: self.append_output("✅ PAT 測試成功，功能已解鎖"))
                elif response.status_code == 401:
                    self.root.after(0, lambda: self.pat_status.config(
                        text="❌ PAT 無效或已過期", foreground="red"))
                    self.root.after(0, lambda: self.append_output("❌ PAT 無效或已過期，請檢查 PAT 是否正確"))
                elif response.status_code == 403:
                    self.root.after(0, lambda: self.pat_status.config(
                        text="❌ PAT 權限不足", foreground="red"))
                    self.root.after(0, lambda: self.append_output("❌ PAT 權限不足，請確保 PAT 具有 Build (read and execute) 權限"))
                else:
                    error_msg = f"❌ 連線失敗 (HTTP {response.status_code})"
                    self.root.after(0, lambda: self.pat_status.config(text=error_msg, foreground="red"))
                    self.root.after(0, lambda: self.append_output(f"{error_msg}: {response.text[:100]}"))
                    
            except Exception as e:
                error_msg = f"❌ 連線測試失敗: {str(e)}"
                self.root.after(0, lambda: self.pat_status.config(text=error_msg, foreground="red"))
                self.root.after(0, lambda: self.append_output(error_msg))
        
        threading.Thread(target=test_connection, daemon=True).start()
    
    def create_tooltip(self, widget, text):
        """為 widget 建立工具提示"""
        def on_enter(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            
            label = ttk.Label(tooltip, text=text, background="lightyellow", 
                             relief="solid", borderwidth=1, font=("TkDefaultFont", 8))
            label.pack()
            
            widget.tooltip = tooltip
            
        def on_leave(event):
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()
                del widget.tooltip
                
        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)
    
    def update_scan_results(self):
        """更新 Pipeline 掃描結果顯示"""
        self.scan_status_label.config(text="🔄 正在更新掃描結果...")
        
        def update_results():
            try:
                # 清空現有結果
                for item in self.scan_results_tree.get_children():
                    self.scan_results_tree.delete(item)
                
                # 獲取負責專案列表
                main_repos = self.config.get_repos("main")
                if not main_repos:
                    self.root.after(0, lambda: self.scan_status_label.config(text="❌ 沒有設定負責專案"))
                    return
                
                # 導入必要的模組
                from fortify_tool.actions.trigger_pipelines import FortifyPipelineTrigger
                from fortify_tool.actions.fetch_reports import get_latest_build_info
                
                # 初始化 Pipeline 觸發器來獲取 pipeline 資訊
                trigger = FortifyPipelineTrigger()
                pipelines_dict = trigger.discover_fortify_pipelines()
                
                # 轉換為與原來邏輯兼容的格式
                pipelines = []
                for repo_name, pipeline_id in pipelines_dict.items():
                    pipelines.append({
                        "repo_name": repo_name,
                        "pipeline_id": pipeline_id,
                        "pipeline_name": f"{repo_name}-evergreen-fortify"
                    })
                
                pipeline_map = {p["repo_name"]: p for p in pipelines}
                
                results_count = 0
                
                for repo_name in main_repos:
                    if repo_name not in pipeline_map:
                        # 沒有找到對應的 pipeline
                        self.root.after(0, lambda r=repo_name: self.scan_results_tree.insert(
                            "", "end", values=(r, "N/A", "N/A", "無 Pipeline", "N/A")
                        ))
                        continue
                    
                    pipeline = pipeline_map[repo_name]
                    pipeline_id = pipeline["pipeline_id"]
                    
                    # 獲取最新的 build 資訊
                    build_id, result, finish_time = get_latest_build_info(pipeline_id)
                    
                    if build_id:
                        # 獲取建置詳細資訊來取得分支名稱
                        try:
                            import requests
                            from fortify_tool.utils.config_loader import get_config
                            
                            config = get_config()
                            ado_config = config.get_azure_devops_config()
                            organization = ado_config["organization"]
                            project = ado_config["project"]
                            pat = os.getenv("AZURE_DEVOPS_PAT", "")
                            
                            if not pat:
                                self.root.after(0, lambda r=repo_name: self.scan_results_tree.insert(
                                    "", "end", values=(r, "N/A", "N/A", "❌ 無 PAT", "N/A")
                                ))
                                continue
                            
                            import base64
                            auth_string = base64.b64encode(f":{pat}".encode()).decode()
                            headers = {"Authorization": f"Basic {auth_string}"}
                            
                            build_url = f"https://dev.azure.com/{organization}/{project}/_apis/build/builds/{build_id}?api-version=7.0"
                            resp = requests.get(build_url, headers=headers)
                            resp.raise_for_status()
                            
                            build_data = resp.json()
                            branch_name = build_data.get("sourceBranch", "").replace("refs/heads/", "")
                            
                            # 更新快取中的 Pipeline 資訊
                            try:
                                from fortify_tool.utils.cache_manager import get_cache_manager
                                cache_manager = get_cache_manager()
                                
                                pipeline_data = {
                                    "pipeline_id": pipeline_id,
                                    "build_id": build_id,
                                    "result": result,
                                    "finish_time": finish_time,
                                    "source_branch": build_data.get("sourceBranch", ""),
                                    "branch_name": branch_name
                                }
                                
                                cache_manager.update_pipeline_project(repo_name, pipeline_data)
                                cache_manager.update_project_branch_info(repo_name, branch_name, pipeline_id)
                            except Exception as cache_error:
                                print(f"更新快取失敗: {cache_error}")
                            
                            # 格式化時間
                            if finish_time:
                                from datetime import datetime
                                try:
                                    dt = datetime.fromisoformat(finish_time.replace('Z', '+00:00'))
                                    formatted_time = dt.strftime("%Y-%m-%d %H:%M")
                                except:
                                    formatted_time = finish_time
                            else:
                                formatted_time = "N/A"
                            
                            # 格式化結果
                            result_display = {
                                "succeeded": "✅ 成功",
                                "partiallySucceeded": "⚠️ 部分成功", 
                                "failed": "❌ 失敗",
                                "canceled": "⏹️ 取消"
                            }.get(result, result or "未知")
                            
                            self.root.after(0, lambda r=repo_name, t=formatted_time, b=branch_name, res=result_display, bid=build_id: 
                                self.scan_results_tree.insert("", "end", values=(r, t, b, res, bid))
                            )
                            results_count += 1
                            
                        except Exception as e:
                            self.root.after(0, lambda r=repo_name: self.scan_results_tree.insert("", "end", 
                                values=(r, "錯誤", "-", f"查詢失敗: {str(e)}", "N/A")
                            ))
                    else:
                        self.root.after(0, lambda r=repo_name: self.scan_results_tree.insert("", "end", 
                            values=(r, "N/A", "N/A", "無建置記錄", "N/A")
                        ))
                
                self.root.after(0, lambda: self.scan_status_label.config(text=f"✅ 已更新 {results_count} 個專案的掃描結果"))
                
            except Exception as e:
                error_msg = f"❌ 更新失敗: {str(e)}"
                self.root.after(0, lambda msg=error_msg: self.scan_status_label.config(text=msg))
        
        # 在背景執行緒中執行更新
        import threading
        threading.Thread(target=update_results, daemon=True).start()
    
    def view_build_details(self):
        """查看選中的 Build 詳情"""
        selection = self.scan_results_tree.selection()
        if not selection:
            messagebox.showwarning("提醒", "請先選擇一個專案")
            return
        
        item = self.scan_results_tree.item(selection[0])
        values = item['values']
        
        if len(values) < 5:
            messagebox.showerror("錯誤", "無效的選擇")
            return
        
        project_name = values[0]
        build_id = values[4]
        
        if build_id == "N/A" or not build_id:
            messagebox.showinfo("提醒", f"專案 {project_name} 沒有可用的 Build ID")
            return
        
        try:
            # 獲取 Azure DevOps 設定
            ado_config = self.config.get_azure_devops_config()
            organization = ado_config["organization"]
            project = ado_config["project"]
            
            # 構建 Build 詳情 URL
            build_url = f"https://dev.azure.com/{organization}/{project}/_build/results?buildId={build_id}"
            
            # 在瀏覽器中開啟
            import webbrowser
            webbrowser.open(build_url)
            
            self.append_output(f"🌐 已在瀏覽器中開啟 {project_name} 的 Build 詳情頁面")
            
        except Exception as e:
            messagebox.showerror("錯誤", f"無法開啟 Build 詳情: {str(e)}")
    
    def load_scan_results(self):
        """載入掃描結果"""
        self.scan_results_status.config(text="🔄 正在載入掃描結果...")
        
        def load_results():
            try:
                # 導入掃描結果分析器
                from fortify_tool.utils.scan_results_analyzer import get_scan_results_analyzer
                
                analyzer = get_scan_results_analyzer()
                results = analyzer.get_project_scan_results()
                
                # 在主執行緒中更新 UI
                self.root.after(0, lambda: self._update_scan_results_display(results))
                
            except Exception as e:
                error_msg = f"載入掃描結果失敗: {e}"
                self.root.after(0, lambda: self.scan_results_status.config(text=f"❌ {error_msg}"))
                self.root.after(0, lambda: self.append_output(error_msg))
        
        # 在背景執行緒中載入
        import threading
        threading.Thread(target=load_results, daemon=True).start()
    
    def _update_scan_results_display(self, results):
        """更新掃描結果顯示"""
        # 清空現有資料
        for item in self.project_results_tree.get_children():
            self.project_results_tree.delete(item)
        
        for item in self.issue_details_tree.get_children():
            self.issue_details_tree.delete(item)
        
        if not results:
            self.scan_results_status.config(text="📋 沒有找到掃描結果")
            return
        
        # 更新專案結果表格
        for project_name, project_data in results.items():
            branch_info = project_data.get("branch_info", {})
            branch_name = branch_info.get("branch_name", "未知")
            
            self.project_results_tree.insert("", "end", values=(
                project_name,
                project_data["total_issues"],
                project_data["total_sources"],
                project_data["total_sinks"],
                branch_name,
                project_data["scan_time"] or "未知"
            ))
        
        # 儲存結果資料供詳情顯示使用
        self.scan_results_data = results
        
        self.scan_results_status.config(text=f"✅ 已載入 {len(results)} 個專案的掃描結果")
        self.append_output(f"📊 掃描結果載入完成，共 {len(results)} 個專案")
    
    def on_project_select(self, event):
        """當選擇專案時顯示詳細議題"""
        selection = self.project_results_tree.selection()
        if not selection:
            return
        
        # 清空議題詳情
        for item in self.issue_details_tree.get_children():
            self.issue_details_tree.delete(item)
        
        # 取得選中的專案
        item = self.project_results_tree.item(selection[0])
        project_name = item['values'][0]
        
        # 檢查是否有掃描結果資料
        if not hasattr(self, 'scan_results_data') or project_name not in self.scan_results_data:
            return
        
        # 顯示專案的議題詳情
        project_data = self.scan_results_data[project_name]
        issues = project_data["issues"]
        
        # 按總數排序議題
        sorted_issues = sorted(issues.items(), key=lambda x: x[1]["total"], reverse=True)
        
        for issue_type, issue_data in sorted_issues:
            self.issue_details_tree.insert("", "end", values=(
                issue_type,
                issue_data["sources"],
                issue_data["sinks"],
                issue_data["total"]
            ))

    def clear_scan_cache(self):
        """清除掃描結果快取"""
        try:
            from fortify_tool.utils.cache_manager import get_cache_manager
            cache_manager = get_cache_manager()
            cache_manager.clear_cache("scan_results")
            
            self.scan_results_status.config(text="✅ 掃描結果快取已清除")
            self.append_output("🗑️ 掃描結果快取已清除")
            
            # 清空顯示
            for item in self.project_results_tree.get_children():
                self.project_results_tree.delete(item)
            for item in self.issue_details_tree.get_children():
                self.issue_details_tree.delete(item)
                
        except Exception as e:
            error_msg = f"清除快取失敗: {e}"
            self.scan_results_status.config(text=f"❌ {error_msg}")
            self.append_output(error_msg)
    
    def force_reload_scan_results(self):
        """強制重新載入掃描結果（不使用快取）"""
        self.scan_results_status.config(text="🔄 正在強制重新載入...")
        
        def force_load_results():
            try:
                from fortify_tool.utils.scan_results_analyzer import get_scan_results_analyzer
                
                analyzer = get_scan_results_analyzer()
                # 強制不使用快取
                results = analyzer.get_project_scan_results(use_cache=False)
                
                self.root.after(0, lambda: self._update_scan_results_display(results))
                
            except Exception as e:
                error_msg = f"強制載入掃描結果失敗: {e}"
                self.root.after(0, lambda: self.scan_results_status.config(text=f"❌ {error_msg}"))
                self.root.after(0, lambda: self.append_output(error_msg))
        
        import threading
        threading.Thread(target=force_load_results, daemon=True).start()

    def _load_pipeline_cache_to_treeview(self, main_repos):
        """載入 Pipeline 快取資料到 Treeview"""
        try:
            from fortify_tool.utils.cache_manager import get_cache_manager
            cache_manager = get_cache_manager()
            
            for repo in main_repos:
                pipeline_data = cache_manager.get_project_pipeline_info(repo)
                
                if pipeline_data:
                    build_id = pipeline_data.get("build_id", "N/A")
                    result = pipeline_data.get("result", "N/A")
                    finish_time = pipeline_data.get("finish_time", "N/A")
                    # 修正分支名稱讀取
                    branch_name = pipeline_data.get("source_branch", "N/A")
                    if branch_name and branch_name.startswith("refs/heads/"):
                        branch_name = branch_name.replace("refs/heads/", "")
                    
                    # 格式化時間
                    if finish_time:
                        from datetime import datetime
                        try:
                            dt = datetime.fromisoformat(finish_time.replace('Z', '+00:00'))
                            formatted_time = dt.strftime("%Y-%m-%d %H:%M")
                        except:
                            formatted_time = finish_time
                    else:
                        formatted_time = "N/A"
                    
                    # 格式化結果
                    result_display = {
                        "succeeded": "✅ 成功",
                        "partiallySucceeded": "⚠️ 部分成功", 
                        "failed": "❌ 失敗",
                        "canceled": "⏹️ 取消"
                    }.get(result, result or "未知")
                    
                    self.scan_results_tree.insert("", "end", values=(
                        repo,
                        formatted_time,
                        branch_name,
                        result_display,
                        build_id
                    ))
                else:
                    self.scan_results_tree.insert("", "end", values=(
                        repo,
                        "N/A",
                        "N/A",
                        "無快取資料",
                        "N/A"
                    ))
        except Exception as e:
            print(f"載入 Pipeline 快取資料失敗: {e}")

    def update_workflow_step_status(self, step_key, status, message=None):
        """更新工作流程步驟狀態
        
        Args:
            step_key: 步驟鍵值 (clone, download, process, sync_status, sync_solution)
            status: 狀態 (pending, running, success, failed)
            message: 可選的額外訊息
        """
        if step_key not in self.workflow_steps:
            return
            
        step_info = self.workflow_steps[step_key]
        step_info["status"] = status
        
        # 狀態圖示和顏色映射
        status_config = {
            "pending": {"icon": "⏳", "text": "待執行", "color": "gray"},
            "running": {"icon": "🔄", "text": "執行中", "color": "blue"},
            "success": {"icon": "✅", "text": "完成", "color": "green"},
            "failed": {"icon": "❌", "text": "失敗", "color": "red"}
        }
        
        config = status_config.get(status, status_config["pending"])
        display_text = f"{step_info['name']}: {config['icon']} {config['text']}"
        
        if message:
            display_text += f" - {message}"
            
        # 更新標籤
        if step_info["label"]:
            step_info["label"].config(text=display_text, foreground=config["color"])

    def update_report_status(self, message, status_type="info"):
        """更新主要狀態訊息
        
        Args:
            message: 狀態訊息
            status_type: 訊息類型 (info, success, warning, error)
        """
        color_map = {
            "info": "blue",
            "success": "green", 
            "warning": "orange",
            "error": "red"
        }
        
        icon_map = {
            "info": "💡",
            "success": "✅",
            "warning": "⚠️", 
            "error": "❌"
        }
        
        color = color_map.get(status_type, "blue")
        icon = icon_map.get(status_type, "💡")
        
        self.report_status_label.config(text=f"{icon} {message}", foreground=color)

    def reset_workflow_status(self):
        """重置所有工作流程步驟狀態"""
        for step_key in self.workflow_steps:
            self.update_workflow_step_status(step_key, "pending")
        self.update_report_status("請選擇要執行的處理步驟", "info")

    def mark_all_steps_complete(self):
        """標記所有步驟為完成狀態"""
        for step_key in self.workflow_steps:
            self.update_workflow_step_status(step_key, "success")

    def mark_all_steps_failed(self):
        """標記所有步驟為失敗狀態"""
        for step_key in self.workflow_steps:
            self.update_workflow_step_status(step_key, "failed")

    def test_pat_connection(self):
        """測試 PAT 連線"""
        pat = self.pat_var.get().strip()
        if not pat:
            self.pat_status.config(text="❌ 請輸入 PAT", foreground="red")
            return
        
        self.pat_status.config(text="🔄 測試連線中...", foreground="blue")
        
        def test_connection():
            try:
                import requests
                from requests.auth import HTTPBasicAuth
                
                # 測試 Azure DevOps API 連線
                organization = self.config.get("azure_devops.organization", "chte")
                project = self.config.get("azure_devops.project", "fia")
                
                # 使用 Build Definitions API 來測試，這需要 Build (read) 權限
                url = f"https://dev.azure.com/{organization}/{project}/_apis/build/definitions?api-version=6.0&$top=1"
                auth = HTTPBasicAuth('', pat)
                
                response = requests.get(url, auth=auth, timeout=10)
                
                if response.status_code == 200:
                    # 測試成功，儲存到 .env 文件
                    self.save_pat_to_env(pat)
                    self.root.after(0, lambda: self.pat_status.config(
                        text="✅ PAT 測試成功並已儲存", foreground="green"))
                    self.root.after(0, lambda: self.set_feature_lock(False))
                    self.root.after(0, lambda: self.append_output("✅ PAT 測試成功，功能已解鎖"))
                elif response.status_code == 401:
                    self.root.after(0, lambda: self.pat_status.config(
                        text="❌ PAT 無效或已過期", foreground="red"))
                    self.root.after(0, lambda: self.append_output("❌ PAT 無效或已過期，請檢查 PAT 是否正確"))
                elif response.status_code == 403:
                    self.root.after(0, lambda: self.pat_status.config(
                        text="❌ PAT 權限不足", foreground="red"))
                    self.root.after(0, lambda: self.append_output("❌ PAT 權限不足，請確保 PAT 具有 Build (read and execute) 權限"))
                else:
                    error_msg = f"❌ 連線失敗 (HTTP {response.status_code})"
                    self.root.after(0, lambda: self.pat_status.config(text=error_msg, foreground="red"))
                    self.root.after(0, lambda: self.append_output(f"{error_msg}: {response.text[:100]}"))
                    
            except Exception as e:
                error_msg = f"❌ 連線測試失敗: {str(e)}"
                self.root.after(0, lambda: self.pat_status.config(text=error_msg, foreground="red"))
                self.root.after(0, lambda: self.append_output(error_msg))
        
        threading.Thread(target=test_connection, daemon=True).start()
    
    def on_pat_changed(self, *args):
        """PAT 輸入變更時的處理"""
        pat = self.pat_var.get().strip()
        if pat:
            self.pat_status.config(text="💡 請點擊「測試連線」來驗證 PAT", foreground="blue")
        else:
            self.pat_status.config(text="❌ 尚未設定 PAT", foreground="red")
            self.set_feature_lock(True)
    
    def save_pat_to_env(self, pat):
        """儲存 PAT 到 .env 文件"""
        try:
            env_file = Path(__file__).parent / ".env"
            
            # 讀取現有的 .env 內容
            env_lines = []
            if env_file.exists():
                with open(env_file, 'r', encoding='utf-8') as f:
                    env_lines = f.readlines()
            
            # 更新或添加 AZURE_DEVOPS_PAT
            pat_found = False
            for i, line in enumerate(env_lines):
                if line.strip().startswith('AZURE_DEVOPS_PAT='):
                    env_lines[i] = f'AZURE_DEVOPS_PAT={pat}\n'
                    pat_found = True
                    break
            
            if not pat_found:
                env_lines.append(f'AZURE_DEVOPS_PAT={pat}\n')
            
            # 寫回 .env 文件
            with open(env_file, 'w', encoding='utf-8') as f:
                f.writelines(env_lines)
            
            # 更新環境變數
            import os
            os.environ['AZURE_DEVOPS_PAT'] = pat
            
        except Exception as e:
            print(f"警告：儲存 PAT 到 .env 時發生錯誤: {e}")
            raise


def main():
    """主程式入口"""
    root = tk.Tk()
    app = FortifyGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
