#!/usr/bin/env python3
"""Render the |OCTO> scene to MP4.

The scene (index.html) exposes a deterministic `window.frame(t)` that draws
time `t` (seconds) to a 1920x1080 canvas and returns a JPEG data URL. This
script drives it headlessly with Playwright, splits the timeline across
parallel workers, pipes the frames straight into ffmpeg, then joins the
segments and muxes the synthesized soundtrack.

    python render/render.py                     # full 28 s @ 30 fps
    python render/render.py --fps 60 --workers 4
    python render/render.py --start 10 --end 15 --out tunnel.mp4
"""
import argparse
import asyncio
import base64
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
SCENE = (ROOT / "index.html").as_uri() + "?render"


def ffmpeg_writer(path: Path, fps: int, crf: int) -> subprocess.Popen:
    return subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg", "-i", "-",
         "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
         "-pix_fmt", "yuv420p", str(path)],
        stdin=subprocess.PIPE,
    )


async def worker(idx: int, frames: list[float], seg: Path, args) -> None:
    ff = ffmpeg_writer(seg, args.fps, args.crf)
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--allow-file-access-from-files"])
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        page.on("pageerror", lambda e: print(f"[w{idx}] page error: {e}", file=sys.stderr))
        await page.goto(SCENE)
        await page.evaluate("window.ready")
        for n, t in enumerate(frames):
            data = await page.evaluate(f"window.frame({t:.6f}, {args.quality})")
            ff.stdin.write(base64.b64decode(data.split(",", 1)[1]))
            if idx == 0 and n % 60 == 0:
                print(f"  worker 0: {n}/{len(frames)} frames", flush=True)
        await browser.close()
    ff.stdin.close()
    if ff.wait() != 0:
        raise RuntimeError(f"ffmpeg failed on segment {idx}")


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=28.0)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--crf", type=int, default=17, help="x264 quality (lower = better)")
    ap.add_argument("--quality", type=float, default=0.95, help="JPEG quality of captured frames")
    ap.add_argument("--audio", default=str(ROOT / "media" / "soundtrack.wav"),
                    help="WAV to mux; generated with render/audio.py if missing")
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "media" / "quantum-octopus.mp4"))
    args = ap.parse_args()

    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found on PATH")

    total = round((args.end - args.start) * args.fps)
    times = [args.start + i / args.fps for i in range(total)]
    chunks = [times[i * total // args.workers:(i + 1) * total // args.workers] for i in range(args.workers)]
    print(f"Rendering {total} frames ({args.start}-{args.end}s @ {args.fps}fps) with {args.workers} workers")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        segs = [tmp / f"seg{i}.mp4" for i in range(args.workers)]
        await asyncio.gather(*(worker(i, c, s, args) for i, (c, s) in enumerate(zip(chunks, segs))))
        (tmp / "list.txt").write_text("".join(f"file '{s}'\n" for s in segs))
        video = tmp / "video.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                        "-i", str(tmp / "list.txt"), "-c", "copy", str(video)], check=True)

        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        if args.no_audio:
            shutil.copy(video, out)
        else:
            audio = Path(args.audio)
            if not audio.exists():
                subprocess.run([sys.executable, str(ROOT / "render" / "audio.py"), "--out", str(audio)], check=True)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video),
                            "-ss", str(args.start), "-i", str(audio),
                            "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", str(out)], check=True)
    print(f"Done → {out}")


if __name__ == "__main__":
    asyncio.run(main())
