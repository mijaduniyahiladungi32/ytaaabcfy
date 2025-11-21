import subprocess
import json

def yt_cmd(args, base_url):
    """Unified yt-dlp command with geo-bypass & headers"""
    cmd = [
        "yt-dlp",
        "--geo-bypass",
        "--add-header", "User-Agent:Mozilla/5.0",
        "--add-header", "Referer:https://www.bilibili.tv/",
    ] + args + [base_url]

    return subprocess.run(cmd, capture_output=True, text=True)

def get_streams_info(url):
    try:
        result = yt_cmd(["-F", "--print-json"], url)
        if result.returncode != 0:
            print("Error:", result.stderr)
            return None
        return result.stdout
    except Exception as e:
        print(f"Error: {e}")
        return None

def parse_streams_info(info_text):
    video_streams = []
    audio_streams = []

    try:
        data = json.loads(info_text)
        formats = data.get('formats', [])

        for fmt in formats:
            if fmt.get('vcodec') != "none" and fmt.get('acodec') == "none":
                video_streams.append({
                    "id": fmt["format_id"],
                    "resolution": f"{fmt.get('width','')}x{fmt.get('height','')}",
                })
            if fmt.get('acodec') != "none" and fmt.get('vcodec') == "none":
                audio_streams.append({
                    "id": fmt["format_id"],
                })

    except json.JSONDecodeError:
        print("JSON parse failed")
    
    return video_streams, audio_streams

def get_all_streams_urls(base_url):
    try:
        result = yt_cmd(["--print-json", "--skip-download"], base_url)
        if result.returncode != 0:
            print("Error:", result.stderr)
            return {}
        data = json.loads(result.stdout)
        return {fmt["format_id"]: fmt.get("url","") for fmt in data.get("formats", [])}
    except:
        return {}

def get_stream_url_individual(base_url, stream_id):
    result = yt_cmd(["--get-url", "-f", stream_id], base_url)
    if result.returncode == 0:
        return result.stdout.strip()
    return None

def calculate_bandwidth(resolution):
    res_map = {"1080":3500000,"720":2000000,"480":1200000,"360":800000}
    for k,v in res_map.items():
        if k in resolution: return v
    return 500000

def create_audio_m3u8(audio_url):
    with open("audio.m3u8", "w") as f:
        f.write("#EXTM3U\n#EXT-X-VERSION:3\n#EXTINF:9999.0,\n")
        f.write(audio_url + "\n#EXT-X-ENDLIST\n")
    print("✓ audio.m3u8 created")

def create_video_m3u8(resolution, video_url):
    filename = resolution.replace("x", "p") + ".m3u8"
    with open(filename, "w") as f:
        f.write("#EXTM3U\n#EXT-X-VERSION:3\n#EXTINF:9999.0,\n")
        f.write(video_url + "\n#EXT-X-ENDLIST\n")
    print(f"✓ {filename} created")

def create_master_m3u8(video_streams):
    with open("master.m3u8", "w") as f:
        f.write("#EXTM3U\n\n")
        f.write('#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",NAME="Audio",DEFAULT=YES,URI="audio.m3u8"\n')
        for s in video_streams:
            bw = calculate_bandwidth(s["resolution"])
            fname = s["resolution"].replace("x","p") + ".m3u8"
            f.write(f'#EXT-X-STREAM-INF:BANDWIDTH={bw},RESOLUTION={s["resolution"]},AUDIO="audio"\n')
            f.write(fname + "\n")
    print("✓ master.m3u8 created")

def main():
    base_url = "https://www.bilibili.tv/en/video/4795275155346944"

    print("Fetching stream information...")
    info_text = get_streams_info(base_url)
    if not info_text:
        print("Failed to get stream information")
        return

    video_streams, audio_streams = parse_streams_info(info_text)
    print(f"Found {len(video_streams)} video & {len(audio_streams)} audio streams")

    # all urls
    print("Fetching URLs...")
    all_urls = get_all_streams_urls(base_url)

    # audio
    if not audio_streams:
        print("No audio stream")
        return

    audio_id = audio_streams[0]["id"]
    audio_url = all_urls.get(audio_id) or get_stream_url_individual(base_url, audio_id)

    if not audio_url:
        print("Audio URL error")
        return

    create_audio_m3u8(audio_url)

    success_streams = []
    for s in video_streams:
        print("Processing:", s["resolution"])
        vid_url = all_urls.get(s["id"]) or get_stream_url_individual(base_url, s["id"])
        if not vid_url:
            print("✗ Failed")
            continue
        create_video_m3u8(s["resolution"], vid_url)
        success_streams.append(s)

    if success_streams:
        create_master_m3u8(success_streams)
        print("🎉 Done!")
    else:
        print("No video streams done")

if __name__ == "__main__":
    main()
