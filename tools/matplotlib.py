"""Matplotlib visualization tool for the LME report agent.

Generates charts (bar, line, pie, scatter) from data using LLM-generated
Python code executed in a sandboxed environment.
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

MATPLOTLIB_SYSTEM_PROMPT = dedent("""
# Role
你是一位專業的 Python 資料視覺化專家，精通 matplotlib、seaborn 等視覺化庫。你的任務是根據使用者指定的視覺化任務與數據內容，生成精確、可執行的 Python 代碼來生成圖片。

# Goal
生成一段可直接執行的 Python 代碼，使用 matplotlib 根據每個任務的描述生成對應的圖片，並將圖片儲存為指定的檔案名稱。

# Input
- <tasks>: 視覺化任務列表，每個任務包含：
  - file_name: 圖片的輸出檔案名稱（含副檔名，如 .png）
  - task: 需要完成的視覺化任務描述（例如：繪製長條圖、折線圖、圓餅圖等）
- <context>: 需要進行視覺化的數據內容（通常為 pandas_tool 或 schema_tool 回傳的數據）

# Rule
- 必須在 import pyplot 之前先執行 `import matplotlib; matplotlib.use('Agg')` 以設定非互動式後端（避免 GUI 視窗彈出）
- 使用 `import matplotlib.pyplot as plt` 進行數據視覺化
- 使用 `import matplotlib` 並設定 `matplotlib.rcParams['font.sans-serif'] = ['Microsoft JhengHei']` 以支援中文字型顯示
- 根據每個 task 的 task 描述，選擇合適的圖表類型（長條圖 bar、折線圖 plot、圓餅圖 pie、散佈圖 scatter 等）
- 每個任務生成一張獨立的圖片，使用 `plt.savefig(file_name, dpi=150, bbox_inches='tight')` 儲存
- 在每個圖片生成前使用 `plt.figure()` 建立新圖表，生成後使用 `plt.close()` 關閉以避免圖表重疊
- 使用 `print(f'已儲存: {{file_name}}')` 輸出每個圖片的儲存確認訊息
- 座標軸數值格式化：嚴禁使用科學記號（如 1e3、1e6）。必須使用 matplotlib.ticker.FuncFormatter 自訂格式化函式，將大數值轉換為易讀格式：
  - 英文報告：使用 K（千）、M（百萬）後綴（例如 1,200 → 1.2K，5,000,000 → 5M）
  - 中文報告：使用「萬」、「億」單位（例如 50,000 → 5萬，100,000,000 → 1億）
  - 根據 task 描述中的語言線索判斷使用英文或中文格式
  - 格式化函式範例：
    `python
    from matplotlib.ticker import FuncFormatter
    def k_formatter(x, pos):
        if x >= 1e6:
            return f'{{x/1e6:.1f}}M'
        elif x >= 1e3:
            return f'{{x/1e3:.1f}}K'
        return f'{{x:.0f}}'
    plt.gca().yaxis.set_major_formatter(FuncFormatter(k_formatter))
    `
- 輸出的代碼必須是純 Python 代碼，不含任何 markdown 標記或解釋文字

# Constraints
- 嚴禁輸出 markdown 代碼塊標記（如 ```python 或 ```）
- 嚴禁在代碼前後添加任何說明、註解或對話文字
- 嚴禁在座標軸上出現科學記號（1e3、1e6 等），必須使用 K/M 或萬/億等易讀格式
- 僅限使用 matplotlib、numpy、pandas 與 Python 標準庫，嚴禁使用其他未安裝的第三方套件
- 嚴禁修改、刪除或寫入任何非圖片檔案
- 嚴禁使用網路請求或外部 API
- 嚴禁使用 `plt.show()`，僅使用 `plt.savefig()` 儲存圖片

# Reasoning (Chain of Thought)
請依以下步驟逐步推理，每完成一步再進行下一步：

Step 1: [狀態確認] 確認輸入的 tasks 列表，逐一檢視每個任務的 file_name 與 task 描述
Step 2: [數據解析] 根據 <context> 中的數據內容，解析數據結構，確認可用於視覺化的欄位與數值
Step 3: [圖表選擇] 針對每個 task，根據其 task 描述選擇最合適的圖表類型與視覺化方式
Step 4: [代碼構建] 為每個任務構建完整的 matplotlib 代碼：import Agg → import pyplot → 建立 figure → 繪製圖表 → 設定標題/標籤 → savefig → close
Step 5: [驗證檢查] 檢查代碼是否僅包含必要的 import 與執行語句，無多餘內容，且每個任務都有對應的 savefig
Step 6: [整合輸出] 輸出純 Python 代碼字串，不含任何格式包裝
""")

class Task(BaseModel):
    """A single visualization task specification.

    Attributes:
        file_name: Output image filename (e.g. "chart.png").
        task: Description of the visualization to create.
    """
    file_name: str = Field(description="圖片的檔案名稱")
    task: str = Field(description="需要完成的任務")


class DataInputs(BaseModel):
    """Input schema for the matplotlib tool.

    Attributes:
        tasks: List of visualization tasks with filenames and descriptions.
        context: Data content to visualize (from pandas_tool or schema_tool).
    """
    tasks: list[Task] = Field(description="視覺化的任務。包含圖片檔案名稱和需要完成的任務")
    context: str = Field(description="需要進行視覺化的數據")


class MatplotlibTool(BaseTool):
    """LangChain tool that generates matplotlib charts from data.

    Uses an LLM to generate Python code that creates visualizations,
    then executes the code in a sandboxed environment. Supports bar,
    line, pie, scatter, and other chart types.

    Attributes:
        name: Tool identifier ("matplotlib_tool").
        description: Tool description for the agent.
        pipeline: LLM chain that generates visualization code.
    """
    name: str = "matplotlib_tool"

    description_template: str = dedent("""
Generates data visualizations (charts, plots, graphs) using Python and matplotlib. Provide a list of visualization tasks, each with a file name and a task description, along with the data context to visualize. Use this tool when you need to create charts, bar plots, line plots, pie charts, scatter plots, or any visual representation of data.

{input_format_instructions}
    """)

    input_parser: PydanticOutputParser = PydanticOutputParser(pydantic_object=DataInputs)
    input_format_instructions: str = input_parser.get_format_instructions()

    description: str = description_template.format(input_format_instructions=input_format_instructions)

    pipeline: Runnable

    @classmethod
    def create(cls, llm: Runnable):
        """Factory method to create a MatplotlibTool instance.

        Args:
            llm: LangChain Runnable (LLM) to use for code generation.

        Returns:
            MatplotlibTool: Configured tool instance.
        """

        input_ = {
            "system": {"template": MATPLOTLIB_SYSTEM_PROMPT},
            "human": {
                "template": dedent("""
                    <tasks>: {tasks}
                    <context>: {context}
                """),
                "input_variables": ["tasks", "context"]
            }
        }
        pipeline = build_standard_chat_prompt_template(input_) | llm | StrOutputParser()

        return cls(pipeline=pipeline)

    def _run(self, runtime: ToolRuntime[Context], **input):
        """Execute the matplotlib visualization tool.

        Generates Python code via the LLM pipeline and executes it
        to produce chart images.

        Args:
            runtime: Tool runtime with Context containing schema_output.
            **input: Must include "tasks" (list of Task) and "context" (str).

        Returns:
            list[Task]: The input tasks (for agent chaining).
        """

        args = input.get("input", input)

        tasks = args['tasks']
        context = args['context']

        # Prepend cached outputs to ensure full context is available
        parts = []
        if runtime.context.schema_output:
            parts.append(f"Schema Information:\n{runtime.context.schema_output}")
        # if runtime.context.pandas_output:
        #     parts.append(f"Analysis Results:\n{runtime.context.pandas_output}")
        if parts:
            context = "\n\n".join(parts) + f"\n\nVisualization Request:\n{context}"

        code = self.pipeline.invoke({
            "tasks": tasks,
            "context": context,
        })

        # Ensure matplotlib uses non-interactive backend and has a writable cache dir
        mpl_cache = os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'Temp', 'matplotlib-cache')
        os.makedirs(mpl_cache, exist_ok=True)
        exec_globals = {"__builtins__": __builtins__, "MPLCONFIGDIR": mpl_cache}

        stdout_capture = io.StringIO()
        try:
            with redirect_stdout(stdout_capture):
                exec(code, exec_globals)  # noqa: S102
        except Exception as e:  # noqa: BLE001
            print(f"EXECUTION ERROR: {e!s}")

        return tasks

    async def _arun(self, runtime: ToolRuntime[Context]):
        """Async execution (not implemented).

        Returns:
            str: Placeholder message.
        """

        return "Not implemented Yet"
