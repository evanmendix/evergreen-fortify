#!/usr/bin/env python3
"""
測試快取功能腳本
"""

import sys
from pathlib import Path

# 添加 src 目錄到 Python 路徑
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

from fortify_tool.utils.cache_manager import get_cache_manager
from fortify_tool.utils.scan_results_analyzer import get_scan_results_analyzer

def test_cache_functionality():
    """測試快取功能"""
    print("=== 測試快取功能 ===")
    
    # 1. 測試 Cache Manager
    print("\n1. 測試 Cache Manager...")
    cache_manager = get_cache_manager()
    print(f"   ✅ Cache 目錄: {cache_manager.cache_dir}")
    
    # 2. 測試掃描結果載入
    print("\n2. 測試掃描結果載入...")
    analyzer = get_scan_results_analyzer()
    
    # 強制重新掃描（不使用快取）
    print("   🔄 強制重新掃描...")
    results = analyzer.get_project_scan_results(use_cache=False)
    print(f"   ✅ 找到 {len(results)} 個專案的掃描結果")
    
    # 顯示專案詳情
    for project_name, project_data in results.items():
        branch_info = project_data.get("branch_info", {})
        print(f"   📋 {project_name}:")
        print(f"      - 議題數量: {project_data['total_issues']}")
        print(f"      - Source 數量: {project_data['total_sources']}")
        print(f"      - Sink 數量: {project_data['total_sinks']}")
        print(f"      - 掃描分支: {branch_info.get('branch_name', '未知')}")
        print(f"      - 處理時間: {project_data.get('scan_time', '未知')}")
    
    # 3. 測試快取載入
    print("\n3. 測試快取載入...")
    cached_results = analyzer.get_project_scan_results(use_cache=True)
    print(f"   ✅ 從快取載入 {len(cached_results)} 個專案")
    
    # 4. 測試 Pipeline 快取
    print("\n4. 測試 Pipeline 快取...")
    pipeline_cache = cache_manager.load_pipeline_cache()
    print(f"   📊 Pipeline 快取: {len(pipeline_cache.get('projects', {}))} 個專案")
    
    # 5. 測試分支資訊快取
    print("\n5. 測試分支資訊快取...")
    branch_cache = cache_manager.load_branch_info_cache()
    print(f"   🌿 分支資訊快取: {len(branch_cache.get('projects', {}))} 個專案")
    
    print("\n=== 測試完成 ===")

if __name__ == "__main__":
    test_cache_functionality()
