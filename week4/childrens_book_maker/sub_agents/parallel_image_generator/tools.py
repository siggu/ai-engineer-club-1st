"""
이미지 생성 + 페이지 합성 툴

OpenAI로 장면 이미지를 생성한 뒤, PIL로 아래 레이아웃의 페이지 이미지를 합성합니다.

┌─────────────────────────┐
│                         │
│      [장면 이미지]       │  ← 상단 460px (cover crop)
│                         │
├─────────────────────────┤  ← 구분선
│  줄거리 텍스트           │  ← 하단 흰색 텍스트 영역
│                         │     (패딩 24px)
│                      1  │  ← 페이지 번호 (우하단)
└─────────────────────────┘
"""

import base64
import io
import json

from google.adk.tools.tool_context import ToolContext
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont

# ── 이미지 생성 스타일 키워드 ──────────────────────────────────
STYLE_KEYWORDS = (
    "children's book illustration, soft watercolor style, warm pastel colors, "
    "gentle lighting, cute and friendly characters, detailed background"
)

# ── 페이지 레이아웃 상수 ───────────────────────────────────────
PAGE_WIDTH       = 620   # 전체 페이지 너비 (px)
IMAGE_HEIGHT     = 460   # 장면 이미지 영역 높이 (px)
TEXT_AREA_HEIGHT = 210   # 텍스트 영역 높이 (px)
PAGE_HEIGHT      = IMAGE_HEIGHT + TEXT_AREA_HEIGHT  # 670px
PADDING          = 28    # 텍스트 영역 좌우·상하 패딩
BODY_FONT_SIZE   = 21
PAGE_NUM_SIZE    = 18

# ── 폰트 경로 (Windows 한국어 지원) ───────────────────────────
_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\malgun.ttf",    # Malgun Gothic (한국어)
    r"C:\Windows\Fonts\gulim.ttc",     # Gulim
    r"C:\Windows\Fonts\arial.ttf",     # Arial (영문 fallback)
]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def _wrap_korean(draw: ImageDraw.ImageDraw, text: str,
                 font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """한국어 문자 단위 줄바꿈."""
    lines: list[str] = []
    current = ""
    for ch in text:
        test = current + ch
        w = draw.textlength(test, font=font)
        if w <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = ch
    if current:
        lines.append(current)
    return lines


def compose_book_page(scene_bytes: bytes, page_text: str, page_number: int) -> bytes:
    """장면 이미지 + 텍스트 + 페이지 번호를 합성해 JPEG bytes를 반환합니다."""

    # ── 1. 빈 흰색 캔버스 ─────────────────────────────────────
    page = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), color=(255, 255, 255))
    draw = ImageDraw.Draw(page)

    # ── 2. 장면 이미지 (cover crop) ────────────────────────────
    scene = Image.open(io.BytesIO(scene_bytes)).convert("RGB")
    orig_w, orig_h = scene.size

    # 가로를 PAGE_WIDTH에 맞춰 스케일 → 상단 IMAGE_HEIGHT px만 사용
    scaled_h = int(orig_h * PAGE_WIDTH / orig_w)
    scene_resized = scene.resize((PAGE_WIDTH, scaled_h), Image.LANCZOS)
    scene_cropped = scene_resized.crop((0, 0, PAGE_WIDTH, IMAGE_HEIGHT))
    page.paste(scene_cropped, (0, 0))

    # ── 3. 구분선 ──────────────────────────────────────────────
    draw.line([(0, IMAGE_HEIGHT), (PAGE_WIDTH, IMAGE_HEIGHT)],
              fill=(210, 210, 210), width=1)

    # ── 4. 줄거리 텍스트 ───────────────────────────────────────
    body_font = _load_font(BODY_FONT_SIZE)
    max_text_w = PAGE_WIDTH - PADDING * 2
    lines = _wrap_korean(draw, page_text, body_font, max_text_w)

    line_h = BODY_FONT_SIZE + 7   # 줄 간격
    text_y = IMAGE_HEIGHT + PADDING

    for line in lines[:4]:        # 최대 4줄
        draw.text((PADDING, text_y), line, font=body_font, fill=(40, 40, 40))
        text_y += line_h

    # ── 5. 페이지 번호 (우하단) ────────────────────────────────
    num_font = _load_font(PAGE_NUM_SIZE)
    num_str  = str(page_number)
    num_w    = draw.textlength(num_str, font=num_font)
    draw.text(
        (PAGE_WIDTH - PADDING - num_w, PAGE_HEIGHT - PADDING - PAGE_NUM_SIZE),
        num_str,
        font=num_font,
        fill=(140, 140, 140),
    )

    # ── 6. JPEG 변환 ───────────────────────────────────────────
    output = io.BytesIO()
    page.save(output, format="JPEG", quality=92)
    return output.getvalue()


# ──────────────────────────────────────────────────────────────
# ADK Tool
# ──────────────────────────────────────────────────────────────

async def generate_page_image(page_number: int, tool_context: ToolContext):
    """페이지 장면 이미지를 생성하고 텍스트를 합성해 동화책 페이지를 만듭니다.

    Args:
        page_number: 페이지 번호 (1~5)
        tool_context: ADK ToolContext
    """
    # ── story_output 로드 ──────────────────────────────────────
    story_output = tool_context.state.get("story_output")
    if story_output is None:
        return {"status": "error", "message": "story_output이 state에 없습니다."}

    if isinstance(story_output, str):
        start, end = story_output.find("{"), story_output.rfind("}")
        if start == -1 or end <= start:
            return {"status": "error", "message": "story_output에서 JSON을 찾을 수 없습니다."}
        try:
            story_output = json.loads(story_output[start : end + 1])
        except json.JSONDecodeError as e:
            return {"status": "error", "message": f"JSON 파싱 실패: {e}"}

    pages = story_output.get("pages", [])
    page  = next((p for p in pages if p.get("page_number") == page_number), None)
    if page is None:
        return {"status": "error", "message": f"페이지 {page_number}를 찾을 수 없습니다."}

    filename = f"scene_{page_number}_image.jpeg"

    # ── 이미 생성된 경우 스킵 (state 기준) ────────────────────
    if tool_context.state.get(f"image_data_{page_number}"):
        return {"status": "skipped", "page_number": page_number, "filename": filename}

    # ── OpenAI 장면 이미지 생성 ────────────────────────────────
    scene_description = page.get("scene_description", "")
    prompt = f"{scene_description}, {STYLE_KEYWORDS}"

    client   = OpenAI()
    response = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        n=1,
        quality="low",
        output_format="jpeg",
        size="1024x1024",   # 정사각형 → cover crop에 최적
    )
    scene_bytes = base64.b64decode(response.data[0].b64_json)

    # ── PIL로 동화책 페이지 합성 (이미지 + 텍스트 + 페이지 번호) ─
    page_text    = page.get("text", "")
    page_bytes   = compose_book_page(scene_bytes, page_text, page_number)

    # ── State 저장 (BookAssemblerAgent 가 순서대로 렌더링) ────────
    # save_artifact 를 쓰면 ADK 브라우저가 완성 순서대로 이미지를 표시해
    # 1→5 순서가 깨지므로 state 에만 저장합니다.
    tool_context.state[f"image_data_{page_number}"] = base64.b64encode(page_bytes).decode("utf-8")

    return {
        "status": "complete",
        "page_number": page_number,
        "filename": filename,
        "prompt_used": prompt[:120],
    }
