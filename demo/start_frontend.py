#!/usr/bin/env python3
import os
import sys

# DEBUG: print env state so we can see in Railway logs
print("=== START_FRONTEND.PY RUNNING ===", flush=True)
print(f"PORT={os.environ.get('PORT', 'NOT_SET')}", flush=True)
print(f"STREAMLIT_SERVER_PORT={os.environ.get('STREAMLIT_SERVER_PORT', 'NOT_SET')}", flush=True)

port = os.environ.get("PORT", "8501")

os.environ.pop("STREAMLIT_SERVER_PORT", None)
os.environ["STREAMLIT_SERVER_PORT"] = str(port)

print(f"STREAMLIT_SERVER_PORT after fix={os.environ.get('STREAMLIT_SERVER_PORT')}", flush=True)
print("=== STARTING STREAMLIT ===", flush=True)

sys.argv = [
    "streamlit", "run", "frontend/app.py",
    "--server.address", "0.0.0.0",
    "--server.headless", "true",
    "--server.port", str(port),
]

from streamlit.web.cli import main
main()
