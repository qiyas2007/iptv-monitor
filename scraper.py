import json
import re
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

def run():
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    target_site = config.get("target_site", "").rstrip("/")
    if not target_site:
        print("Sayt linki tapılmadı!")
        return

    m3u_lines = ["#EXTM3U"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print(f"Əsas sayta daxil olunur: {target_site}")
        try:
            page.goto(target_site, timeout=60000)
            page.wait_for_timeout(3000)
        except Exception as e:
            print(f"Əsas səhifə açılmadı: {e}")
            browser.close()
            return

        # Səhifədəki bütün daxili linkləri toplayırıq
        elements = page.query_selector_all("a")
        channel_links = {}

        for el in elements:
            href = el.get_attribute("href")
            title = el.inner_text().strip()
            
            if href and ("izle" in href or "canli" in href) and not href.startswith("#"):
                full_url = urljoin(target_site, href)
                # Təkrarlanmanın qarşısını almaq və adı təmizləmək
                clean_name = title.split("\n")[0].strip() if title else href.split("/")[-2].replace("-", " ").title()
                if len(clean_name) > 1 and full_url not in channel_links.values():
                    channel_links[clean_name] = full_url

        print(f"Tapılan potensial kanallar: {len(channel_links)}")

        # Hər bir kanal səhifəsinə girib .m3u8 tapırıq
        for name, ch_url in channel_links.items():
            found_stream = None

            def handle_request(request):
                nonlocal found_stream
                if ".m3u8" in request.url and not found_stream:
                    found_stream = request.url

            ch_page = context.new_page()
            ch_page.on("request", handle_request)

            print(f"Axtarılır: {name} ({ch_url})")
            try:
                ch_page.goto(ch_url, timeout=25000)
                # Pleyerin işə düşməsi üçün qısa gözləmə
                ch_page.wait_for_timeout(4000)
            except Exception:
                pass

            ch_page.close()

            if found_stream:
                print(f"-> Tapıldı: {found_stream}")
                # TV üçün xüsusi boru (|) formatı ilə referer əlavə edirik
                tv_link = f"{found_stream}|Referer={ch_url}&User-Agent=Mozilla/5.0"
                m3u_lines.append(f'#EXTINF:-1 tvg-name="{name}", {name}')
                m3u_lines.append(tv_link)
            else:
                print(f"-> Stream tapılmadı.")

        browser.close()

    # Yekun m3u faylını yazırıq
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print("Yenilənmə tamamlandı! playlist.m3u faylı hazırlandı.")

if __name__ == "__main__":
    run()
