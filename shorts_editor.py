import argparse
import subprocess
from pathlib import Path


def create_short(input_path: str, output_path: str, start_time: str = "00:00:00", duration: int = 45) -> None:
    src = Path(input_path)
    dst = Path(output_path)

    if not src.exists():
        raise FileNotFoundError(f"Input video not found: {src}")

    dst.parent.mkdir(parents=True, exist_ok=True)

    # Crop/scale to vertical 9:16 (1080x1920) for YouTube Shorts
    vf_filter = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        start_time,
        "-i",
        str(src),
        "-t",
        str(duration),
        "-vf",
        vf_filter,
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        str(dst),
    ]

    subprocess.run(cmd, check=True)
    print(f"Short created successfully: {dst}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Automated YouTube Shorts video processor.")
    parser.add_argument("--input", required=True, help="Path to source video file")
    parser.add_argument("--output", required=True, help="Path to output Short MP4 file")
    parser.add_argument("--start", default="00:00:00", help="Start timestamp (HH:MM:SS)")
    parser.add_argument("--duration", type=int, default=45, help="Clip duration in seconds")
    args = parser.parse_args()

    create_short(args.input, args.output, args.start, args.duration)


if __name__ == "__main__":
    main()
