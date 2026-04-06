"""Report export utilities."""

from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("services.report_export")


async def export_markdown(session_id: str, report_content: str) -> Path:
    """Export a report as a Markdown file to the data directory.

    Returns the path to the saved file.
    """
    settings = get_settings()
    reports_dir = Path(settings.upload_path).parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    filename = f"report_{session_id}.md"
    path = reports_dir / filename
    path.write_text(report_content, encoding="utf-8")

    logger.info("Report exported to %s", path)
    return path
