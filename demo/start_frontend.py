#!/usr/bin/env python3
"""
Railway injects STREAMLIT_SERVER_PORT='$PORT' (literal string) which causes Streamlit to fail.
This script removes that bad value from the environment BEFORE any Streamlit import occurs,
then runs Streamlit in-process so Railway cannot re-inject the env var.
"""
import os
import sys

port = os.environ.get("PORT", "8501")

# Must happen before any streamlit import — Streamlit reads env vars on first import
os.environ.pop("STREAMLIT_SERVER_PORT", None)
os.environ["STREAMLIT_SERVER_PORT"] = str(port)

# Construct CLI args so streamlit picks up the port via --server.port as fallback
sys.argv = [
    "streamlit", "run", "frontend/app.py",
    "--server.address", "0.0.0.0",
    "--server.headless", "true",
    "--server.port", str(port),
]

# Run streamlit in-process (no exec/subprocess — Railway cannot re-inject env vars here)
from streamlit.web.cli import main
main()
