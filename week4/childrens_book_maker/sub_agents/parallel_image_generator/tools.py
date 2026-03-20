import base64
import json
from google.genai import types
from openai import OpenAI
from google.adk.tools.tool_context import ToolContext

STYLE_KEYWORDS = (
    "children's book illustration, soft watercolor style, warm pastel colors, "
    "gentle lighting, cute and friendly characters, detailed background"
)


async def generate_page_image(page_number: int, tool_context: ToolContext):
    """지정된 페이지 번호의 이미지를 생성합니다.

    Args:
        page_number: 이미지를 생성할 페이지 번호 (1~5)
        tool_context: ADK ToolContext
    """
    story_output = tool_context.state.get("story_output")

    if story_output is None:
        return {"status": "error", "message": "story_output이 state에 없습니다. StoryWriterAgent가 먼저 실행되어야 합니다."}

    if isinstance(story_output, str):
        if not story_output.strip():
            return {"status": "error", "message": "story_output이 빈 문자열입니다."}
        # { } 사이의 JSON 객체를 직접 추출 (코드블록, 주변 텍스트 모두 무시)
        start = story_output.find("{")
        end = story_output.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {"status": "error", "message": f"story_output에서 JSON 객체를 찾을 수 없습니다: {story_output[:200]}"}
        try:
            story_output = json.loads(story_output[start : end + 1])
        except json.JSONDecodeError as e:
            return {"status": "error", "message": f"JSON 파싱 실패: {e}"}

    pages = story_output.get("pages", [])
    page = next((p for p in pages if p.get("page_number") == page_number), None)

    if page is None:
        return {"status": "error", "message": f"페이지 {page_number}를 찾을 수 없습니다."}

    scene_description = page.get("scene_description", "")
    enhanced_prompt = f"{scene_description}, {STYLE_KEYWORDS}"
    filename = f"scene_{page_number}_image.jpeg"

    existing_artifacts = await tool_context.list_artifacts()
    if filename in existing_artifacts:
        return {
            "status": "skipped",
            "page_number": page_number,
            "filename": filename,
            "message": "이미 생성된 이미지입니다.",
        }

    client = OpenAI()
    image = client.images.generate(
        model="gpt-image-1.5",
        prompt=enhanced_prompt,
        n=1,
        quality="low",
        moderation="low",
        output_format="jpeg",
        background="opaque",
        size="1024x1536",
    )

    image_bytes = base64.b64decode(image.data[0].b64_json)

    artifact = types.Part(
        inline_data=types.Blob(
            mime_type="image/jpeg",
            data=image_bytes,
        )
    )

    await tool_context.save_artifact(filename=filename, artifact=artifact)

    return {
        "status": "complete",
        "page_number": page_number,
        "filename": filename,
        "prompt_used": enhanced_prompt[:120],
    }
