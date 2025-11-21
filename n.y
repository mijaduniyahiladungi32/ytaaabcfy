import subprocess
import os
import json

def get_streams_info(url):
    """Get available streams using yt-dlp with JSON output"""
    try:
        result = subprocess.run([
            'yt-dlp', '-F', '--print-json', url
        ], capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        return None

def parse_streams_info(info_text):
    """Parse yt-dlp JSON output to extract stream information"""
    video_streams = []
    audio_streams = []
    
    try:
        # Try to parse as JSON first
        data = json.loads(info_text)
        formats = data.get('formats', [])
        
        for fmt in formats:
            if fmt.get('vcodec') != 'none' and fmt.get('acodec') == 'none':
                # Video only stream
                video_streams.append({
                    'id': fmt['format_id'],
                    'resolution': f"{fmt.get('width', '')}x{fmt.get('height', '')}",
                    'url': fmt.get('url', '')
                })
            elif fmt.get('acodec') != 'none' and fmt.get('vcodec') == 'none':
                # Audio only stream
                audio_streams.append({
                    'id': fmt['format_id'],
                    'url': fmt.get('url', '')
                })
                
    except json.JSONDecodeError:
        # Fallback to text parsing
        print("Falling back to text parsing...")
        for line in info_text.split('\n'):
            if 'video only' in line:
                parts = line.split()
                if len(parts) >= 3:
                    stream_id = parts[0]
                    resolution = None
                    for part in parts:
                        if 'x' in part and part.replace('x', '').replace('~', '').isdigit():
                            resolution = part
                            break
                    if resolution:
                        video_streams.append({'id': stream_id, 'resolution': resolution, 'url': None})
            
            elif 'audio only' in line:
                parts = line.split()
                if len(parts) >= 3:
                    stream_id = parts[0]
                    audio_streams.append({'id': stream_id, 'url': None})
    
    return video_streams, audio_streams

def get_all_streams_urls(base_url):
    """Get all stream URLs at once using yt-dlp --print-json"""
    try:
        result = subprocess.run([
            'yt-dlp', '--print-json', '--skip-download', base_url
        ], capture_output=True, text=True, check=True)
        
        data = json.loads(result.stdout)
        formats = data.get('formats', [])
        
        stream_urls = {}
        for fmt in formats:
            stream_urls[fmt['format_id']] = fmt.get('url', '')
        
        return stream_urls
        
    except subprocess.CalledProcessError as e:
        print(f"Error getting stream URLs: {e}")
        return {}

def get_stream_url_individual(base_url, stream_id):
    """Get URL for individual stream"""
    try:
        result = subprocess.run([
            'yt-dlp', '--get-url', '-f', stream_id, base_url
        ], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error getting URL for stream {stream_id}: {e}")
        return None

def calculate_bandwidth(resolution):
    """Calculate bandwidth based on resolution"""
    if '1080' in resolution:
        return 3500000
    elif '720' in resolution:
        return 2000000
    elif '480' in resolution:
        return 1200000
    elif '360' in resolution:
        return 800000
    else:
        return 500000

def create_audio_m3u8(audio_url):
    """Create audio.m3u8 file"""
    with open('audio.m3u8', 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        f.write("#EXT-X-VERSION:3\n")
        f.write("#EXT-X-TARGETDURATION:30\n")
        f.write("#EXT-X-MEDIA-SEQUENCE:0\n")
        f.write("#EXT-X-PLAYLIST-TYPE:VOD\n")
        f.write("#EXTINF:9999.000,\n")
        f.write(f"{audio_url}\n")
        f.write("#EXT-X-ENDLIST\n")
    print("✓ audio.m3u8 created")

def create_video_m3u8(resolution, video_url):
    """Create individual video quality M3U8 file"""
    # Clean resolution for filename
    clean_res = resolution.replace('x', 'p').replace('~', '')
    filename = f"{clean_res}.m3u8"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        f.write("#EXT-X-VERSION:3\n")
        f.write("#EXT-X-TARGETDURATION:30\n")
        f.write("#EXT-X-MEDIA-SEQUENCE:0\n")
        f.write("#EXT-X-PLAYLIST-TYPE:VOD\n")
        f.write("#EXTINF:9999.000,\n")
        f.write(f"{video_url}\n")
        f.write("#EXT-X-ENDLIST\n")
    print(f"✓ {filename} created")

def create_master_m3u8(video_streams):
    """Create master.m3u8 file"""
    with open('master.m3u8', 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        f.write("#EXT-X-VERSION:3\n")
        f.write("#EXT-X-INDEPENDENT-SEGMENTS\n\n")
        
        f.write("# Audio Track\n")
        f.write('#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",NAME="Audio",DEFAULT=YES,AUTOSELECT=YES,URI="audio.m3u8"\n\n')
        
        f.write("# Video Tracks\n")
        for stream in video_streams:
            bandwidth = calculate_bandwidth(stream['resolution'])
            clean_res = stream['resolution'].replace('x', 'p').replace('~', '')
            f.write(f'#EXT-X-STREAM-INF:BANDWIDTH={bandwidth},RESOLUTION={stream["resolution"]},AUDIO="audio"\n')
            f.write(f'{clean_res}.m3u8\n\n')
    
    print("✓ master.m3u8 created")

def main():
    base_url = "https://www.bilibili.tv/en/video/4795275155346944"
    
    print("Fetching stream information...")
    info_text = get_streams_info(base_url)
    
    if not info_text:
        print("Failed to get stream information")
        return
    
    video_streams, audio_streams = parse_streams_info(info_text)
    
    print(f"Found {len(video_streams)} video streams and {len(audio_streams)} audio streams")
    
    # Get all stream URLs at once
    print("Getting all stream URLs...")
    all_urls = get_all_streams_urls(base_url)
    
    # Process audio stream
    if audio_streams:
        audio_url = None
        # Try to get audio URL from all_urls first
        for audio_stream in audio_streams:
            if audio_stream['id'] in all_urls:
                audio_url = all_urls[audio_stream['id']]
                break
        
        # If not found, try individual request
        if not audio_url and audio_streams[0].get('url'):
            audio_url = audio_streams[0]['url']
        elif not audio_url:
            audio_url = get_stream_url_individual(base_url, audio_streams[0]['id'])
        
        if audio_url:
            create_audio_m3u8(audio_url)
        else:
            print("Failed to get audio URL")
            return
    else:
        print("No audio streams found")
        return
    
    # Process video streams
    processed_streams = []
    for stream in video_streams:
        print(f"Processing {stream['resolution']} (ID: {stream['id']})...")
        
        video_url = None
        # Try to get URL from all_urls first
        if stream['id'] in all_urls:
            video_url = all_urls[stream['id']]
        
        # If not found, try other methods
        if not video_url and stream.get('url'):
            video_url = stream['url']
        elif not video_url:
            video_url = get_stream_url_individual(base_url, stream['id'])
        
        if video_url:
            create_video_m3u8(stream['resolution'], video_url)
            processed_streams.append(stream)
            print(f"  ✓ URL obtained")
        else:
            print(f"  ✗ Failed to get URL")
    
    # Create master playlist
    if processed_streams:
        create_master_m3u8(processed_streams)
        print("\n🎉 M3U8 files created successfully!")
        print(f"Processed {len(processed_streams)} out of {len(video_streams)} video streams")
    else:
        print("No video streams processed successfully")

if __name__ == "__main__":
    main()
