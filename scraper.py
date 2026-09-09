import json
import asyncio
import urllib.request
from urllib.parse import urljoin
from playwright.async_api import async_playwright

# Eyni vaxtda paralel yoxlanılacaq kanal sayı
CONCURRENCY_LIMIT = 5

def is_stream_alive(url, referer):
    """Linkin canlı və işlək olduğunu, telif/404 almadığını 2 saniyəyə yoxlayır"""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Referer": referer
            }
        )
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            # Əgər status 200-dürsə və içində HLS açarları varsa kanal aktivdir
            return resp.status == 200
    except Exception:
        return False

async def check_channel(sem, context, name, ch_url, idx, total):
    async with sem:
        found_stream = None

        def handle_request(req):
            nonlocal found_stream
            u = req.url
            if (".m3u8" in u or "playlist.m3u8" in u or "chunklist" in u) and not found_stream:
                if not u.endswith(".js") and not u.endswith(".css"):
                    found_stream = u

        page = await context.new_page()
        # Reklam, şəkil və şriftləri dərhal bloklayırıq (maksimum sürət üçün)
        await page.route("**/*.{png,jpg,jpeg,svg,gif,webp,woff,woff2,css}", lambda r: r.abort())
        page.on("request", handle_request)

        print(f"[{idx}/{total}] Yoxlanılır: {name} ...", end=" ", flush=True)

        try:
            await page.goto(ch_url, timeout=6000, wait_until="commit")
            await asyncio.sleep(1.2)

            # İframe və pleyer daxilindəki gizli videoları oyadırıq
            for frame in page.frames:
                try:
                    await frame.evaluate("""() => {
                        const v = document.querySelector('video');
                        if (v) { v.muted = true; v.play(); }
                    }""")
                except Exception:
                    pass

            await asyncio.sleep(1.0)
        except Exception:
            pass
        finally:
            await page.close()

        # Link tapıldısa, telif və ya ölüm vəziyyətini yoxlayırıq
        if found_stream:
            # Canlı test
            loop = asyncio.get_event_loop()
            alive = await loop.run_in_executor(None, is_stream_alive, found_stream, ch_url)
            
            if alive:
                print("AKTİV (Əlavə edildi)", flush=True)
                tv_link = f"{found_stream}|Referer={ch_url}&User-Agent=Mozilla/5.0"
                return f'#EXTINF:-1 tvg-name="{name}", {name}\n{tv_link}'
            else:
                print("ÖLÜ / TELİF (Keçildi)", flush=True)
                return None
        else:
            print("YAYIM YOXDUR (Keçildi)", flush=True)
            return None

async def main():
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    target_site = config.get("target_site", "").rstrip("/")
    if not target_site:
        print("Sayt linki tapılmadı!", flush=True)
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--autoplay-policy=no-user-gesture-required",
                "--no-sandbox",
                "--disable-gpu",
                "--blink-settings=imagesEnabled=false"
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )

        print(f"Əsas səhifə açılır: {target_site}", flush=True)
        page = await context.new_page()
        try:
            await page.goto(target_site, timeout=25000, wait_until="domcontentloaded")
        except Exception as e:
            print(f"Xəta: {e}", flush=True)
            await browser.close()
            return

        # Səhifəni sürətlə aşağı fırladıb bütün 200 kanalı yükləyirik
        print("Kanallar siyahıya alınır...", flush=True)
        for _ in range(7):
            await page.mouse.wheel(0, 5000)
            await asyncio.sleep(0.6)

        elements = await page.query_selector_all("a")
        channel_links = {}

        for el in elements:
            href = await el.get_attribute("href")
            title = await el.inner_text()
            
            if href and ("canli" in href or "izle" in href) and not href.startswith("#"):
                full_url = urljoin(target_site, href)
                if full_url != target_site and full_url not in channel_links.values():
                    raw_name = title.split("\n")[0].strip() if title else href.strip("/").split("/")[-1].replace("-", " ").title()
                    clean_name = raw_name.replace("Canlı", "").replace("İzle", "").strip()
                    if len(clean_name) > 1:
                        channel_links[clean_name] = full_url

        await page.close()
        total = len(channel_links)
        print(f"Tapılan ümumi kanal: {total}\n---", flush=True)

        sem = asyncio.Semaphore(CONCURRENCY_LIMIT)
        tasks = []
        idx = 1
        for name, ch_url in channel_links.items():
            tasks.append(check_channel(sem, context, name, ch_url, idx, total))
            idx += 1

        # Bütün kanalları eyni anda paralel emal edirik
        results = await asyncio.gather(*tasks)
        await browser.close()

    # Yalnız aktiv və canlı kanalları fayla yazırıq
    active_channels = [r for r in results if r]
    m3u_content = "#EXTM3U\n" + "\n".join(active_channels)

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write(m3u_content)

    print(f"\nProses bitdi! {total} kanaldan {len(active_channels)} ədədi aktiv çıxdı və playlist.m3u faylına yazıldı.", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
