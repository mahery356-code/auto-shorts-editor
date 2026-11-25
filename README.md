# auto-shorts-editor

Open-source automated video editing and YouTube Shorts generator built with Python and FFmpeg.

## Features
- Crops and scales source videos to vertical 9:16 (1080x1920) format suitable for YouTube Shorts.
- Extracts clips by start timestamp and duration via a clean CLI interface.
- Designed as a modular base for adding auto-captions, highlight detection, and batch workflows.

## Prerequisites
- Python 3.9+
- ffmpeg installed and available in your system PATH

## Usage
python shorts_editor.py --input input.mp4 --output out/short_1.mp4 --start 00:00:10 --duration 45

## License
MIT
