import re
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from app.database import get_connection
from app.services.image_loader import download_image
from app.services.vision import VISION_MODEL, analyze_design_screenshot


class MemoryNotFoundError(Exception):
    pass


class MemoryProcessingError(Exception):
    pass


def get_memory(memory_id: UUID) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, summary, url, screenshot_url, processing_status
                FROM cortex_memories
                WHERE id = %s
                """,
                (memory_id,),
            )
            row = cur.fetchone()

        if row is None:
            return None

        return {
            "id": row[0],
            "title": row[1],
            "summary": row[2],
            "url": row[3],
            "screenshot_url": row[4],
            "processing_status": row[5],
        }
    finally:
        conn.close()


def mark_processing(memory_id: UUID) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE cortex_memories
                SET
                    processing_status = %s,
                    processing_error = NULL,
                    updated_at = now()
                WHERE id = %s
                """,
                ("processing", memory_id),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def mark_completed(memory_id: UUID, analysis: dict[str, Any]) -> str:
    conn = get_connection()
    try:
        columns = get_cortex_memory_columns(conn)
        update_fields = [
            "visual_description = %s",
            "extracted_text = %s",
            "auto_tags = %s",
            "processing_status = %s",
            "processing_error = NULL",
        ]
        update_params: list[Any] = [
            analysis["visual_description"],
            analysis["extracted_text"],
            analysis["auto_tags"],
            "completed",
        ]

        if "detected_components" in columns:
            insert_update_field(
                update_fields,
                update_params,
                2,
                "detected_components = %s",
                Jsonb(analysis["detected_components"]),
            )

        if "detected_colors" in columns:
            color_index = 3 if "detected_components" in columns else 2
            insert_update_field(
                update_fields,
                update_params,
                color_index,
                "detected_colors = %s",
                Jsonb(analysis["detected_colors"]),
            )

        if "model_version" in columns:
            update_fields.append("model_version = %s")
            update_params.append(VISION_MODEL)

        update_fields.append("updated_at = now()")
        update_params.append(memory_id)

        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE cortex_memories
                SET {", ".join(update_fields)}
                WHERE id = %s
                RETURNING processing_status
                """,
                update_params,
            )
            row = cur.fetchone()

        conn.commit()
        return row[0]
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def mark_failed(memory_id: UUID, error_message: str) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE cortex_memories
                SET
                    processing_status = %s,
                    processing_error = %s,
                    updated_at = now()
                WHERE id = %s
                """,
                ("failed", clean_error_message(error_message), memory_id),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def process_memory(memory_id: UUID) -> dict[str, Any]:
    memory = get_memory(memory_id)
    if memory is None:
        raise MemoryNotFoundError("Memory not found")

    try:
        mark_processing(memory_id)

        screenshot_url = memory.get("screenshot_url")
        if not screenshot_url:
            raise MemoryProcessingError("Memory does not have a screenshot_url to analyze")

        image_bytes, mime_type = download_image(str(screenshot_url))
        analysis = analyze_design_screenshot(
            image_bytes=image_bytes,
            mime_type=mime_type,
            context={
                "title": memory.get("title"),
                "summary": memory.get("summary"),
                "url": memory.get("url"),
            },
        )
        analysis["auto_tags"] = build_auto_tags(analysis)

        processing_status = mark_completed(memory_id, analysis)
        analysis["memory_id"] = memory_id
        analysis["processing_status"] = processing_status

        return analysis
    except Exception as exc:
        try:
            mark_failed(memory_id, clean_error_message(str(exc)))
        except Exception:
            pass

        if isinstance(exc, MemoryProcessingError):
            raise

        raise MemoryProcessingError("Processing failed") from exc


def get_cortex_memory_columns(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'cortex_memories'
            """
        )
        return {row[0] for row in cur.fetchall()}


def insert_update_field(
    update_fields: list[str],
    update_params: list[Any],
    index: int,
    field: str,
    value: Any,
) -> None:
    update_fields.insert(index, field)
    update_params.insert(index, value)


def build_auto_tags(analysis: dict[str, Any]) -> list[str]:
    tags = []
    tags.extend(analysis.get("auto_tags", []))

    page_type = analysis.get("page_type")
    if page_type:
        tags.append(page_type)

    tags.extend(analysis.get("design_style", []))

    normalized_tags = []
    seen = set()
    for tag in tags:
        normalized = to_kebab_case(str(tag))
        if normalized and normalized not in seen:
            normalized_tags.append(normalized)
            seen.add(normalized)

    return normalized_tags


def to_kebab_case(value: str) -> str:
    text = value.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def clean_error_message(message: str) -> str:
    cleaned = message.strip()
    if not cleaned:
        return "Processing failed"
    return cleaned[:500]
