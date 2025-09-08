#!/bin/bash
# MetaHuman Streamer GUI - Installation and Run Script

echo "Installing MetaHuman Streamer GUI dependencies..."
pip install -r requirements.txt

echo "Starting MetaHuman Streamer GUI..."
python mh_streamer_gui.py
