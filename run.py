"""LME report generation agent runner.

Initializes a LangChain ReAct agent backed by Ollama (deepseek-v4-pro)
with schema, pandas, matplotlib, and typesetting tools. The agent
analyzes LME Excel data and produces formatted reports with charts.

Usage:
    python run.py "<query>" [directory] [output_path]
"""

import os
import sys
from textwrap import dedent
from datetime import datetime

# Fix Windows console encoding for Unicode characters
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Fix matplotlib cache directory permissions in sandboxed environments
os.environ.setdefault('MPLCONFIGDIR', os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'Temp', 'matplotlib-cache'))
os.makedirs(os.environ['MPLCONFIGDIR'], exist_ok=True)

from langchain_ollama import ChatOllama
from langchain.agents import create_agent
from langchain.agents.middleware.tool_retry import ToolRetryMiddleware
from langchain_core.messages import HumanMessage

from initialization import credential_init
from context import Context
from tools.matplotlib import MatplotlibTool
from tools.typesetting import TypesettingTool
from tools.pandas import PandasTool
from tools.schema import SchemaTool
from tools.image_checker import ImageCheckerTool


credential_init()

AGENT_INSTRUCTION = dedent("""
# Role
你是一位專業的數據分析顧問，擅長解讀資料結構並提供清晰的分析建議。你的工作方式是先了解資料的樣貌，再根據使用者需求給出精準的回應。

# Goal
協助使用者理解資料內容並回答數據分析相關問題，必要時生成視覺化圖表來輔助說明。

# Tool
你可以使用以下工具來完成任務：

- **schema_tool**: 讀取指定目錄中的所有 Excel 檔案，返回每個檔案的結構摘要（工作表名稱、欄位名稱、資料型別、非空值數量）與前五筆範例資料。注意：此工具僅提供結構資訊與極少量範例，無法用於統計、篩選或計算。
- **pandas_tool**: 使用 Python 與 pandas、scikit-learn、scipy 等專業庫對指定的 Excel 檔案進行數據處理與分析，遍歷所有工作表（sheets）。支援篩選、分組、聚合、合併、統計檢定、機器學習建模等操作。這是唯一能對資料進行實際計算與分析的工具。
- **matplotlib_tool**: 使用 Python 與 matplotlib 將數據分析結果轉化為視覺化圖表（如長條圖、折線圖、圓餅圖、散佈圖等）。接受多個視覺化任務，每個任務包含圖片檔案名稱與任務描述，並根據提供的數據上下文生成對應圖片。注意：此工具僅用於視覺化，不能進行數據計算或分析。
- **typesetting_tool**: 使用 Python 與 LLM 將文字內容與圖片整合成結構清晰、美觀易讀的報告。接受圖片列表（含檔案名稱與描述）與文字內容，生成排版精美的 Markdown 報告。注意：此工具僅用於排版，不能進行數據計算或分析。
- **image_checker_tool**: 使用視覺模型檢查 matplotlib_tool 生成的圖表圖片。檢查項目包括：(1) 文字是否重疊（標籤、標題、軸標籤互相遮擋）；(2) 圖片內容是否符合任務需求（圖表類型、數據完整性、標題標籤清晰度）。返回每張圖片的詳細檢查結果，包含是否需要重新繪製及具體修改建議。注意：此工具僅用於檢查，不能生成或修改圖片。

# Workflow
1. 先使用 schema_tool 了解資料結構
2. 根據使用者需求，使用 pandas_tool 進行數據分析
3. 若需要視覺化，使用 matplotlib_tool 生成圖表
4. **重要**：生成圖表後，必須使用 image_checker_tool 檢查每張圖片的品質
5. 若 image_checker_tool 回報有圖片需要重畫（needs_redraw = true），根據 redraw_suggestion 的建議，重新調用 matplotlib_tool 修正該圖片
6. 重畫後再次使用 image_checker_tool 檢查，直到所有圖片通過檢查（最多重試 2 次）
7. 若需要報告，使用 typesetting_tool 生成排版報告

# Tool Selection

- 結構資訊 → schema_tool
- 實際資料分析 → pandas_tool
- 視覺化 → matplotlib_tool
- 圖片品質檢查 → image_checker_tool
- 報告排版 → typesetting_tool

注意：不應因為工具存在就強制使用工具。只使用完成任務所需要的工具。

# Constraints
- 嚴禁在未調用工具的情況下憑空猜測資料內容
- 嚴禁僅憑 schema_tool 的 5 筆範例資料就回答需要統計或計算的問題
- 嚴禁對資料進行任何寫入、修改或刪除操作
- 回答必須基於 pandas_tool 的實際計算結果，不得虛構
- 若使用者要求圖表，必須調用 matplotlib_tool 生成，不得以文字描述代替圖表
- 若使用者要求報告，必須調用 typesetting_tool 生成，不得以純文字代替排版報告
""")


llm = ChatOllama(model='deepseek-v4-pro:cloud',
                 base_url='https://ollama.com',
                 name='main', temperature=0)

# Vision-capable LLM for image checking (use a vision model like llava, gemma3, or minicpm-v)
vision_llm = ChatOllama(model='kimi-k2.6:cloud',
                 base_url='https://ollama.com',
                 name='vision', temperature=0)

tools = [SchemaTool.create(llm=llm),
         PandasTool.create(llm=llm),
         MatplotlibTool.create(llm=llm),
         TypesettingTool.create(llm=llm),
         ImageCheckerTool.create(vision_llm=vision_llm)]

agent = create_agent(
    model=llm,
    name="analysis_agent",
    tools=tools,
    system_prompt=AGENT_INSTRUCTION,
    middleware=[
        ToolRetryMiddleware(max_retries=2),
    ]
)


def invoke(query: str, directory: str = "./data", output_path: str = None):
    """Invoke the analysis agent with a user query.

    Creates a runtime Context bound to the given data directory and passes
    the user request to the agent. The agent will reason step-by-step
    (ReAct) and call the appropriate tools (schema / pandas / matplotlib /
    typesetting) to fulfil the request.

    Args:
        query: User request in natural language (e.g. "分析今天 LME 價格趨勢並產出報告").
        directory: Path to the folder that contains the data files.
        output_path: Optional path for saving the final report text.
            If None, defaults to data/LME_Report_YYYY-MM-DD.txt.

    Returns:
        str: The agent's final response. If the agent generated images
            or a report, their file names are mentioned in the response.
    """
    context = Context(directory=directory)

    agent_input = {
        "messages": HumanMessage(content=query)
    }

    final_content = ""

    for update in agent.stream(
            agent_input,
            context=context,
            stream_mode="updates",
    ):
        for key, value in update.items():
            if key == "model":
                content = value["messages"][0].content
                tool_calls = value["messages"][0].tool_calls
                try:
                    print(f"{key}: ", content, tool_calls)
                except UnicodeEncodeError:
                    # Fallback for Windows cp950 console
                    print(f"{key}: ", content.encode('utf-8', errors='replace').decode('utf-8'), tool_calls)
                # Track the latest model output as the final answer
                final_content = content
            if key == "tools":
                try:
                    print(f"{key}: ", value["messages"][0].content, value["messages"][0].name)
                except UnicodeEncodeError:
                    print(f"{key}: ", value["messages"][0].content.encode('utf-8', errors='replace').decode('utf-8'), value["messages"][0].name)

                if value["messages"][0].name == "typesetting_tool":

                    # Resolve output path
                    if output_path is None:
                        today = datetime.now().strftime("%Y-%m-%d")
                        output_path = os.path.join(directory, f"Report_{today}.txt")

                    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

                    with open(output_path, "w", encoding="utf-8") as f:
                        f.write(value['messages'][0].content)

                    print(f"Report saved to: {output_path}")

    return final_content


if __name__ == "__main__":

    from textwrap import dedent

    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "analysis_requirements.txt")
    with open(config_path, "r", encoding="utf-8") as f:
        user_goals = f.read()

    user_query = dedent("""
    {goals}
    
    # 欄位解釋:
    
    - Total shipment amount in US$: 出貨美金金額
    - PO issued month: 下訂單月份
    - PO issued year: 下訂單年份
    - Product type: 產品分類
    - Name of end customer: 終端客戶
    - Industry: 產業
    - Order qty: 銷售數量
    - Shipped month: 出貨月份
    - Shipped year: 出貨年份
    
    # 規則:
    
    - 當提到時間的時候，以出貨的時間為主
    - 輸出使用英文
    
    """).format(goals=user_goals)

    data_dir = "./data"

    output_file = None

    response = invoke(query=user_query, directory=data_dir, output_path=output_file)
    print(response)
