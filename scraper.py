import json
import os

def main():
    if not os.path.exists("channels.json"):
        print("channels.json tapılmadı!")
        return

    with open("channels.json", "r", encoding="utf-8") as f:
        channels = json.load(f)

    m3u_lines = ["#EXTM3U"]

    for ch in channels:
        name = ch.get("name", "Kanal")
        url = ch.get("url", "")

        if not url:
            continue

        print(f"Əlavə olundu: {name}")
        m3u_lines.append(f'#EXTINF:-1 tvg-name="{name}", {name}')
        m3u_lines.append(url)

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print("\nplaylist.m3u uğurla yaradıldı!")

if __name__ == "__main__":
    main()
