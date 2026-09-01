#!/usr/bin/env python3
"""Wrapper to launch codex exec with the slideshow report prompt."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

PROMPT = """
    # Role & Task
    你是一個自動化文件生成專家。請讀取本地最新的 `Report_<YYYY>-<MM>-<DD>.txt` 檔案，將其內容透過 `hyperframes` SKILL 的 `slideshow` 工作流轉換為 HTML，載入指定圖片後，最終使用 Playwright 輸出為 A4 直式 (Portrait) 的 PDF 報告。
    
    ---
    
    ## 1. 輸入與檔案處理 (Input & File Handling)
    1. **尋找來源檔**：檢索指定目錄下檔名符合 `Report_<YYYY>-<MM>-<DDDD>.txt` 的檔案，並自動選取**日期最新**的一份。
    2. **提取圖片標籤**：解析 .txt 內容中的圖片標記（例如 `![alt](image_name.png)` 或特定標籤），並確保 HTML 輸出時使用正確的本地相對路徑或 absolute path，以便 Playwright 順利讀取與載入。
    
    ---
    
    ## 2. 設計系統與樣式 (Design System & Tokens)
    - **Preset 來源**：讀取 `skills/hyperframes-creative/frame-presets/blue-professional/FRAME.md`。
    - **嚴格規範**：
      - 必須 100% 遵守 FRAME.md 裡定義的 `colors`、`typography`、`radii`、`spacing` 與 `components` tokens。
      - **嚴禁**自行增減或覆蓋預設的設計參數（如字體、主色系、邊框圓角等）。
    
    ---
    
    ## 3. 頁面與列印規範 (Page & Print CSS)
    在產出的 HTML/CSS 中必須包含以下列印樣式設定：
    
        ```css
        @page {
          size: A4 portrait;
          margin: 20mm;
        }
        
        /* 章節分頁 */
        h2, .section-header {
          page-break-before: always;
        }
        
        /* 避免元素跨頁裁切 */
        table, img, blockquote, .card {
          page-break-inside: avoid;
        }
        
        /* 圖片樣式：嚴格遵循 preset 的 radii 與 border */
        img {
          max-width: 100%;
          height: auto;
          border-radius: var(--radii-md); /* 依據 FRAME.md 的 token */
          border: var(--border-width-sm) solid var(--color-border);
        }
    
    ---
    
    ## 4. 執行流程與 Playwright 渲染 (Execution & Rendering)
        - 生成 HTML：
            - 整合內文與 CSS Tokens，生成中間檔 temp_report.html。
            - 採用 FRAME.md 的設計 token 建立靜態 HTML
        - 圖片加載檢查：
            - 使用 Playwright 啟動無頭瀏覽器 (Headless Browser) 開啟 HTML，並等待所有圖片載入完成 (networkidle 或監聽 img.complete)：
                page.goto(f"file://{html_path}", wait_until="networkidle")
        - 匯出 PDF：
            - 使用 Playwright 的 page.pdf() 導出。
            - 啟用 print_background=True 以確保渲染 CSS 背景色與顏色 Tokens。
            - 設定與 CSS 匹配的 A4 margin。
    
    ---
    
    ## 5. 輸出規範 (Output Requirements)
        - PDF 檔名：與來源 txt 檔名保持一致，僅替換副檔名。
            範例：來源為 Report_2026-08-11.txt ➔ 輸出 Report_2026-08-11.pdf。

        - 清理作業：PDF 成功生成後，自動清除臨時生成的 .html 檔案（若需要保留可註明）。
        - 輸出語言: 英文
"""


def find_codex() -> str:
    """Locate the codex executable in a cross-platform way."""
    # 1. Try shutil.which first
    found = shutil.which("codex")
    if found:
        found_path = Path(found)
        # On Windows, shutil.which may already return the .cmd/.bat wrapper.
        # If it has no extension, prefer the .cmd sidecar when present.
        if os.name == "nt" and not found_path.suffix:
            cmd_path = found_path.with_suffix(".cmd")
            if cmd_path.exists():
                return str(cmd_path)
        return found

    # 2. Fallback to common npm global paths on Windows
    if os.name == "nt":
        appdata = os.environ.get("APPDATA", "")
        candidates = [
            Path(appdata) / "npm" / "codex.cmd",
            Path(appdata) / "npm" / "codex.ps1",
            Path(os.environ.get("LOCALAPPDATA", "")) / "npm" / "codex.cmd",
        ]
        for cand in candidates:
            if cand.exists():
                return str(cand)

    # 3. Fallback to common *nix paths
    unix_candidates = [
        Path.home() / ".local" / "bin" / "codex",
        "/usr/local/bin/codex",
        "/usr/bin/codex",
    ]
    for cand in unix_candidates:
        if cand.exists():
            return str(cand)

    raise FileNotFoundError(
        "Could not locate 'codex' executable. "
        "Please ensure it is installed (e.g. via npm install -g codex) and on your PATH."
    )


def main():
    """Build and run the codex exec command."""
    codex_path = find_codex()
    print(f"Using codex: {codex_path}", file=sys.stderr)

    cmd = [
        codex_path,
        "--ask-for-approval", "never",
        "exec",
        "--skip-git-repo-check",
        "--local-provider=ollama",
        "--oss",
        "-m", "kimi-k2.6:cloud",
        "--sandbox", "danger-full-access",
        "--ephemeral",
    ]

    print("CMD:", repr(cmd), file=sys.stderr)

    for i, arg in enumerate(cmd):
        print(f"  [{i}] = {arg!r}", file=sys.stderr)

    print("Launching codex exec ...", file=sys.stderr)
    result = subprocess.run(cmd, cwd=".", encoding="utf-8", input=PROMPT)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
