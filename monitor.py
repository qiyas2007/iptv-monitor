import asyncio
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

BASE = Path(__file__).resolve().parent
CHANNELS_FILE = BASE / "channels.json"
OUTPUT_DIR = BASE / "output"
OUTPUT_FILE = OUTPUT_DIR / "channels.m3u"

# Səhifənin player-i gec yüklənirsə bunu artır.
WAIT_AFTER_LOAD_SECONDS = 8

# Eyni səhifədə bir neçə playlist tapıla bilər.
# Sadə seçim qaydası: son tapılan m3u8.
M3U8_RE = re.compile(r"\.m3u8(?:[?#]|$)", re.I)


def load_channels():
    with CHANNELS_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("channels.json list formatında olmalıdır.")

    return data


def is_m3u8(url: str) -> bool:
    return bool(M3U8_RE.search(url))


def make_extinf(name: str) -> str:
    safe_name = name.replace("\n", " ").strip()
    return f"#EXTINF:-1,{safe_name}"


async def capture_channel(browser, channel):
    name = channel["name"]
    page_url = channel["page_url"]

    page = await browser.new_page()
    found = []

    async def on_request(request):
        url = request.url
        if is_m3u8(url):
            found.append(url)

    page.on("request", on_request)

    try:
        await page.goto(page_url, wait_until="domcontentloaded", timeout=60_000)
        await page.wait_for_timeout(WAIT_AFTER_LOAD_SECONDS * 1000)

        # Player-in başlanmasına kömək edə biləcək adi hərəkət.
        # Heç bir auth/DRM bypass edilmir.
        try:
            await page.mouse.move(400, 300)
            await page.mouse.click(400, 300)
        except Exception:
            pass

        await page.wait_for_timeout(3_000)

        # Təkrarlanan URL-ləri saxlamadan sonuncunu seçirik.
        unique = list(dict.fromkeys(found))
        if not unique:
            return name, page_url, None, "m3u8 tapılmadı"

        return name, page_url, unique[-1], None

    except Exception as exc:
        return name, page_url, None, str(exc)

    finally:
        await page.close()


async def main():
    channels = load_channels()
    OUTPUT_DIR.mkdir(exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage"]
        )

        results = []
        for index, channel in enumerate(channels, start=1):
            print(f"[{index}/{len(channels)}] {channel['name']}")
            result = await capture_channel(browser, channel)
            results.append(result)

        await browser.close()

    lines = ["#EXTM3U"]
    ok = 0

    for name, page_url, stream_url, error in results:
        if stream_url:
            lines.append(make_extinf(name))
            lines.append(stream_url)
            ok += 1
            print(f"  OK: {stream_url}")
        else:
            print(f"  FAIL: {error} | {page_url}")

    OUTPUT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print()
    print(f"Yeniləndi: {OUTPUT_FILE}")
    print(f"Tapılan kanallar: {ok}/{len(channels)}")


if __name__ == "__main__":
    asyncio.run(main())
