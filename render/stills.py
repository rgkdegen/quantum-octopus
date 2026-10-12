#!/usr/bin/env python3
"""Grab single frames from the scene as PNG — handy for thumbnails and for
checking a moment without rendering the whole clip.

    python render/stills.py 5.5 12.2 17.5 21.8 26
"""
import asyncio
import base64
import sys
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent


async def main(times: list[float], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--allow-file-access-from-files"])
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        await page.goto((ROOT / "index.html").as_uri() + "?render")
        await page.evaluate("window.ready")
        for t in times:
            data = await page.evaluate(f"(window.render({t}), document.getElementById('c').toDataURL('image/png'))")
            path = out_dir / f"frame_{t:05.2f}s.png"
            path.write_bytes(base64.b64decode(data.split(",", 1)[1]))
            print(path)
        await browser.close()


if __name__ == "__main__":
    ts = [float(a) for a in sys.argv[1:]] or [0.5, 5.5, 12.2, 17.5, 21.8, 26.0]
    asyncio.run(main(ts, ROOT / "stills"))
