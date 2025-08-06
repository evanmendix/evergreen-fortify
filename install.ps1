# Fortify 報告處理工具 - PowerShell 安裝腳本
# 適用於 Windows PowerShell 5.0+ 和 PowerShell Core 6.0+

param(
    [switch]$SkipPythonCheck,
    [switch]$Force
)

# 設定控制台編碼
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Fortify 報告處理工具 - 安裝程式" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 函數：檢查命令是否存在
function Test-Command {
    param($Command)
    try {
        Get-Command $Command -ErrorAction Stop | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

# 函數：顯示錯誤訊息並退出
function Show-Error {
    param($Message, $Solutions = @())
    Write-Host "❌ $Message" -ForegroundColor Red
    Write-Host ""
    if ($Solutions.Count -gt 0) {
        Write-Host "📋 解決方案：" -ForegroundColor Yellow
        foreach ($solution in $Solutions) {
            Write-Host "   • $solution" -ForegroundColor Yellow
        }
        Write-Host ""
    }
    Read-Host "按 Enter 鍵退出"
    exit 1
}

# 1. 檢查 Python
Write-Host "[1/5] 檢查 Python 環境..." -ForegroundColor Green

if (-not $SkipPythonCheck) {
    if (-not (Test-Command "python")) {
        Show-Error "未偵測到 Python！" @(
            "前往 https://www.python.org/downloads/ 下載最新版本",
            "安裝時請勾選 'Add Python to PATH'",
            "建議安裝 Python 3.8 或更新版本",
            "安裝完成後重新執行此腳本"
        )
    }
    
    $pythonVersion = python --version 2>&1
    Write-Host "✅ $pythonVersion 已安裝" -ForegroundColor Green
    
    # 檢查 Python 版本
    $versionMatch = $pythonVersion -match "Python (\d+)\.(\d+)"
    if ($versionMatch) {
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 8)) {
            Write-Host "⚠️  建議使用 Python 3.8 或更新版本" -ForegroundColor Yellow
        }
    }
}

# 2. 檢查 pip
Write-Host ""
Write-Host "[2/5] 檢查 pip 套件管理工具..." -ForegroundColor Green

if (-not (Test-Command "pip")) {
    Show-Error "pip 不可用！" @(
        "執行：python -m ensurepip --upgrade",
        "或重新安裝 Python 並確保包含 pip",
        "檢查 Python 安裝是否完整"
    )
}

$pipVersion = pip --version 2>&1
Write-Host "✅ pip 可正常使用" -ForegroundColor Green

# 3. 檢查並安裝 uv
Write-Host ""
Write-Host "[3/5] 檢查 uv 套件管理工具..." -ForegroundColor Green

if (-not (Test-Command "uv")) {
    Write-Host "⚠️  未偵測到 uv，正在安裝..." -ForegroundColor Yellow
    try {
        pip install uv
        Write-Host "✅ uv 安裝成功" -ForegroundColor Green
    }
    catch {
        Show-Error "uv 安裝失敗！" @(
            "檢查網路連線",
            "手動執行：pip install uv",
            "確認防火牆設定允許 Python 存取網路"
        )
    }
} else {
    Write-Host "✅ uv 已安裝" -ForegroundColor Green
}

# 4. 檢查專案檔案
Write-Host ""
Write-Host "[4/5] 檢查專案檔案..." -ForegroundColor Green

if (-not (Test-Path "pyproject.toml")) {
    Show-Error "找不到 pyproject.toml 檔案！" @(
        "確認您在正確的專案目錄中執行此腳本",
        "檢查檔案是否存在且未損壞"
    )
}

if (-not (Test-Path "fortify_gui.py")) {
    Write-Host "⚠️  找不到 fortify_gui.py，請確認專案檔案完整" -ForegroundColor Yellow
}

Write-Host "✅ 專案檔案檢查完成" -ForegroundColor Green

# 5. 安裝依賴套件
Write-Host ""
Write-Host "[5/5] 安裝專案依賴套件..." -ForegroundColor Green

try {
    uv sync
    Write-Host "✅ 依賴套件安裝完成" -ForegroundColor Green
}
catch {
    Show-Error "依賴套件安裝失敗！" @(
        "檢查網路連線",
        "嘗試手動執行：uv sync",
        "或使用傳統方式：pip install -r requirements.txt",
        "檢查防火牆是否阻擋套件下載"
    )
}

# 檢查設定檔
Write-Host ""
Write-Host "[設定檢查] 檢查設定檔..." -ForegroundColor Green

if (-not (Test-Path "config\config.yaml")) {
    Write-Host "⚠️  設定檔不存在，請確認 config/config.yaml 已正確設置" -ForegroundColor Yellow
} else {
    Write-Host "✅ 設定檔存在" -ForegroundColor Green
}

# 安裝完成
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "           🎉 安裝完成！" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "📋 使用說明：" -ForegroundColor Yellow
Write-Host "   1. 啟動 GUI：雙擊 start_gui.bat" -ForegroundColor White
Write-Host "   2. 或手動執行：uv run python fortify_gui.py" -ForegroundColor White
Write-Host "   3. 首次使用請先在設定分頁設置 Azure DevOps PAT" -ForegroundColor White
Write-Host ""

Write-Host "📁 重要檔案：" -ForegroundColor Yellow
Write-Host "   • fortify_gui.py - GUI 主程式" -ForegroundColor White
Write-Host "   • config/config.yaml - 設定檔" -ForegroundColor White
Write-Host "   • README.md - 詳細使用說明" -ForegroundColor White
Write-Host ""

Write-Host "🔧 如遇問題：" -ForegroundColor Yellow
Write-Host "   • 檢查 README.md 中的疑難排解章節" -ForegroundColor White
Write-Host "   • 確認 PAT 權限設定正確" -ForegroundColor White
Write-Host "   • 檢查網路連線與防火牆設定" -ForegroundColor White
Write-Host ""

Read-Host "按 Enter 鍵結束"
