import os
import re
import sys

import requests
from ..utils.get_filepath import SOLUTIONS_DIR


def sync_hackmd_to_md(url, output_dir, filename):
    """
    Downloads a HackMD note and saves it as a local Markdown file.
    """
    print("=== 開始同步 HackMD 解決方案指南 ===")

    # 1. 準備下載 URL 和輸出路徑
    download_url = f"{url}/download"
    output_path = os.path.join(output_dir, filename)

    print(f"  [INFO] 準備從: {url}")
    print(f"  [INFO] 儲存至: {output_path}")

    # 2. 建立輸出目錄 (如果不存在)
    try:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"  [INFO] 已建立目錄: {output_dir}")
    except Exception as e:
        print(f"  [ERROR] 建立目錄 '{output_dir}' 失敗: {e}", file=sys.stderr)
        return

    # 3. 下載內容
    try:
        print("  [INFO] 正在下載內容...")
        response = requests.get(download_url, timeout=15)
        response.raise_for_status()  # 如果 HTTP 狀態碼是 4xx 或 5xx，則拋出異常
        content = response.text
        print("  [SUCCESS] 內容下載成功。")
    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] 下載 HackMD 內容失敗: {e}", file=sys.stderr)
        return

    # 4. 寫入檔案
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  [SUCCESS] 已成功將解決方案指南儲存至 '{output_path}'")
    except Exception as e:
        print(f"  [ERROR] 寫入檔案失敗: {e}", file=sys.stderr)
        return

    print("=== 同步完成 ===")


def main():
    """
    主執行函式，定義所有解決方案文件並逐一同步。
    """
    solutions = {
        "Fortify Critical Solution": "https://hackmd.io/4wfKm4XfQD2V9YSA9ng5qw",
        "Fortify High Solution": "https://hackmd.io/Ko6tCMQqTi6z7SlcvGxjTg",
        "Fortify Medium Solution": "https://hackmd.io/C5ZECnJdQbGwKwUOAMU3tw",
        "Fortify Low Solution": "https://hackmd.io/tbNWu10NSISEmrZ_Kz6KXg",
        "Fortify Others Solution": "https://hackmd.io/4AfMfC7FS1ygUixs7FEp-Q"
    }

    output_dir = SOLUTIONS_DIR

    for name, url in solutions.items():
        filename = f"{name}.md"
        sync_hackmd_to_md(url, output_dir, filename)
        print("-" * 40)  # 分隔線


if __name__ == "__main__":
    main()
