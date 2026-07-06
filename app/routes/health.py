from fastapi import APIRouter, HTTPException
from psycopg import Error as PsycopgError

from app.database import get_connection


router = APIRouter()


@router.get("/health")
def health_check():
    conn = None

    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            result = cur.fetchone()[0]

        return {
            "status": "ok",
            "database": "connected",
            "result": result,
        }
    except PsycopgError as exc:
        raise HTTPException(
            status_code=500,
            detail="Database health check failed.",
        ) from exc
    finally:
        if conn is not None:
            conn.close()
