## 自動修復執行記錄

### 執行時間：{當前時間}

#### 處理結果摘要
- 總專案數：{數量}
- 成功修復專案數：{數量}
- 跳過專案數：{數量}

#### 詳細結果

##### 專案：{專案名稱}
- 狀態：✅ 成功修復 / ⚠️ 部分修復 / ❌ 跳過
- 處理的問題：
  - ✅ {問題名稱} - 已修復並提交
  - 👤 {問題名稱} - 使用者拒絕修復
  - ⚠️ {問題名稱} - 部分 Source 無法修復
  - ❌ {問題名稱} - 無適用解決方案

##### 專案：{下一個專案名稱}
...

## 2025-08-05 Fortify 問題現況分類與修復狀態

### imc 專案
- 001_System_Information_Leak_External.md：**不可修復**（用戶明確指示跳過，無有效修復方案）
- 002_Path_Manipulation.md：**不可修復**（多次嘗試均未通過 Fortify，已暫停修復，待官方指引）
- 003_SQL_Injection.md：**需進一步確認**（若已參數化查詢則可視為已修復，否則需檢查共筆/SDT_Fortify.md 是否有可行建議）

### ina 專案
- 001_Path_Manipulation.md：**不可修復**（所有常見修復未被 Fortify 接受，已記錄）
- 002_Cross-Site_Scripting_Reflected.md：**進行修復中**（依據共筆與 SDT_Fortify.md，優先採用 HTML encode/escape 等修正）
- 003_System_Information_Leak_External.md：**需進一步確認**（若有明確修復建議則可修復，否則需檢查共筆/SDT_Fortify.md 是否有記錄）

> 本分類依據：Issue修復共筆、SDT_Fortify.md、用戶指示與實際修復經驗。Path Manipulation 類型問題已明確標註不可修復，其餘問題依據共筆內容持續追蹤與更新。

### 已確認無解的問題類型

#### Path Manipulation (Critical)
**狀態**：目前無解 (2025-08-05 確認)

**問題描述**：
- Fortify 檢測到攻擊者可控制 `File()` 的檔案系統路徑參數
- 允許攻擊者存取或修改受保護的檔案

**已嘗試但失敗的修復方法**：
1. ❌ **LocaleConvertUtilsBean.convert()** - Fortify 不認可此方法為有效的路徑安全化
2. ❌ **白名單檔案名稱驗證** - 使用正則表達式 `^[a-zA-Z0-9._-]+$` 等模式，Fortify 仍報告漏洞
3. ❌ **自定義 safeFileName() 方法** - 包含中文字符的白名單驗證，Fortify 無法追蹤間接驗證
4. ❌ **路徑遍歷檢查** - 明確檢查 `..` 和目錄前綴，Fortify 仍無法識別

**影響專案**：
- `imc` 專案：`IMC702WController.java:455` - `new File(filePath, name)`
- `ina` 專案：`INA722WController.java:219` 等多處 - 10 個程式碼位置

**根本原因**：
- Fortify 對 Path Manipulation 的檢測極其嚴格
- 無法識別自定義的安全驗證方法
- 需要使用 Fortify 明確認可的官方安全 API

**建議處理方式**：
- 暫停修復嘗試，避免無效的程式碼變更
- 等待修復團隊討論結果並更新到修復共筆內
