#!/usr/bin/env python3
"""Script to re-encode all existing AI-generated videos to H.264 (avc1) for web playback."""
import sys
sys.path.insert(0, 'app')

from video_diffusion_generator import reencode_to_h264, _verify_h264
from pathlib import Path

VIDEO_DIR = Path("videos/ai_generated")

def main():
    if not VIDEO_DIR.exists():
        print(f"Video directory not found: {VIDEO_DIR}")
        return 1

    video_files = sorted(VIDEO_DIR.glob("ai_video_*.mp4"))
    if not video_files:
        print("No AI video files found to re-encode")
        return 0

    print(f"Found {len(video_files)} video(s) to check")
    
    reencoded = 0
    skipped = 0
    failed = 0

    for video_path in video_files:
        if video_path.stem.endswith("_h264"):
            print(f"Skipping already re-encoded: {video_path.name}")
            skipped += 1
            continue

        if _verify_h264(video_path):
            print(f"Already H.264: {video_path.name}")
            skipped += 1
            continue

        print(f"Re-encoding: {video_path.name}...")
        try:
            output_path = reencode_to_h264(video_path)
            print(f"  -> Success: {output_path.name}")
            reencoded += 1
        except Exception as e:
            print(f"  -> FAILED: {e}")
            failed += 1

    print(f"\nSummary: {reencoded} re-encoded, {skipped} skipped, {failed} failed")
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())