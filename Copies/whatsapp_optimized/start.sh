#!/bin/bash
# Render start script - MUST import logging_config FIRST

cd backend

# Use Python to run wsgi.py which imports logging_config first
exec python -c "
import logging_config
from wsgi import app
from waitress import serve
import os

host = os.getenv('HOST', '0.0.0.0')
port = int(os.getenv('PORT', 5000))

print(f'[RENDER] Starting FairTax backend on {host}:{port}')
serve(app, host=host, port=port, threads=4)
"
