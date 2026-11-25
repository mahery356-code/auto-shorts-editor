import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


def run_ffmpeg(args: List[str], capture_stderr: bool = False) -> subprocess.CompletedProcess:
    cmd = ["ffmpeg", "-y", *args]
    return subprocess.run(
        cmd,
        check=True,
        text=True,
        stdout=subprocess.PIPE if not capture_stderr else subprocess.PIPE,
        stderr=subprocess.PIPE if capture_stderr else subprocess.PIPE,
    )


def escape_ffmpeg_path(path: str) -> str:
    abs_path = os.path.abspath(path).replace("\\", "/")
    abs_path = abs_path.replace(":", "\\:")
    abs_path = abs_path.replace("'", "\\'")
    return abs_path


def detect_active_segments(
    input_path: str,
    total_duration: float,
    noise_db: float = -35.0,
    min_silence_sec: float = 0.8,
    min_clip_sec: float = 5.0,
) -> List[Tuple[float, float]]:
    """يكتشف الفترات النشطة صوتياً باستبعاد فترات الصمت الطويلة."""
    proc = run_ffmpeg(
        [
            "-i",
            input_path,
            "-af",
            f"silencedetect=noise={noise_db}dB:d={min_silence_sec}",
            "-f",
            "null",
            "-",
        ],
        capture_stderr=True,
    )

    stderr = proc.stderr or ""
    silence_starts = [float(x) for x in re.findall(r"silence_start:\s*([0-9.]+)", stderr)]
    silence_ends = [float(x) for x in re.findall(r"silence_end:\s*([0-9.]+)", stderr)]

    silences: List[Tuple[float, float]] = []
    for idx, start in enumerate(silence_starts):
        end = silence_ends[idx] if idx < len(silence_ends) else total_duration
        silences.append((max(0.0, start), min(total_duration, end)))

    active_segments: List[Tuple[float, float]] = []
    cursor = 0.0
    for s_start, s_end in silences:
        if s_start - cursor >= min_clip_sec:
            active_segments.append((round(cursor, 2), round(s_start, 2)))
        cursor = max(cursor, s_end)

    if total_duration - cursor >= min_clip_sec:
        active_segments.append((round(cursor, 2), round(total_duration, 2)))

    return active_segments


def get_media_duration(input_path: str) -> float:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            input_path,
        ],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return float(proc.stdout.strip())


def build_video_filter(
    subtitles_path: str | None = None,
    font_size: int = 20,
) -> str:
    filters = [
        "crop=ih*9/16:ih:(iw-ih*9/16)/2:0",
        "scale=1080:1920:flags=lanczos",
        "setsar=1",
    ]
    if subtitles_path:
        escaped_sub = escape_ffmpeg_path(subtitles_path)
        force_style = f"FontSize={font_size},PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=140"
        filters.append(f"subtitles='{escaped_sub}':force_style='{force_style}'")
    return ",".join(filters)


def render_clip(
    input_path: str,
    output_path: str,
    start: str | float | None = None,
    duration: str | float | None = None,
    subtitles_path: str | None = None,
    font_size: int = 20,
    normalize_audio: bool = False,
) -> None:
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    args: List[str] = []
    if start is not None:
        args.extend(["-ss", str(start)])
    if duration is not None:
        args.extend(["-t", str(duration)])

    args.extend(["-i", input_path])
    args.extend(["-vf", build_video_filter(subtitles_path=subtitles_path, font_size=font_size)])

    if normalize_audio:
        args.extend(["-af", "loudnorm=I=-16:TP=-1.5:LRA=11"])

    args.extend(
        [
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(out_file),
        ]
    )

    run_ffmpeg(args)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Automated YouTube Shorts generator built with Python and FFmpeg."
    )
    parser.add_argument("--input", required=True, help="Path to source video file.")
    parser.add_argument("--output", required=True, help="Output file path or output directory (with --auto-cut).")
    parser.add_argument("--start", default=None, help="Start timestamp (e.g. 00:00:10 or seconds).")
    parser.add_argument("--duration", default=None, help="Clip duration in seconds or HH:MM:SS.")
    parser.add_argument("--subtitles", default=None, help="Path to .srt or .ass subtitle file.")
    parser.add_argument("--font-size", type=int, default=20, help="Subtitle font size (default: 20).")
    parser.add_argument("--normalize-audio", action="store_true", help="Normalize audio loudness for Shorts.")
    parser.add_argument(
        "--auto-cut",
        action="store_true",
        help="Automatically detect active speech/sound segments and export clips.",
    )
    parser.add_argument(
        "--silence-threshold",
        type=float,
        default=-35.0,
        help="Silence noise threshold in dB for --auto-cut (default: -35.0).",
    )
    parser.add_argument(
        "--min-silence",
        type=float,
        default=0.8,
        help="Minimum silence duration in seconds (default: 0.8).",
    )
    parser.add_argument(
        "--min-clip",
        type=float,
        default=5.0,
        help="Minimum active clip length in seconds (default: 5.0).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_file = Path(args.input)
    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}", file=sys.stderr)
        return 1

    if args.subtitles and not Path(args.subtitles).exists():
        print(f"Error: Subtitle file not found: {args.subtitles}", file=sys.stderr)
        return 1

    try:
        if args.auto_cut:
            total_dur = get_media_duration(str(input_file))
            segments = detect_active_segments(
                input_path=str(input_file),
                total_duration=total_dur,
                noise_db=args.silence_threshold,
                min_silence_sec=args.min_silence,
                min_clip_sec=args.min_clip,
            )
            if not segments:
                print("No active segments matched the thresholds; exporting full converted video.")
                render_clip(
                    input_path=str(input_file),
                    output_path=str(Path(args.output) / f"{input_file.stem}_short_1.mp4"),
                    subtitles_path=args.subtitles,
                    font_size=args.font_size,
                    normalize_audio=args.normalize_audio,
                )
                return 0

            out_dir = Path(args.output)
            out_dir.mkdir(parents=True, exist_ok=True)
            for idx, (seg_start, seg_end) in enumerate(segments, start=1):
                seg_len = round(seg_end - seg_start, 2)
                out_path = out_dir / f"{input_file.stem}_short_{idx}.mp4"
                print(f"[{idx}/{len(segments)}] Rendering {seg_start}s -> {seg_end}s ({seg_len}s) => {out_path}")
                render_clip(
                    input_path=str(input_file),
                    output_path=str(out_path),
                    start=seg_start,
                    duration=seg_len,
                    subtitles_path=args.subtitles,
                    font_size=args.font_size,
                    normalize_audio=args.normalize_audio,
                )
            print("Done! All auto-cut Shorts exported.")
        else:
            render_clip(
                input_path=str(input_file),
                output_path=args.output,
                start=args.start,
                duration=args.duration,
                subtitles_path=args.subtitles,
                font_size=args.font_size,
                normalize_audio=args.normalize_audio,
            )
            print(f"Done! Saved Short to: {args.output}")
    except subprocess.CalledProcessError as exc:
        print(f"FFmpeg/FFprobe failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
