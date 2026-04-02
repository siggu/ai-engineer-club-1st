#!/usr/bin/env python3
import os
import sys

# Railway injects STREAMLIT_SERVER_PORT='$PORT' (literal string), not the expanded value.
# Read the actual port from PORT env var (which Railway sets correctly as a number).
port = os.environ.get("PORT", "8501")

# Overwrite STREAMLIT_SERVER_PORT with the real port number before exec'ing streamlit.
os.environ["STREAMLIT_SERVER_PORT"] = port

os.execlp(
    "/app/.venv/bin/streamlit",
    "streamlit", "run", "frontend/app.py",
    "--server.address", "0.0.0.0",
    "--server.headless", "true",
)
