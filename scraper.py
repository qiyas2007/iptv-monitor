import json
import re
import urllib.request
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

def fetch_html(url):
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
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

    print(f"Bütün kanallar axtarılır: {target_site}", flush=True)

    # 1. Saytın sitemap və ya bütün səhifələrindən regex ilə bütün kanal linklərini dərhal çəkirik
    html = fetch_html(target_site)
    if not html:
        html = fetch_html(f"{target_site}/televizyonlar")

    # Bütün mümkün kanal url formatlarını çıxarırıq
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

    print(f"Ümumi aşkar edilən kanal sayı: {len(all_channels)} ədəd", flush=True)

    # 2. Hər bir kanalın yayımını sürətlə əldə edirik
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--autoplay-policy=no-user-gesture-required", "--no-sandbox", "--disable-gpu"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

        idx = 1
        total = len(all_channels)

        for name, url in all_channels.items():
            stream_url = None

            def handle_req(req):
                nonlocal stream_url
                u = req.url
                if (".m3u8" in u or "playlist" in u or "chunklist" in u) and not stream_url:
                    if not any(u.endswith(ext) for ext in [".js", ".css", ".html", ".png", ".jpg"]):
                        stream_url = u

            page = context.new_page()
            page.route("**/*.{png,jpg,jpeg,svg,gif,webp,woff,woff2,css}", lambda r: r.abort())
            page.on("request", handle_req)

            print(f"[{idx}/{total}] {name} ...", end=" ", flush=True)
            try:
                page.goto(url, timeout=7000, wait_until="commit")
                page.wait_for_timeout(1200)

                for frame in page.frames:
                    try:
                        frame.evaluate("""() => {
                            const v = document.querySelector('video');
                            if (v) { v.muted = true; v.play(); }
                        }""")
                    except Exception:
                        pass
                page.wait_for_timeout(1000)
            except Exception:
                pass
            finally:
                page.close()

            if stream_url:
                print("TAPILDI", flush=True)
                tv_link = f"{stream_url}|Referer={url}&User-Agent=Mozilla/5.0"
                m3u_lines.append(f'#EXTINF:-1 tvg-name="{name}", {name}')
                m3u_lines.append(tv_link)
            else:
                print("yoxdur", flush=True)

            idx += 1

        browser.close()

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print(f"\nUğurla tamamlandı! playlist.m3u faylına {len(m3u_lines) // 2} kanal yazıldı.", flush=True)

if __name__ == "__main__":
    main()
