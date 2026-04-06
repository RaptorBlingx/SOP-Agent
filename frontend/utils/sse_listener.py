"""SSE event listener for real-time execution updates."""

from __future__ import annotations

import json
from typing import Generator
import httpx

from frontend.utils.api_client import get_api_url


def listen_sse(session_id: str) -> Generator[dict, None, None]:
    """Connect to the SSE stream and yield parsed events.

    Yields dicts with 'event' and 'data' keys.
    """
    url = f"{get_api_url()}/api/v1/execute/{session_id}/stream"

    with httpx.Client(timeout=None) as client:
        with client.stream("GET", url) as response:
            event_type = "message"
            data_buffer = ""

            for line in response.iter_lines():
                if line.startswith("event:"):
                    event_type = line[6:].strip()
                elif line.startswith("data:"):
                    data_buffer = line[5:].strip()
                elif line == "":
                    # End of event
                    if data_buffer:
                        try:
                            parsed = json.loads(data_buffer)
                        except json.JSONDecodeError:
                            parsed = {"raw": data_buffer}

                        yield {"event": event_type, "data": parsed}

                        if event_type in ("done", "error"):
                            return

                    event_type = "message"
                    data_buffer = ""
