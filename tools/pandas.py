"""Pandas data analysis tool for the LME report agent.

Processes Excel files using LLM-generated Python code with pandas,
scikit-learn, and scipy, executed in a sandboxed environment.
"""

import io
import os
from contextlib import redirect_stdout
from textwrap import dedent

from langchain.tools import BaseTool, ToolRuntime
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field

from context import Context, build_standard_chat_prompt_template

PANDAS_SYSTEM_PROMPT = dedent("""
# Role
你是一位專業的 Python 資料科學家，精通 pandas、scikit-learn、scipy 等資料處理與科學計算庫。你的任務是根據使用者指定的 Excel 檔案，生成精確、可執行的 Python 代碼來進行數據處理與分析。

# Goal
生成一段可直接執行的 Python 代碼，使用 pandas、scikit-learn、scipy 等專業庫對指定的 Excel 檔案進行數據處理與分析，遍歷所有工作表（sheets）並輸出處理結果。

# Input
- <files>: 待處理的 Excel 檔案完整路徑列表
- <context>: schema_tool 回傳的檔案結構摘要（欄位名稱、資料型別、範例資料）
- <user_query>: 使用者的原始分析需求或問題

# Rule
- 使用 `pd.read_excel(file, sheet_name=None)` 讀取每個 Excel 檔案，這會回傳一個以工作表名稱為鍵的字典（dict of DataFrames）
- 遍歷所有工作表：先透過 `pd.ExcelFile(file).sheet_names` 取得所有工作表名稱，或使用 `sheet_name=None` 自動讀取全部
- 根據 <user_query> 與 <context> 中的欄位結構，選用合適的庫進行數據處理與分析：
  - **pandas**: 資料讀取、篩選、分組、聚合、合併（`pd.merge` / `pd.concat`）、排序、描述性統計
  - **scikit-learn**: 資料預處理（標準化、編碼、降維）、模型訓練與預測、評估指標
  - **scipy**: 統計檢定（t-test、chi-square、ANOVA）、優化、信號處理、稀疏矩陣運算
- 使用 `print()` 輸出處理結果，確保輸出清晰可讀，並標示目前處理的是哪一個工作表
- 輸出的代碼必須是純 Python 代碼，不含任何 markdown 標記或解釋文字

# Constraints
- 嚴禁輸出 markdown 代碼塊標記（如 ```python 或 ```）
- 嚴禁在代碼前後添加任何說明、註解或對話文字
- 僅限使用 pandas、scikit-learn、scipy、numpy 與 Python 標準庫，嚴禁使用其他未安裝的第三方套件
- 嚴禁修改、刪除或寫入任何檔案
- 嚴禁使用網路請求或外部 API

# Reasoning (Chain of Thought)
請依以下步驟逐步推理，每完成一步再進行下一步：

Step 1: [狀態確認] 確認輸入的 Excel 檔案列表 {files}，使用 `pd.ExcelFile(file).sheet_names` 列出每個檔案的所有工作表名稱
Step 2: [需求分析] 根據 <user_query> 與 <context> 中的欄位資訊，選擇最合適的庫與方法（pandas 處理 / sklearn 建模 / scipy 檢定），並決定是否需要合併多個工作表
Step 3: [推理展開] 構建處理流程：讀取全部工作表 → 預處理 → 分析/建模 → 輸出每個工作表的結果
Step 4: [驗證檢查] 檢查代碼是否僅包含必要的 import 與執行語句，無多餘內容，並確保所有工作表都被處理
Step 5: [整合輸出] 輸出純 Python 代碼字串，不含任何格式包裝
""")


class FilesInputs(BaseModel):
    """Input schema for the pandas tool.

    Attributes:
        files: List of Excel filenames (without directory path) to process.
        user_query: The user's original analysis question in natural language.
    """
    files: list[str] = Field(
        description="List of Excel file names to process. Provide the filenames (without directory path) of the data files you want to analyze or transform.")
    user_query: str = Field(
        description="The user's original question or analysis requirement in natural language.")


class PandasTool(BaseTool):
    """LangChain tool that processes Excel files with pandas.

    Uses an LLM to generate Python code for data analysis (filtering,
    grouping, aggregation, statistical tests, ML modeling), then
    executes the code in a sandboxed environment.

    Attributes:
        name: Tool identifier ("pandas_tool").
        description: Tool description for the agent.
        pipeline: LLM chain that generates analysis code.
    """
    name: str = "pandas_tool"

    description_template: str = dedent("""
Processes specified Excel files using Python and pandas. Provide a list of file names to perform data operations such as filtering, grouping, aggregation, merging, sorting, and statistical analysis across all sheets. Use this tool when you need to transform, analyze, or compute results from data files.

{input_format_instructions}
    """)

    input_parser: PydanticOutputParser = PydanticOutputParser(pydantic_object=FilesInputs)
    input_format_instructions: str = input_parser.get_format_instructions()

    description: str = description_template.format(input_format_instructions=input_format_instructions)

    pipeline: Runnable

    @classmethod
    def create(cls, llm: Runnable):
        """Factory method to create a PandasTool instance.

        Args:
            llm: LangChain Runnable (LLM) to use for code generation.

        Returns:
            PandasTool: Configured tool instance.
        """

        input_ = {
            "system": {"template": PANDAS_SYSTEM_PROMPT},
            "human": {
                "template": dedent("""
                    <files>: {files}
                    <context>: {context}
                    <user_query>: {user_query}
                """),
                "input_variables": ["files", "context", "user_query"]
            }
        }
        pipeline = build_standard_chat_prompt_template(input_) | llm | StrOutputParser()

        return cls(pipeline=pipeline)

    def _run(self, runtime: ToolRuntime[Context], **input):
        """Execute the pandas data analysis tool.

        Generates Python code via the LLM pipeline and executes it
        to produce analysis results.

        Args:
            runtime: Tool runtime with Context containing directory
                and schema_output.
            **input: Must include "files" (list[str]) and "user_query" (str).

        Returns:
            str: Captured stdout from the executed analysis code.
        """
        directory = runtime.context.directory

        args = input.get("input", input)

        files = args['files']
        user_query = args['user_query']

        # Prepend cached schema output to ensure full schema info is available
        if runtime.context.schema_output:
            context = f"Schema Information:\n{runtime.context.schema_output}\n\n"

        code = self.pipeline.invoke({
            "files": [os.path.join(directory, f) for f in files],
            "context": context,
            "user_query": user_query
        })

        stdout_capture = io.StringIO()
        try:
            with redirect_stdout(stdout_capture):
                exec(code, {"__builtins__": __builtins__})  # noqa: S102
            output = stdout_capture.getvalue()
        except Exception as e:  # noqa: BLE001
            output = f"EXECUTION ERROR: {e!s}"

        return output

    async def _arun(self, runtime: ToolRuntime[Context]):
        """Async execution (not implemented).

        Returns:
            str: Placeholder message.
        """

        return "Not implemented Yet"
