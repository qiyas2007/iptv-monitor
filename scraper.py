import json
import re
import urllib.request
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

def fetch_html(url):
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode('utf-8', errors='ignore')
    except Exception:
        return ""

def main():
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    target_site = config.get("target_site", "").rstrip("/")
    if not target_site:
        print("Sayt linki tapılmadı!", flush=True)
        return

    m3u_lines = ["#EXTM3U"]
    all_channels = {}

    print(f"Bütün kanallar toplanır: {target_site}", flush=True)

    html = fetch_html(target_site)
    if not html:
        print("Sayt kodunu oxumaq mümkün olmadı!", flush=True)
        return

    # Səhifədəki bütün kanal keçidlərini toplayırıq
    matches = re.findall(r'href=["\'](/[^"\']*(?:canli|izle|tv)[^"\']*)["\']', html, re.IGNORECASE)
    matches += re.findall(r'href=["\'](https?://[^"\']*(?:canli|izle)[^"\']*)["\']', html, re.IGNORECASE)

    for m in set(matches):
        full = urljoin(target_site, m)
        if any(skip in full for skip in ["iletisim", "gizlilik", "hakkimizda", "yayin-akisi", "kategori", "blog", "tags"]):
            continue
        slug = full.rstrip("/").split("/")[-1].replace("-canli-izle", "").replace("-izle", "").replace("-canli", "")
        name = slug.replace("-", " ").title()
        if len(name) > 1 and full != target_site:
            all_channels[name] = full

    print(f"Tapılan ümumi kanal: {len(all_channels)} ədəd\n", flush=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--autoplay-policy=no-user-gesture-required",
                "--no-sandbox",
                "--disable-web-security"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )

        idx = 1
        total = len(all_channels)

        for name, url in all_channels.items():
            stream_url = None

            def handle_req(req):
                nonlocal stream_url
                u = req.url
                # m3u8 və ya playlist aşkar edildikdə tuturuq
                if (".m3u8" in u or "playlist" in u or "chunklist" in u) and not stream_url:
                    if not any(u.endswith(ext) for ext in [".js", ".css", ".html", ".png", ".jpg", ".svg", ".ts"]):
                        stream_url = u

            page = context.new_page()
            page.on("request", handle_req)

            print(f"[{idx}/{total}] {name} ...", end=" ", flush=True)
            try:
                # Səhifənin DOM kodunun yüklənməsini gözləyirik
                page.goto(url, timeout=12000, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)

                # 1. Pleyerin üzərinə real klik atırıq (Pleyer adətən səhifənin mərkəzində olur)
                page.mouse.click(640, 360)

                # 2. İframe və ya birbaşa səhifədəki videonu 'play' edirik
                for frame in page.frames:
                    try:
                        frame.evaluate("""() => {
                            const v = document.querySelector('video');
                            if (v) {
                                v.muted = true;
                                v.play();
                            }
                            // Bəzi saytlarda play düyməsi class-la olur
                            const btn = document.querySelector('.vjs-big-play-button, .jw-display-icon-container, #play, .play-btn');
                            if (btn) btn.click();
                        }""")
                    except Exception:
                        pass

                # m3u8 sorğusunun şəbəkəyə düşməsi üçün 3 saniyə möhlət
                for _ in range(6):
                    if stream_url:
                        break
                    page.wait_for_timeout(500)

            except Exception:
                pass
            finally:
                page.close()

            if stream_url:
                print("TAPILDI!", flush=True)
                tv_link = f"{stream_url}|Referer={url}&User-Agent=Mozilla/5.0"
                m3u_lines.append(f'#EXTINF:-1 tvg-name="{name}", {name}')
                m3u_lines.append(tv_link)
            else:
                print("yoxdur", flush=True)

            idx += 1

        browser.close()

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print(f"\nUğurla tamamlandı! playlist.m3u faylına cəmi {len(m3u_lines) // 2} kanal yazıldı.", flush=True)

if __name__ == "__main__":
    main()
