import os
import re
import glob
import shutil
import fitz  # PyMuPDF
from collections import defaultdict
from ..utils.get_filepath import REPORTS_DIR
from datetime import datetime

# Determine the project root dynamically
# Assuming the script is in src/fortify_tool/actions/
# Project root is 4 levels up from this file.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '..', ))


def clean_filename(text):
    """
    將文字轉換為合法的檔案名稱。
    """
    cleaned = re.sub(r'[\\/*?:"<>|]', '', text)
    cleaned = re.sub(r'\s+', '_', cleaned)
    cleaned = re.sub(r'_+', '_', cleaned)
    cleaned = cleaned.strip('_')
    return cleaned[:100] if len(cleaned) > 100 else cleaned


def format_content_for_markdown(text):
    """
    使用狀態機尋找 'Source:' 或 'Sink:' 後的文字區塊，並用 Markdown 程式碼圍欄包覆。
    """
    lines = text.split('\n')
    processed_lines = []
    in_code_block = False
    for line in lines:
        stripped_line = line.strip()
        if stripped_line.startswith('Source:') or stripped_line.startswith('Sink:'):
            if in_code_block:
                processed_lines.append('```')
            processed_lines.append(line)
            processed_lines.append('```')
            in_code_block = True
        elif stripped_line == '' and in_code_block:
            processed_lines.append('```')
            processed_lines.append(line)
            in_code_block = False
        else:
            processed_lines.append(line)
    if in_code_block:
        processed_lines.append('```')
    return '\n'.join(processed_lines)


def clean_category_content(text):
    """
    清理從 PDF 提取出的單一 Category 內容，移除頁首、頁尾、附錄及不必要的圖表/統計數字。
    """
    # 移除附錄之後的所有內容
    appendix_keywords = ['依據類別排序列出問題', '檢測總檔案數', '掃描檔案清單']
    for keyword in appendix_keywords:
        if keyword in text:
            text = text.split(keyword)[0]

    lines = text.split('\n')
    cleaned_lines = []

    # Regex to detect and remove lines that are likely artifacts from charts or tables.
    chart_data_pattern = re.compile(
        r'^\s*(\d+\s*)+$|'  # e.g., "10", "0 5 10"
        r'^\s*(Critical|High|Medium|Low)\s*$|'  # e.g., "Critical"
        r'.*Issues\s+Found.*'  # e.g., "Issues Found" table header
    )

    for line in lines:
        # 移除頁首/頁尾
        if 'FIA_Fortify_Summary_Report' in line or '程式碼安全檢測' in line:
            continue
        # 移除頁碼
        if re.match(r'^\s*Page \d+ of \d+\s*$', line.strip()):
            continue

        # 移除圖表/統計行
        if chart_data_pattern.match(line.strip()):
            continue

        # 從主要 Category 標題中移除問題計數，例如 " (1 Issues, 1 High)"
        if line.strip().startswith('Category:'):
            line = re.sub(r'\s*\(\d+\s+Issues?.*?\)\s*$', '', line)

        cleaned_lines.append(line)

    cleaned_text = '\n'.join(cleaned_lines)

    # 移除連續的空行，保持報告整潔
    cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)

    return cleaned_text.strip()


def load_solutions(solutions_dir='data/solutions'):
    """
    從指定目錄載入所有解決方案檔案，區分通用解法與專屬解法。
    - 通用解法：以嚴重性 (如 'critical') 為鍵。
    - 專屬解法：以標準化的弱點名稱 (如 'Cross-Site_Scripting_DOM') 為鍵，值為包含內容和嚴重性的字典。
    返回兩個字典: generic_solutions, specific_solutions
    """
    generic_solutions = {}
    specific_solutions = {}
    if not os.path.isdir(solutions_dir):
        print(f"[WARN] 找不到解決方案目錄: '{solutions_dir}'")
        return generic_solutions, specific_solutions

    print(f"\n--- 正在從 '{solutions_dir}' 載入解決方案 ---")
    for filename in os.listdir(solutions_dir):
        if not filename.endswith('.md'):
            continue

        # 1. 處理通用解法 (依嚴重等級)
        severity_match = re.search(r'Fortify (\w+) Solution\.md', filename, re.IGNORECASE)
        if not severity_match:
            continue

        severity = severity_match.group(1).lower()
        filepath = os.path.join(solutions_dir, filename)

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            # 2. 處理專屬解法 (依 ## 標題)
            # 使用正規表示式分割，保留分隔符 (## ...)
            parts = re.split(r'(\n## .+)', content)

            # 第一部分是通用解法內容 (在第一個 ## 之前)
            if parts and parts[0].strip():
                generic_solutions[severity] = parts[0].strip()
                print(f"  [INFO] 已載入 '{severity}' 等級的通用解決方案。")

            # 處理後續的專屬解法部分
            # parts 結構: [通用, ## 標題1, 內容1, ## 標題2, 內容2, ...]
            specific_issues_found = 0
            for i in range(1, len(parts), 2):
                header = parts[i].strip()
                body = parts[i + 1].strip() if (i + 1) < len(parts) else ""

                # 從 '## Cross-Site Scripting: DOM' 提取 'Cross-Site Scripting: DOM'
                issue_name = header.lstrip('# ').strip()
                normalized_name = clean_filename(issue_name)

                # 將標題和內容重新組合，並儲存嚴重性
                specific_solutions[normalized_name] = {
                    "content": f"{header}\n\n{body}",
                    "severity": severity
                }
                specific_issues_found += 1

            if specific_issues_found > 0:
                print(f"    -> 在 '{filename}' 中找到並載入 {specific_issues_found} 個 '{severity}' 等級的專屬解法。")

        except Exception as e:
            print(f"  [WARN] 讀取解決方案檔案 '{filename}' 失敗: {e}")

    return generic_solutions, specific_solutions


def get_severity_from_header(header_line):
    """
    從 Category 標題行中提取最高嚴重等級。
    例如：'Category: ... (1 Issues, 1 High)' -> 'high'
    """
    severities = ['critical', 'high', 'medium', 'low']
    header_lower = header_line.lower()
    for severity in severities:
        if f" {severity}" in header_lower:
            return severity
    return None


def append_solution_to_file(file_path, solution_content):
    """
    將解決方案內容附加到指定的 Markdown 檔案末尾。
    """
    try:
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write('\n\n---\n')
            f.write('# 通用解決方案建議\n\n')
            f.write(solution_content)
        return True
    except IOError as e:
        print(f"    [ERROR] 附加解決方案到 '{os.path.basename(file_path)}' 失敗: {e}")
        return False


def process_pdf_file(pdf_path, generic_solutions, specific_solutions):
    """處理單一 PDF，拆分報告並附加解決方案。"""
    pdf_filename = os.path.basename(pdf_path)
    project_name, _ = os.path.splitext(pdf_filename)
    print(f"--- 開始處理專案: {project_name} (來源: {pdf_filename}) ---")

    output_dir = os.path.join(PROJECT_ROOT, '產出資料', 'Fortify報告整理', 'repo拆分報告', project_name)

    if os.path.isdir(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)

    try:
        print(f"  [INFO] 正在讀取 PDF: {pdf_filename}")
        doc = fitz.open(pdf_path)
        full_text = "".join([page.get_text("text") for page in doc])
        doc.close()
        print(f"  [INFO] PDF 讀取完成。")

        category_pattern = r'(Category: .+?(\d+ Issues?).*?)(?=Category: |\Z)'
        matches = list(re.finditer(category_pattern, full_text, re.DOTALL))

        if not matches:
            print("  [WARN] 在 PDF 中找不到任何 'Category:' 標籤，專案可能已完全修復。")
            # 建立狀態說明檔案
            status_file_path = os.path.join(output_dir, "00_專案狀態.md")
            status_content = f"""# {project_name} - 專案狀態

## 🎉 恭喜！此專案已完全修復

根據最新的 Fortify 掃描報告，此專案目前**沒有任何安全性問題**。

- **狀態**: ✅ 已完全修復
- **最後更新**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **說明**: 在最新的 Fortify 報告中未發現任何 Category 標籤，表示所有先前的安全性問題都已得到解決。

---

> [!SUCCESS]
> 此專案已達到安全性合規標準，無需進一步的修復工作。
"""
            with open(status_file_path, 'w', encoding='utf-8') as f:
                f.write(status_content)
            
            print(f"  [SUCCESS] 已建立專案狀態說明檔案: {os.path.basename(status_file_path)}")
            return {"project_name": project_name, "status": "fully_remediated", "issues_count": 0}

        print(f"  [INFO] 找到 {len(matches)} 個問題類別，開始寫入檔案...")
        files_processed_count = 0
        issue_summary_data = []
        for i, match in enumerate(matches, 1):
            category_content = match.group(1).strip()
            header_line = category_content.split('\n', 1)[0]
            title_match = re.search(r'Category: (.+?)\s*\(', header_line)
            category_name = title_match.group(1).strip() if title_match else f"Unknown_Category_{i}"

            filename = clean_filename(f"{i:03d}_{category_name}.md")
            output_path = os.path.join(output_dir, filename)

            cleaned_content = clean_category_content(category_content)
            formatted_content = format_content_for_markdown(cleaned_content)

            # Count occurrences of Source and Sink to give a summary
            source_count = formatted_content.count('Source:')
            sink_count = formatted_content.count('Sink:')
            total_locations = source_count + sink_count

            # Create a summary line to show how many code locations need review
            if total_locations > 0:
                summary_line = f"> [!NOTE]\n> This report identifies **{total_locations}** code location(s) for review ({source_count} Source(s), {sink_count} Sink(s)).\n\n"
                final_content = summary_line + formatted_content
            else:
                final_content = formatted_content

            with open(output_path, 'w', encoding='utf-8') as out_f:
                out_f.write(final_content)

            # 附加解決方案 (新邏輯：優先專屬，後備通用)
            category_name_match = re.search(r'Category: (.+?)\s*\(', header_line)
            category_name = category_name_match.group(1).strip() if category_name_match else ""
            normalized_name = clean_filename(category_name)

            solution_to_append = None
            solution_type = ""

            # 1. 優先查找專屬解法
            if normalized_name in specific_solutions:
                solution_info = specific_solutions[normalized_name]
                solution_to_append = solution_info["content"]
                severity = solution_info["severity"]
                solution_type = f"專屬解法 (來源: {severity.capitalize()})"

            # 2. 若無專屬解法，查找通用解法
            else:
                severity = get_severity_from_header(header_line)
                if severity and severity in generic_solutions:
                    solution_to_append = generic_solutions[severity]
                    solution_type = f"通用解法 (來源: {severity.capitalize()})"

            if solution_to_append:
                if append_solution_to_file(output_path, solution_to_append):
                    print(f"    -> 已附加 {solution_type}。")
                    solution_status = solution_type
                else:
                    print(f"    -> ({i}/{len(matches)}) 已寫入 '{filename}' (解法附加失敗)")
                    solution_status = "解法附加失敗"
            else:
                print(f"    -> ({i}/{len(matches)}) 已寫入 '{filename}' (無對應解法)")
                solution_status = "無對應解法"

            issue_summary_data.append({
                "index": i,
                "category_name": category_name,
                "solution_status": solution_status
            })
            files_processed_count += 1

        print(f"[SUCCESS] 專案 '{project_name}' 處理完成！總共產出 {files_processed_count} 個問題檔案。")

        # 新增：生成並儲存問題摘要報告
        summary_filename = f"{project_name}_issue_summary.md"
        summary_filepath = os.path.join(output_dir, summary_filename)

        summary_content = f"# {project_name} Fortify 問題摘要報告\n\n"
        summary_content += "## 問題列表與解決方案狀態\n\n"
        summary_content += "| 序號 | 問題類別 | 解決方案狀態 |\n"
        summary_content += "|---|---|---|\n"
        for item in issue_summary_data:
            summary_content += f"| {item['index']} | {item['category_name']} | {item['solution_status']} |\n"

        summary_content += "\n## 說明\n"
        summary_content += "- **解決方案狀態** 顯示該問題是否在公共筆記中找到對應的解決方案。\n"
        summary_content += "- **專屬解法** 表示找到針對該特定問題的解決方案，並標示其來源嚴重等級。\n"
        summary_content += "- **通用解法** 表示找到針對該問題嚴重等級的通用解決方案。\n"
        summary_content += "- **無對應解法** 表示在公共筆記中未找到針對該問題的解決方案。\n"

        with open(summary_filepath, 'w', encoding='utf-8') as f:
            f.write(summary_content)
        print(f"  [INFO] 已生成問題摘要報告: {summary_filepath}")

        return {"project_name": project_name, "issues": issue_summary_data}

    except Exception as e:
        print(f"\n  [ERROR] 處理 PDF '{pdf_filename}' 過程中發生未預期錯誤: {e}")
        return None


def generate_global_summary(all_projects_data):
    """
    根據所有專案的資料，生成一份全域的問題摘要報告。
    """
    print("\n--- 正在生成 FIA 全域 Fortify 問題摘要報告 ---")

    # 使用 defaultdict 簡化統計邏輯
    # 結構: { 'category_name': {'count': 1, 'projects': {'proj1', 'proj2'}, 'solution': 'status'} }
    global_summary = defaultdict(lambda: {'count': 0, 'projects': set(), 'solution': '無對應解法'})

    # 定義解決方案狀態的優先級
    solution_priority = {
        "解法附加失敗": 0,
        "無對應解法": 1,
        "通用解法": 2,
        "專屬解法": 3
    }

    for project_data in all_projects_data:
        project_name = project_data['project_name']
        for issue in project_data.get('issues', []):
            category = issue['category_name']

            # 更新統計數據
            global_summary[category]['count'] += 1
            global_summary[category]['projects'].add(project_name)

            # 更新解決方案狀態 (取最高優先級的)
            current_solution_status = global_summary[category]['solution']
            new_solution_status = issue['solution_status']

            # 提取狀態關鍵字 (專屬/通用/無)
            current_key = current_solution_status.split(' ')[0]
            new_key = new_solution_status.split(' ')[0]

            if solution_priority.get(new_key, 0) > solution_priority.get(current_key, 0):
                global_summary[category]['solution'] = new_solution_status

    if not global_summary:
        print("[INFO] 沒有可供分析的資料，不生成全域報告。")
        return

    # 準備 Markdown 報告內容
    report_path = os.path.join(PROJECT_ROOT, '產出資料', 'Fortify報告整理', 'fia_fortify_issue_summary.md')

    content = "# FIA Fortify 問題總結報告\n\n"
    content += "此報告統整所有已分析專案的 Fortify 安全問題，提供一個高層次的風險概覽。\n\n"
    content += "## 問題類別統計\n\n"
    content += "| 問題類別 (Category) | 出現總次數 | 受影響專案 | 解決方案狀態 |\n"
    content += "|---|---|---|---|\n"

    # 根據出現次數排序
    sorted_summary = sorted(global_summary.items(), key=lambda item: item[1]['count'], reverse=True)

    for category, data in sorted_summary:
        projects_str = ", ".join(sorted(list(data['projects'])))
        content += f"| {category} | {data['count']} | {projects_str} | {data['solution']} |\n"

    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[SUCCESS] 全域摘要報告已成功生成於: {report_path}")
    except IOError as e:
        print(f"[ERROR] 無法寫入全域摘要報告: {e}")


def process_local_pdfs():
    """主執行函式：掃描PDF，拆分報告，附加解決方案，並生成全域總結。"""
    root_dir = REPORTS_DIR
    print("=== Fortify 報告全自動處理腳本啟動 ===")

    if not os.path.isdir(root_dir):
        print(f"[ERROR] 找不到來源目錄 '{root_dir}'，請確認執行路徑是否正確。")
        return

    pdf_files = glob.glob(os.path.join(root_dir, '**', '*.pdf'), recursive=True)
    if not pdf_files:
        print(f"[INFO] 在 '{root_dir}' 目錄下找不到任何 PDF 檔案。")
        return

    print(f"在 '{root_dir}' 中找到 {len(pdf_files)} 個 PDF，準備處理...")
    print("[INFO]    # 步驟 1: 載入通用與專屬解決方案")
    generic_solutions, specific_solutions = load_solutions(os.path.join(PROJECT_ROOT, '產出資料', 'Issue修復共筆'))
    if not generic_solutions and not specific_solutions:
        print("[INFO] 未載入任何解決方案，將僅執行報告拆分。")
    else:
        print("[INFO] 解決方案載入完成.\n")

    all_projects_data = []
    for pdf_path in pdf_files:
        project_data = process_pdf_file(pdf_path, generic_solutions, specific_solutions)
        if project_data:
            all_projects_data.append(project_data)
        print("--- 專案處理完畢 ---\n")

    generate_global_summary(all_projects_data)
    print("=== 所有 PDF 報告處理完成 ===")


if __name__ == "__main__":
    process_local_pdfs()