import asyncio
import base64
import json
import os
from textwrap import dedent

from langchain.tools import BaseTool, ToolRuntime
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field

from context import Context

IMAGE_CHECKER_SYSTEM_PROMPT = dedent("""
# Role
你是一位專業的圖表品質審查員，擅長檢查資料視覺化圖片的視覺品質與內容正確性。

# Goal
檢查每張圖表圖片，判斷是否存在以下問題：
1. 文字重疊（例如：標籤重疊、標題與圖表元素重疊、軸標籤互相遮擋）
2. 圖片內容是否符合任務需求（例如：圖表類型是否正確、數據是否完整呈現、標題與標籤是否清晰）

# Input
- 每張圖片附帶其原始視覺化任務描述（task）

# Output Format
對每張圖片輸出 JSON 格式的檢查結果：
{
  "file_name": "圖片檔案名稱",
  "has_text_overlap": true/false,
  "text_overlap_detail": "文字重疊的具體描述（若無則為空字串）",
  "meets_task_requirements": true/false,
  "task_requirement_detail": "不符合任務需求的具體描述（若符合則為空字串）",
  "needs_redraw": true/false,
  "redraw_suggestion": "若需重畫，提供具體的修改建議（若無則為空字串）"
}

# Rule
- needs_redraw 為 true 的條件：has_text_overlap 為 true 或 meets_task_requirements 為 false
- redraw_suggestion 必須具體明確，例如：「請調整 x 軸標籤旋轉角度以避免重疊」、「請使用長條圖而非折線圖」
- 若圖片完全正常，needs_redraw 為 false，redraw_suggestion 為空字串

# Constraints
- 必須對每張圖片都進行檢查，不可跳過
- 檢查結果必須基於圖片實際內容，不可憑空猜測
- 輸出必須是有效的 JSON 格式
""")

SEMAPHORE_LIMIT = 4


class ImageCheckItem(BaseModel):
    file_name: str = Field(description="圖片檔案名稱")
    task: str = Field(description="該圖片的原始視覺化任務描述")


class ImageCheckResult(BaseModel):
    file_name: str = Field(description="圖片檔案名稱")
    has_text_overlap: bool = Field(description="是否有文字重疊問題")
    text_overlap_detail: str = Field(description="文字重疊的具體描述")
    meets_task_requirements: bool = Field(description="是否符合任務需求")
    task_requirement_detail: str = Field(description="不符合任務需求的具體描述")
    needs_redraw: bool = Field(description="是否需要重新繪製")
    redraw_suggestion: str = Field(description="重新繪製的具體建議")


class ImageCheckInputs(BaseModel):
    images: list[ImageCheckItem] = Field(description="要檢查的圖片列表，每個包含檔案名稱與原始任務描述")


class ImageCheckerTool(BaseTool):
    name: str = "image_checker_tool"

    description_template: str = dedent("""
Checks generated chart images for visual quality issues. Provide a list of images (each with a file name and the original visualization task description). The tool will analyze each image for text overlap problems and whether the chart meets the task requirements. Returns a detailed assessment for each image, including whether a redraw is needed and specific suggestions for improvement.

{input_format_instructions}
    """)

    input_parser: PydanticOutputParser = PydanticOutputParser(pydantic_object=ImageCheckInputs)
    input_format_instructions: str = input_parser.get_format_instructions()

    description: str = description_template.format(input_format_instructions=input_format_instructions)

    vision_llm: Runnable

    @classmethod
    def create(cls, vision_llm: Runnable):
        return cls(vision_llm=vision_llm)

    def _encode_image(self, file_path: str) -> str:
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _resolve_path(self, file_name: str) -> str:
        if os.path.isabs(file_name):
            return file_name
        return os.path.join(os.getcwd(), file_name)

    def _get_mime_type(self, file_name: str) -> str:
        ext = os.path.splitext(file_name)[1].lower()
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        return mime_map.get(ext, "image/png")

    def _parse_response(self, result_text: str, file_name: str) -> dict:
        result_text = result_text.strip()
        if result_text.startswith(""):
            lines = result_text.split("\n")
            result_text = "\n".join(lines[1:-1])
        try:
            return json.loads(result_text)
        except json.JSONDecodeError:
            return {
                "file_name": file_name,
                "has_text_overlap": "文字重疊" in result_text or "重疊" in result_text,
                "text_overlap_detail": result_text,
                "meets_task_requirements": "符合" in result_text and "不符合" not in result_text,
                "task_requirement_detail": result_text,
                "needs_redraw": "重畫" in result_text or "重繪" in result_text or "修改" in result_text,
                "redraw_suggestion": result_text if "重畫" in result_text or "重繪" in result_text else "",
            }

    def _error_result(self, file_name: str, detail: str, suggestion: str) -> dict:
        return {
            "file_name": file_name,
            "has_text_overlap": False,
            "text_overlap_detail": "",
            "meets_task_requirements": False,
            "task_requirement_detail": detail,
            "needs_redraw": True,
            "redraw_suggestion": suggestion,
        }

    async def _check_image_async(self, semaphore: asyncio.Semaphore, img: dict) -> dict:
        async with semaphore:
            file_name = img["file_name"]
            task = img["task"]

            full_path = self._resolve_path(file_name)

            if not os.path.exists(full_path):
                return self._error_result(file_name, f"圖片檔案不存在: {full_path}", "請確認圖片檔案路徑是否正確")

            try:
                image_b64 = self._encode_image(full_path)
            except OSError as e:
                return self._error_result(file_name, f"無法讀取圖片: {e!s}", "請確認圖片檔案是否損毀")

            mime_type = self._get_mime_type(file_name)
            user_prompt = f"請檢查以下圖片。原始視覺化任務：{task}"

            message = HumanMessage(
                content=[
                    {"type": "text", "text": IMAGE_CHECKER_SYSTEM_PROMPT + "\n\n" + user_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}},
                ]
            )

            try:
                response = await self.vision_llm.ainvoke([message])
                result_text = response.content if hasattr(response, "content") else str(response)
            except Exception as e:  # noqa: BLE001
                return self._error_result(file_name, f"視覺檢查失敗: {e!s}", "請重新生成圖片後再次檢查")

            return self._parse_response(result_text, file_name)

    async def _run_async(self, images: list) -> list:
        semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)
        tasks = [self._check_image_async(semaphore, img) for img in images]
        return await asyncio.gather(*tasks)

    def _run(self, runtime: ToolRuntime[Context], **input):
        args = input.get("input", input)
        images = args["images"]
        return asyncio.run(self._run_async(images))

    async def _arun(self, runtime: ToolRuntime[Context], **input):
        args = input.get("input", input)
        images = args["images"]
        return await self._run_async(images)
