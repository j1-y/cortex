import json
import re
from typing import Any

from google import genai
from google.genai import types

from app.config import GEMINI_API_KEY


VISION_MODEL = "gemini-2.5-flash"
COLOR_ROLES = {"background", "text", "accent", "surface", "border", "unknown"}


def analyze_design_screenshot(
    image_bytes: bytes,
    mime_type: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is missing. Add it to .env before processing.")

    client = genai.Client(api_key=GEMINI_API_KEY)
    image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

    response = client.models.generate_content(
        model=VISION_MODEL,
        contents=[
            build_prompt(context),
            image_part,
        ],
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )

    try:
        raw_analysis = json.loads(response.text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Gemini returned malformed JSON.") from exc

    return normalize_analysis(raw_analysis)


def build_prompt(context: dict[str, Any]) -> str:
    title = context.get("title") or ""
    summary = context.get("summary") or ""
    url = context.get("url") or ""

    return f"""
You are analyzing a screenshot from a saved design/reference bookmark.
Analyze it from a product designer's perspective.

Bookmark context:
- title: {title}
- summary: {summary}
- url: {url}

Focus on UI layout, visual hierarchy, components, style, content, colors, and searchable keywords.
Extract visible text if possible. If exact colors are uncertain, estimate reasonable hex values.
Use lowercase-kebab-case for auto_tags.

Return ONLY valid JSON with this exact shape:
{{
  "visual_description": "string",
  "extracted_text": "string",
  "page_type": "string",
  "design_style": ["string"],
  "detected_components": [
    {{
      "type": "string",
      "label": "string",
      "confidence": 0.0
    }}
  ],
  "detected_colors": [
    {{
      "hex": "#FFFFFF",
      "role": "background|text|accent|surface|border|unknown",
      "confidence": 0.0
    }}
  ],
  "auto_tags": ["string"]
}}

Useful auto_tags include examples like landing-page, pricing-page, dashboard, dark-theme,
hero-section, bento-grid, glassmorphism, saas, ecommerce.

No markdown fences. No commentary.
""".strip()


def normalize_analysis(raw_analysis: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw_analysis, dict):
        raise ValueError("Gemini analysis JSON must be an object.")

    return {
        "visual_description": as_string(raw_analysis.get("visual_description")),
        "extracted_text": as_string(raw_analysis.get("extracted_text")),
        "page_type": as_string(raw_analysis.get("page_type")),
        "design_style": normalize_string_list(raw_analysis.get("design_style")),
        "detected_components": normalize_components(raw_analysis.get("detected_components")),
        "detected_colors": normalize_colors(raw_analysis.get("detected_colors")),
        "auto_tags": normalize_string_list(raw_analysis.get("auto_tags")),
    }


def normalize_components(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    components = []
    for item in value:
        if not isinstance(item, dict):
            continue

        components.append(
            {
                "type": as_string(item.get("type")) or "unknown",
                "label": as_string(item.get("label")),
                "confidence": clamp_confidence(item.get("confidence")),
            }
        )

    return components


def normalize_colors(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    colors = []
    for item in value:
        if not isinstance(item, dict):
            continue

        role = as_string(item.get("role")).lower()
        if role not in COLOR_ROLES:
            role = "unknown"

        colors.append(
            {
                "hex": normalize_hex_color(item.get("hex")),
                "role": role,
                "confidence": clamp_confidence(item.get("confidence")),
            }
        )

    return colors


def normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    return [text for item in value if (text := as_string(item))]


def as_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def clamp_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0

    return max(0.0, min(1.0, confidence))


def normalize_hex_color(value: Any) -> str:
    text = as_string(value).upper()
    if re.fullmatch(r"#[0-9A-F]{6}", text):
        return text
    return "#000000"
