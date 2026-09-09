import json
import sys
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

def run():
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    target_site = config.get("target_site", "").rstrip("/")
    if not target_site:
        print("Sayt linki tapılmadı!", flush=True)
        return

    m3u_lines = ["#EXTM3U"]

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--autoplay-policy=no-user-gesture-required", "--no-sandbox"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        
        # Şəkilləri və reklam fontlarını bloklayırıq ki, səhifələr 1 saniyəyə açılsın
        page = context.new_page()
        page.route("**/*.{png,jpg,jpeg,svg,gif,webp,woff,woff2}", lambda route: route.abort())

        print(f"Əsas sayta daxil olunur: {target_site}", flush=True)
        try:
            page.goto(target_site, timeout=30000)
            page.wait_for_timeout(2000)
        except Exception as e:
            print(f"Əsas səhifə açılmadı: {e}", flush=True)
            browser.close()
            return

        elements = page.query_selector_all("a")
        channel_links = {}

        for el in elements:
            href = el.get_attribute("href")
            title = el.inner_text().strip()
            
            if href and ("izle" in href or "canli" in href) and not href.startswith("#"):
                full_url = urljoin(target_site, href)
                clean_name = title.split("\n")[0].strip() if title else href.split("/")[-2].replace("-", " ").title()
                if len(clean_name) > 1 and full_url not in channel_links.values():
                    channel_links[clean_name] = full_url

        print(f"Tapılan potensial kanallar: {len(channel_links)} ədəd\n", flush=True)

        for name, ch_url in channel_links.items():
            found_stream = None

            def handle_request(request):
                nonlocal found_stream
                url = request.url
                if (".m3u8" in url or "playlist" in url or "chunklist" in url) and not found_stream:
                    if not url.endswith(".js") and not url.endswith(".css"):
                        found_stream = url

            ch_page = context.new_page()
            ch_page.route("**/*.{png,jpg,jpeg,svg,gif,webp,woff,woff2}", lambda route: route.abort())
            ch_page.on("request", handle_request)

            print(f"Yoxlanılır: {name} ...", end=" ", flush=True)
            try:
                ch_page.goto(ch_url, timeout=15000)
                ch_page.wait_for_timeout(1000)
                ch_page.mouse.click(350, 250)
                ch_page.evaluate("""() => {
                    const v = document.querySelector('video');
                    if (v) { v.muted = true; v.play(); }
                }""")
                ch_page.wait_for_timeout(2500)
            except Exception:
                pass

            ch_page.close()

            if found_stream:
                print("TAPILDI!", flush=True)
                tv_link = f"{found_stream}|Referer={ch_url}&User-Agent=Mozilla/5.0"
                m3u_lines.append(f'#EXTINF:-1 tvg-name="{name}", {name}')
                m3u_lines.append(tv_link)
            else:
                print("yoxdur", flush=True)

        browser.close()

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print("\nTamamlandı! Bütün kanallar playlist.m3u faylına yazıldı.", flush=True)

if __name__ == "__main__":
    run()
