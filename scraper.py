import json
import asyncio
from urllib.parse import urljoin
from playwright.async_api import async_playwright

CONCURRENCY_LIMIT = 4

async def check_channel(sem, context, name, ch_url, idx, total):
    async with sem:
        found_stream = None

        def handle_request(req):
            nonlocal found_stream
            u = req.url
            if (".m3u8" in u or "playlist.m3u8" in u or "chunklist" in u) and not found_stream:
                if not any(u.endswith(ext) for ext in [".js", ".css", ".html", ".png", ".jpg", ".svg"]):
                    found_stream = u

        page = await context.new_page()
        await page.route("**/*.{png,jpg,jpeg,svg,gif,webp,woff,woff2,css}", lambda r: r.abort())
        page.on("request", handle_request)

        print(f"[{idx}/{total}] {name} ...", end=" ", flush=True)

        try:
            await page.goto(ch_url, timeout=9000, wait_until="commit")
            await asyncio.sleep(1.5)

            # Səhifədəki və iframe daxilindəki video/audio elementlərini işə salırıq
            for frame in page.frames:
                try:
                    await frame.evaluate("""() => {
                        document.querySelectorAll('video, audio').forEach(v => {
                            v.muted = true;
                            v.play();
                        });
                    }""")
                except Exception:
                    pass

            await asyncio.sleep(1.5)
        except Exception:
            pass
        finally:
            await page.close()

        if found_stream:
            print("TAPILDI", flush=True)
            tv_link = f"{found_stream}|Referer={ch_url}&User-Agent=Mozilla/5.0"
            return f'#EXTINF:-1 tvg-name="{name}", {name}\n{tv_link}'
        else:
            print("yoxdur", flush=True)
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

        print(f"Əsas sayta daxil olunur: {target_site}", flush=True)
        page = await context.new_page()
        try:
            await page.goto(target_site, timeout=30000, wait_until="domcontentloaded")
            await asyncio.sleep(2)
        except Exception as e:
            print(f"Xəta: {e}", flush=True)
            await browser.close()
            return

        # 1. Saytdakı bütün menyu və kateqoriya linklərini toplayırıq
        cat_elements = await page.query_selector_all("a")
        category_urls = set([target_site])

        for cat in cat_elements:
            href = await cat.get_attribute("href")
            if href and any(k in href for k in ["kategori", "tur", "kanallar", "azerbaycan", "ulusal", "haber", "spor"]):
                full_cat = urljoin(target_site, href)
                if target_site in full_cat:
                    category_urls.add(full_cat)

        print(f"Tapılan kateqoriya səhifələri: {len(category_urls)} ədəd", flush=True)

        # 2. Hər kateqoriyanı açıb oradakı kanalları siyahıya yığırıq
        channel_links = {}
        for c_url in list(category_urls)[:12]: # Əsas 12 kateqoriyanı yoxlayır
            try:
                await page.goto(c_url, timeout=12000, wait_until="domcontentloaded")
                # Scroll edərək səhifəni tam açırıq
                for _ in range(4):
                    await page.mouse.wheel(0, 3500)
                    await asyncio.sleep(0.4)

                elements = await page.query_selector_all("a")
                for el in elements:
                    href = await el.get_attribute("href")
                    title = await el.inner_text()
                    if href and ("canli" in href or "izle" in href) and not href.startswith("#"):
                        full_ch = urljoin(target_site, href)
                        if full_ch not in channel_links.values() and full_ch != target_site:
                            raw_name = title.split("\n")[0].strip() if title else href.strip("/").split("/")[-1].replace("-", " ").title()
                            clean_name = raw_name.replace("Canlı", "").replace("İzle", "").replace("HD", "").strip()
                            if len(clean_name) > 1 and "Kategori" not in clean_name and "Televizyon" not in clean_name:
                                channel_links[clean_name] = full_ch
            except Exception:
                continue

        await page.close()
        total = len(channel_links)
        print(f"\nÜmumi çıxarılan unikal kanal sayı: {total}\n" + "="*40, flush=True)

        sem = asyncio.Semaphore(CONCURRENCY_LIMIT)
        tasks = []
        idx = 1
        for name, ch_url in channel_links.items():
            tasks.append(check_channel(sem, context, name, ch_url, idx, total))
            idx += 1

        results = await asyncio.gather(*tasks)
        await browser.close()

    active_channels = [r for r in results if r]
    m3u_content = "#EXTM3U\n" + "\n".join(active_channels)

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write(m3u_content)

    print(f"\nTamamlandı! {total} kanaldan {len(active_channels)} ədədi uğurla playlist.m3u faylına əlavə olundu.", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
