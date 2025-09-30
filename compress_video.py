import os
import subprocess
import pathlib
import time
import sys
import shutil

def get_file_size(file_path):
    return os.path.getsize(file_path) / (1024 * 1024)

def check_nvidia_gpu():
    try:
        result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False

def get_video_rotation(input_path):
    """Extract rotation metadata from video (returns 0/90/180/270 or None)"""
    try:
        result = subprocess.run([
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream_tags=rotate',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            input_path
        ], capture_output=True, text=True)
        rot_str = result.stdout.strip()
        if rot_str:
            return int(rot_str)
    except Exception:
        pass
    return 0  # default: no rotation

def compress_video(input_path, output_path):
    input_path = str(pathlib.Path(input_path).resolve())
    output_path = str(pathlib.Path(output_path).resolve())

    input_size = get_file_size(input_path)
    print(f"\nInput file size: {input_size:.2f} MB")
    print(f"Starting compression of: {os.path.basename(input_path)}")

    rotation = get_video_rotation(input_path)
    vf_filters = []
    if rotation == 90:
        vf_filters.append('transpose=1')
    elif rotation == -90 or rotation == 270:
        vf_filters.append('transpose=2')
    elif rotation == 180 or rotation == -180:
        vf_filters.append('transpose=1,transpose=1')
    # else: no rotation

    has_nvidia = check_nvidia_gpu()
    command = [
        'ffmpeg',
        '-y',
        '-i', input_path,
        '-map_metadata', '0',
        '-map', '0'
    ]
    if vf_filters:
        command += ['-vf', ','.join(vf_filters)]
        # ★★★ 회전메타데이터 제거 옵션 추가 ★★★
        command += ['-metadata:s:v:0', 'rotate=0']
    else:
        # 그래도 메타데이터는 0으로 맞춤
        command += ['-metadata:s:v:0', 'rotate=0']

    if has_nvidia:
        print("\nNVIDIA GPU detected, using hardware acceleration")
        command += [
            '-c:v', 'hevc_nvenc',
            '-preset', 'p7',
            '-rc:v', 'vbr',
            '-cq:v', '28',
            '-b:v', '0',
            '-spatial-aq', '1',
            '-aq-strength', '15',
            '-c:a', 'copy',
            '-c:s', 'copy',
            '-thread_queue_size', '4096',
            output_path
        ]
    else:
        print("\nNo NVIDIA GPU detected, using CPU encoding with optimized settings")
        cpu_count = os.cpu_count() or 4
        command += [
            '-c:v', 'libx265',
            '-preset', 'medium',
            '-crf', '28',
            '-x265-params', 'aq-mode=3:aq-strength=1:psy-rd=1.0:deblock=1,1:sao=1:strong-intra-smoothing=1',
            '-c:a', 'copy',
            '-c:s', 'copy',
            '-thread_queue_size', '4096',
            '-threads', str(cpu_count),
            output_path
        ]
    
    start_time = time.time()
    try:
        print("\nCompressing... (This might take a while)")
        print("Press Ctrl+C to cancel the compression\n")
        
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )
        
        while True:
            line = process.stderr.readline()
            if not line and process.poll() is not None:
                break
            if line:
                if "frame=" in line or "time=" in line or "speed=" in line:
                    print(f"\r{line.strip()}", end='')
                    sys.stdout.flush()
        
        return_code = process.wait()
            
        if return_code == 0:
            output_size = get_file_size(output_path)
            duration = time.time() - start_time
            
            print(f"\n\nCompression completed successfully!")
            print(f"Output file size: {output_size:.2f} MB")
            print(f"Compression ratio: {(1 - output_size/input_size) * 100:.1f}%")
            print(f"Time taken: {duration/60:.1f} minutes")
            print(f"Output saved to: {output_path}")
        else:
            print(f"\nError: FFmpeg process failed with return code {return_code}")
            stderr = process.stderr.read()
            if stderr:
                print(f"Error details: {stderr}")
            
    except KeyboardInterrupt:
        print("\nCompression cancelled by user")
        process.terminate()
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
                print(f"Partially compressed file removed: {output_path}")
            except:
                print(f"Warning: Could not remove partial output file: {output_path}")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()



def process_video(path):
    path = pathlib.Path(path).resolve()
    print(f"Processing path: {path}")

    SUPPORTED_EXTS = ('.mkv', '.mp4', '.mov')

    if path.is_file():
        if path.suffix.lower() not in SUPPORTED_EXTS:
            print(f"Error: {path} is not a supported video file (MKV, MP4, MOV)")
            return

        directory = path.parent
        output_dir = directory / "compressed"
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / f"compressed_{path.name}"
        compress_video(str(path), str(output_file))

    elif path.is_dir():
        output_dir = path / "compressed"
        output_dir.mkdir(exist_ok=True)
        # filter 방식
        video_files = [f for f in path.iterdir() 
                       if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS]
        if not video_files:
            print(f"No video files (MKV, MP4, MOV) found in {path}")
            return

        for i, video_file in enumerate(video_files, 1):
            print(f"\nProcessing file {i} of {len(video_files)}")
            output_file = output_dir / f"{video_file.name}"
            compress_video(str(video_file), str(output_file))
    else:
        print(f"Error: {path} is not a valid file or directory")


# /mnt/c/Users/SSAFY/Documents/강의자료/12기/03 자율 - 기업연계C/멘토링 녹화 영상/2025-04-28 14-30-00 S302_트리니들.mkv
if __name__ == "__main__":
    # Get the path (can be either a file or directory)
    path = input("Enter the path to video file (MKV or MP4) or folder containing video files: ").strip()
    process_video(path)
    