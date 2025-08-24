import yt_dlp
import os

def download_youtube_video_with_ytdlp(video_urls, resolution='best', download_path='.'):
    """
    yt-dlp를 사용하여 유튜브 영상을 지정된 해상도 또는 최고 화질로 다운로드하는 함수.
    비디오 코덱을 H.264(avc1)로 제한하여 선택하고, 오디오를 MP3로 변환하여 MP4 컨테이너에 병합합니다.
    (YouTube에서 직접 MP3 오디오를 제공하지 않으므로 다운로드 후 FFmpeg로 변환 처리.
    yt-dlp가 FFmpeg를 내부적으로 사용하므로 FFmpeg가 설치되어 있어야 합니다.)

    :param video_urls: 다운로드할 유튜브 영상 URL 또는 URL 리스트 (문자열 또는 문자열 리스트)
    :param resolution: 원하는 높이(height) 값 (문자열, 예: '1080', '720'). 'best'일 경우 H.264 지원 범위 내 최고 화질 선택 (일반적으로 1080p 이하).
    :param download_path: 파일이 저장될 경로 (문자열).
    """
    try:
        # 단일 URL을 리스트로 변환하여 처리
        if isinstance(video_urls, str):
            video_urls = [video_urls]

        # 다운로드 경로가 없으면 생성
        if not os.path.exists(download_path):
            os.makedirs(download_path)

        # yt-dlp 옵션 설정
        # H.264 비디오 코덱(avc1)과 MP4 확장자 우선, 오디오 변환을 위한 postprocessor 설정
        base_format = 'bestvideo[vcodec^=avc1][ext=mp4]{height_filter}+bestaudio[ext=m4a]/best[ext=mp4]/best'
            
        if resolution == 'best':
            height_filter = ''  # 'best'일 경우 높이 제한 없이 H.264 중 최고 (YouTube 한계로 1080p 이하)
            outtmpl = os.path.join(download_path, '%(title)s.%(ext)s')
        else:
            height_filter = f'[height<={resolution}]'
            outtmpl = os.path.join(download_path, '%(title)s - ' + resolution + 'p.%(ext)s')
        
        ydl_opts = {
            'format': base_format.format(height_filter=height_filter),
            'outtmpl': outtmpl,
            'merge_output_format': 'mp4',
            'postprocessor_args': [
                '-c:v', 'copy',  # 비디오 코덱(H.264)은 복사 (이미 선택된 상태)
                '-c:a', 'libmp3lame'  # 오디오를 MP3로 변환
            ],
        }
        
        print(f"'{', '.join(video_urls)}' 영상 다운로드를 시작합니다...")
        
        # yt-dlp 객체로 다운로드 실행 (리스트를 직접 전달하여 순서대로 처리)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download(video_urls)
            
        print("\n다운로드 완료! 🎉")
        print(f"저장 경로: {os.path.abspath(download_path)}")
        print("출력 파일: MP4 컨테이너 (비디오 코덱: H.264, 오디오 코덱: MP3)")

    except Exception as e:
        print(f"오류가 발생했습니다: {e}")

# --- 실행 부분 ---
if __name__ == "__main__":
    # 다운로드할 유튜브 영상 주소
    video_urls = [
        "https://youtu.be/L8-5ezsoI5A?si=hITIDkyhJzHGJVTA",
        "https://youtu.be/CiMVKnX-CNI?si=gxKsDpmEYkgO6J36"
        # 추가 URL 예시: "https://youtu.be/another_video_id",
        # "https://youtu.be/yet_another_video_id"
    ]

    # --- 사용 예시 ---

    # 1. 최고 화질(Best)로 다운로드 (기본값)
    download_youtube_video_with_ytdlp(video_urls)

    # 2. 특정 해상도(예: 1080p) 이하 중 가장 좋은 화질로 다운로드
    # download_youtube_video_with_ytdlp(video_url, resolution='1080')
    
    # 3. 특정 해상도(예: 720p) 이하 중 가장 좋은 화질로 다운로드
    # download_youtube_video_with_ytdlp(video_url, resolution='720')