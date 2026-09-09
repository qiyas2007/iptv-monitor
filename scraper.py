import json
import os
import sys

def main():
    file_path = "channels.json"

    if not os.path.exists(file_path):
        print(f"XƏTA: {file_path} tapılmadı!", flush=True)
        sys.exit(1)

    if os.path.getsize(file_path) == 0:
        print(f"XƏTA: {file_path} faylının içi tamamilə boşdur!", flush=True)
        sys.exit(1)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            channels = json.load(f)
    except json.JSONDecodeError as e:
        print(f"XƏTA: JSON sintaksisi səhvdir: {e}", flush=True)
        sys.exit(1)

    m3u_lines = ["#EXTM3U"]

    for ch in channels:
        name = ch.get("name", "Kanal")
        url = ch.get("url", "")

        if not url:
            continue

        print(f"Əlavə edildi: {name}", flush=True)
        m3u_lines.append(f'#EXTINF:-1 tvg-name="{name}", {name}')
        m3u_lines.append(url)

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print(f"\nUğurlu! playlist.m3u daxilinə {len(m3u_lines) // 2} kanal yazıldı.", flush=True)

if __name__ == "__main__":
    main()
