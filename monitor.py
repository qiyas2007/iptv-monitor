import json
import os
from playwright.sync_api import sync_playwright

def main():
    json_path = "channels.json"
    output_dir = "output"
    output_file = os.path.join(output_dir, "channels.m3u")
    
    os.makedirs(output_dir, exist_ok=True)
    
    if not os.path.exists(json_path):
        print(f"Xəta: {json_path} tapılmadı!")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        channels = json.load(f)

    m3u_lines = ["#EXTM3U"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        for ch in channels:
            name = ch.get("name", "Kanal")
            url = ch.get("page_url", "")
            found_stream = None

            if not url:
                continue

            print(f"Yoxlanılır: {name} -> {url}")
            page = context.new_page()

            def handle_request(request):
                nonlocal found_stream
                if ".m3u8" in request.url and not found_stream:
                    found_stream = request.url

            page.on("request", handle_request)

            try:
                page.goto(url, timeout=30000)
                page.wait_for_timeout(5000)
            except Exception as e:
                print(f"Səhifə açılmadı: {url} ({e})")

            page.close()

            if found_stream:
                print(f"Tapıldı: {found_stream}")
                m3u_lines.append(f'#EXTINF:-1,{name}')
                m3u_lines.append(found_stream)
            else:
                print(f"Tapılmadı: {name}")

        browser.close()

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))
    
    print(f"Uğurla yazıldı: {output_file}")

if __name__ == "__main__":
    main()
