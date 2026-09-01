"""Schema analysis tool for the LME report agent.

Reads Excel files in a directory and returns structure summaries
(sheet names, column names, data types, non-null counts, sample rows)
using LLM-generated Python code.
"""

import io
import os
from contextlib import redirect_stdout
from textwrap import dedent

from langchain.tools import BaseTool, ToolRuntime
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import Runnable

from context import build_standard_chat_prompt_template, Context


SCHEMA_SYSTEM_PROMPT = dedent("""
# Role
你是一位專業的 Python 資料分析師，精通 pandas 資料處理。你的任務是為指定的 Excel 檔案生成精確、可執行的 Python 代碼。

# Goal
生成一段可直接執行的 Python 代碼，使用 pandas 讀取 Excel 檔案，列出所有工作表名稱，並輸出每個工作表的結構摘要與前五筆資料。

# Input
- <file>: 待分析的 Excel 檔案完整路徑

# Rule
- 使用 `pd.ExcelFile(file).sheet_names` 列出所有工作表名稱
- 對每個工作表使用 `pd.read_excel(file, sheet_name=sheet_name)` 讀取
- 使用 `df.info()` 輸出人類可讀的完整摘要（欄位名、非空值數量、資料型別）
- 使用 `print(df.head(5).to_string())` 輸出前五筆資料
- 輸出的代碼必須是純 Python 代碼，不含任何 markdown 標記或解釋文字

# Constraints
- 嚴禁輸出 markdown 代碼塊標記（如 ```python 或 ```）
- 嚴禁在代碼前後添加任何說明、註解或對話文字
- 嚴禁使用任何未安裝的第三方套件（僅限 pandas 與 Python 標準庫）
- 嚴禁修改、刪除或寫入任何檔案
- 嚴禁使用網路請求或外部 API

# Reasoning (Chain of Thought)
請依以下步驟逐步推理，每完成一步再進行下一步：

Step 1: [狀態確認] 確認輸入的 Excel 檔案路徑 {file}，判斷檔案是否存在
Step 2: [關鍵分析] 先列出所有工作表名稱，再針對每個工作表使用 pd.read_excel() 讀取
Step 3: [推理展開] 構建輸出邏輯：先輸出工作表名稱，再對每個工作表呼叫 df.info() 與 print(df.head(5).to_string())
Step 4: [驗證檢查] 檢查代碼是否僅包含必要的 import 與執行語句，無多餘內容
Step 5: [整合輸出] 輸出純 Python 代碼字串，不含任何格式包裝
""")


class SchemaTool(BaseTool):
    """LangChain tool that analyzes Excel file schemas.

    Iterates over all .xlsx files in the context directory, generates
    Python code via an LLM to read each file's structure, and returns
    sheet names, column info, and sample data.

    Attributes:
        name: Tool identifier ("schema_tool").
        description: Tool description for the agent.
        pipeline: LLM chain that generates schema analysis code.
    """
    name: str = "schema_tool"
    description: str = dedent("""
    Reads all Excel files in a given directory and returns the schema (structure summary) and first 5 rows of each sheet. Uses pandas to analyze Excel files, providing sheet names, column names, data types, non-null counts, and sample data. Use this tool when you need to understand the structure and content of data files before further processing.
    """)

    pipeline: Runnable

    @classmethod
    def create(cls, llm: Runnable):
        """Factory method to create a SchemaTool instance.

        Args:
            llm: LangChain Runnable (LLM) to use for code generation.

        Returns:
            SchemaTool: Configured tool instance.
        """

        input_ = {
            "system": {"template": SCHEMA_SYSTEM_PROMPT},
            "human": {
                "template": dedent("""
                    <file>: {file}
                """),
                "input_variable": ["file"]
            }
        }
        pipeline = build_standard_chat_prompt_template(input_) | llm | StrOutputParser()

        return cls(pipeline=pipeline)

    def _run(self, runtime: ToolRuntime[Context], **input):
        """Execute the schema analysis tool.

        Iterates over all .xlsx files in the context directory, generates
        and executes Python code to read each file's structure, and caches
        the result in runtime.context.schema_output.

        Args:
            runtime: Tool runtime with Context containing the data directory.
            **input: Additional input (unused; directory comes from context).

        Returns:
            str: Concatenated schema summaries for all .xlsx files found.
        """
        directory = runtime.context.directory

        raw_output = ""

        for f in os.listdir(directory):

            if not f.endswith(".xlsx"):
                continue

            file = os.path.join(directory, f)

            code = self.pipeline.invoke({
                "file": file
            })

            stdout_capture = io.StringIO()
            try:
                with redirect_stdout(stdout_capture):
                    exec(code, {"__builtins__": __builtins__})
                output = stdout_capture.getvalue()
            except Exception as e:
                output = f"EXECUTION ERROR: {str(e)}"

            raw_output += f"-{file}: {output}\n\n"

        runtime.context.schema_output = raw_output

        return raw_output

    async def _arun(self, runtime: ToolRuntime[Context]):
        """Async execution (not implemented).

        Returns:
            str: Placeholder message.
        """

        return "Not implemented Yet"
