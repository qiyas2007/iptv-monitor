import json
import os

def main():
    json_path = "channels.json"
    output_dir = "output"
    output_file = os.path.join(output_dir, "channels.m3u")
    
    os.makedirs(output_dir, exist_ok=True)
    
    if not os.path.exists(json_path):
        print(f"Xəta: {json_path} tapılmadı!")
        return

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            channels = json.load(f)
    except Exception as e:
        print(f"JSON oxunmadı: {e}")
        return

    m3u_lines = ["#EXTM3U"]

    for ch in channels:
        name = ch.get("name", "Kanal")
        url = ch.get("stream_url", "") # Birbaşa m3u8 linkini oxuyur

        if not url:
            continue

        print(f"Əlavə olundu: {name}")
        m3u_lines.append(f'#EXTINF:-1,{name}')
        m3u_lines.append(url)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))
    
    print(f"Uğurla yazıldı: {output_file}")

if __name__ == "__main__":
    main()
