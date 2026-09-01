"""Typesetting and report generation tool for the LME report agent.

Combines text content with images into a well-formatted Markdown report
using LLM-generated layout instructions.
"""

from textwrap import dedent

from langchain.tools import BaseTool, ToolRuntime
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field

from context import Context, build_standard_chat_prompt_template

TYPESETTING_SYSTEM_PROMPT = dedent("""
# Role
你是一位專業的報告排版專家，精通 Markdown 格式與文件排版。你的任務是將文字內容與圖片整合成結構清晰、美觀易讀的報告。

# Goal
根據提供的 <text> 文字內容與 <images> 圖片列表，生成一份排版精美的 Markdown 報告。

# Input
- <images>: 圖片列表，每個圖片包含：
  - file_name: 圖片的檔案名稱
  - caption: 圖片的說明文字
- <text>: 報告的文字內容

# Rule
- 根據文字內容的結構，合理安排章節標題與段落
- 將圖片插入到文字中相關的位置，並附上 caption 作為圖說
- 報告應包含標題、章節、段落等結構化元素
- 使用 Markdown 語法生成格式化的報告
- 圖片使用 Markdown 語法 ![caption](file_name) 插入
- 報告排版應美觀易讀，段落之間保持適當間距

# Constraints
- 嚴禁憑空捏造不存在於 <text> 中的內容
- 嚴禁使用不存在的圖片 file_name 或 caption
- 嚴禁在報告中添加未經請求的內容
- 輸出必須是純 Markdown 格式
- 嚴禁使用任何未安裝的第三方套件或外部資源

# Reasoning (Chain of Thought)
請依以下步驟逐步推理，每完成一步再進行下一步：

Step 1: [內容分析] 閱讀 <text> 的內容，了解報告的主題、結構與重點
Step 2: [圖片匹配] 檢視 <images> 列表，根據每張圖片的 caption 判斷應插入的章節位置
Step 3: [結構規劃] 規劃報告的整體結構：標題、章節、段落與圖片插入點
Step 4: [報告生成] 使用 Markdown 語法生成完整的報告，包含標題、章節與圖片
Step 5: [排版檢查] 檢查報告的排版是否美觀、圖片位置是否合理、章節結構是否清晰
Step 6: [最終輸出] 輸出完整的 Markdown 報告，不含任何格式包裝
""")


class Image(BaseModel):
    """An image to include in the report.

    Attributes:
        file_name: Image filename (e.g. "chart.png").
        caption: Descriptive caption displayed below the image.
    """

    file_name: str = Field(description="圖片的檔案名稱")
    caption: str = Field(description="圖片的說明文字，用於在報告中顯示在圖片下方作為圖說")


class ContentInputs(BaseModel):
    """Input schema for the typesetting tool.

    Attributes:
        images: List of images with filenames and captions.
        text: Report body text to format.
    """

    images: list[Image] = Field(description="要包含在報告中的圖片列表，每個圖片包含檔案名稱和說明文字")
    text: str = Field(description="報告的文字內容")


class TypesettingTool(BaseTool):
    """LangChain tool that generates formatted Markdown reports.

    Combines text content with images, intelligently arranging images
    within the text to create a structured, readable report.

    Attributes:
        name: Tool identifier ("typesetting_tool").
        description: Tool description for the agent.
        pipeline: LLM chain that generates the formatted report.
    """

    name: str = "typesetting_tool"

    # return_direct: bool = True
    description_template: str = dedent("""
Generates a well-formatted report by combining text content with images. Provide a list of images (each with a file name and caption) and the report text. The tool will intelligently arrange images within the text to create a structured, readable report in Markdown format. Use this tool when you need to create a report that integrates both textual content and visual elements.

{input_format_instructions}
    """)

    input_parser: PydanticOutputParser = PydanticOutputParser(pydantic_object=ContentInputs)
    input_format_instructions: str = input_parser.get_format_instructions()

    description: str = description_template.format(input_format_instructions=input_format_instructions)

    pipeline: Runnable

    @classmethod
    def create(cls, llm: Runnable):
        """Factory method to create a TypesettingTool instance.

        Args:
            llm: LangChain Runnable (LLM) to use for report generation.

        Returns:
            TypesettingTool: Configured tool instance.
        """

        input_ = {
            "system": {"template": TYPESETTING_SYSTEM_PROMPT},
            "human": {
                "template": dedent("""
                    <images>: {images}
                    <text>: {text}
                """),
                "input_variables": ["images", "text"],
            },
        }
        pipeline = build_standard_chat_prompt_template(input_) | llm | StrOutputParser()

        return cls(pipeline=pipeline)

    def _run(self, runtime: ToolRuntime[Context], **input):
        """Execute the typesetting tool.

        Generates a formatted Markdown report combining text and images,
        with cached schema and pandas outputs prepended for context.

        Args:
            runtime: Tool runtime with Context containing schema_output
                and pandas_output.
            **input: Must include "images" (list[Image]) and "text" (str).

        Returns:
            str: Formatted Markdown report.
        """
        args = input.get("input", input)

        images = args["images"]
        text = args["text"]

        # Prepend cached outputs to ensure full context is available
        parts = []
        if runtime.context.schema_output:
            parts.append(f"Schema Information:\n{runtime.context.schema_output}")
        if runtime.context.pandas_output:
            parts.append(f"Analysis Results:\n{runtime.context.pandas_output}")
        if parts:
            text = "\n\n".join(parts) + f"\n\nReport Text:\n{text}"

        output = self.pipeline.invoke(
            {
                "text": text,
                "images": images,
            }
        )

        return output

    async def _arun(self, runtime: ToolRuntime[Context]):
        """Async execution (not implemented).

        Returns:
            str: Placeholder message.
        """

        return "Not implemented Yet"
