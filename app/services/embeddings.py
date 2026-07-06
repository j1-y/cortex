from typing import Any

from google import genai
from google.genai import types

from app.config import GEMINI_API_KEY


EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768
MAX_EXTRACTED_TEXT_CHARS = 6000


def build_memory_embedding_text(memory: dict[str, Any]) -> str:
    sections = []

    add_section(sections, "Title", memory.get("title"))
    add_section(sections, "URL", memory.get("url"))
    add_section(sections, "Summary", memory.get("summary"))
    add_section(sections, "Visual Description", memory.get("visual_description"))
    add_section(
        sections,
        "Extracted Text",
        truncate_text(memory.get("extracted_text"), MAX_EXTRACTED_TEXT_CHARS),
    )
    add_section(
        sections,
        "Detected Components",
        format_detected_components(memory.get("detected_components")),
    )
    add_section(
        sections,
        "Detected Colors",
        format_detected_colors(memory.get("detected_colors")),
    )
    add_section(sections, "Auto Tags", format_string_list(memory.get("auto_tags")))

    content = "\n\n".join(sections).strip()
    if not content:
        raise ValueError("Memory does not contain enough content to embed")

    return content


def generate_text_embedding(text: str) -> list[float]:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is missing. Add it to .env before embedding.")

    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMENSIONS),
    )
    embedding = extract_embedding_values(response)

    if len(embedding) != EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"Gemini returned embedding dimension {len(embedding)}, expected {EMBEDDING_DIMENSIONS}."
        )

    return embedding


def format_vector_for_pgvector(embedding: list[float]) -> str:
    return "[" + ",".join(str(value) for value in embedding) + "]"


def extract_embedding_values(response: Any) -> list[float]:
    candidates = [
        lambda: response.embeddings[0].values,
        lambda: response.embedding.values,
        lambda: response.embeddings[0],
        lambda: response["embeddings"][0]["values"],
        lambda: response["embedding"]["values"],
        lambda: response["embeddings"][0],
    ]

    for get_candidate in candidates:
        try:
            candidate = get_candidate()
        except (AttributeError, IndexError, KeyError, TypeError):
            continue

        values = normalize_embedding_values(candidate)
        if values is not None:
            return values

    raise ValueError("Gemini embedding response did not contain embedding values.")


def normalize_embedding_values(candidate: Any) -> list[float] | None:
    if hasattr(candidate, "values"):
        candidate = candidate.values

    if not isinstance(candidate, list):
        return None

    try:
        return [float(value) for value in candidate]
    except (TypeError, ValueError):
        return None


def add_section(sections: list[str], label: str, value: Any) -> None:
    text = normalize_text(value)
    if text:
        sections.append(f"{label}:\n{text}")


def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    return str(value).strip()


def truncate_text(value: Any, max_chars: int) -> str:
    text = normalize_text(value)
    if len(text) <= max_chars:
        return text

    return text[:max_chars].rstrip() + "..."


def format_string_list(value: Any) -> str:
    if not isinstance(value, list):
        return normalize_text(value)

    items = [normalize_text(item) for item in value]
    return ", ".join(item for item in items if item)


def format_detected_components(value: Any) -> str:
    if not isinstance(value, list):
        return normalize_text(value)

    components = []
    for item in value:
        if isinstance(item, dict):
            component_type = normalize_text(item.get("type"))
            label = normalize_text(item.get("label"))
            if component_type and label:
                components.append(f"{component_type} ({label})")
            elif component_type:
                components.append(component_type)
            elif label:
                components.append(label)
        else:
            text = normalize_text(item)
            if text:
                components.append(text)

    return ", ".join(components)


def format_detected_colors(value: Any) -> str:
    if not isinstance(value, list):
        return normalize_text(value)

    colors = []
    for item in value:
        if isinstance(item, dict):
            hex_value = normalize_text(item.get("hex"))
            role = normalize_text(item.get("role"))
            if hex_value and role:
                colors.append(f"{hex_value} {role}")
            elif hex_value:
                colors.append(hex_value)
            elif role:
                colors.append(role)
        else:
            text = normalize_text(item)
            if text:
                colors.append(text)

    return ", ".join(colors)
