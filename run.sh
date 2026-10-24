#!/bin/bash
cd "$(dirname "$0")"
.venv/bin/streamlit run app.py --server.port 8511 --server.headless true
