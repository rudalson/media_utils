import argparse
import subprocess
import pathlib
import sys

def crop_video(input_path, output_path, width, height, x, y):
    """Crop a region from the input video and save to output."""
    input_path = str(pathlib.Path(input_path).resolve())
    output_path = str(pathlib.Path(output_path).resolve())
    crop_filter = f"crop={width}:{height}:{x}:{y}"
    
    command = [
        'ffmpeg',
        '-i', input_path,
        '-vf', crop_filter,
        '-c:a', 'copy',  # Copy audio without re-encoding
        output_path
    ]
    print(f"Running: {' '.join(command)}")
    try:
        subprocess.run(command, check=True)
        print(f"Cropped video saved to: {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error during cropping: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Crop a region from a video file or all videos in a directory.")
    parser.add_argument('input', help='Input video file or directory path')
    parser.add_argument('--width', type=int, required=True, help='Crop width (pixels)')
    parser.add_argument('--height', type=int, required=True, help='Crop height (pixels)')
    parser.add_argument('--x', type=int, help='Crop start x (pixels, default: center)')
    parser.add_argument('--y', type=int, help='Crop start y (pixels, default: center)')
    args = parser.parse_args()

    input_path = pathlib.Path(args.input).resolve()

    def process_one_file(file_path):
        output_dir = file_path.parent / 'trimmed'
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / f"trimmed_{file_path.name}"

        # If x or y are not provided, center the crop
        if args.x is None or args.y is None:
            probe_cmd = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height',
                '-of', 'csv=s=x:p=0',
                str(file_path)
            ]
            try:
                output = subprocess.check_output(probe_cmd, text=True).strip()
                video_w, video_h = map(int, output.split('x'))
            except Exception as e:
                print(f"Failed to get video resolution for {file_path}: {e}")
                return
            x = args.x if args.x is not None else max((video_w - args.width) // 2, 0)
            y = args.y if args.y is not None else max((video_h - args.height) // 2, 0)
        else:
            x = args.x
            y = args.y
        crop_video(str(file_path), str(output_path), args.width, args.height, x, y)

    if input_path.is_file():
        process_one_file(input_path)
    elif input_path.is_dir():
        video_files = list(input_path.glob('*.mp4')) + list(input_path.glob('*.mkv'))
        if not video_files:
            print(f"No .mp4 or .mkv files found in {input_path}")
            return
        for i, file_path in enumerate(video_files, 1):
            print(f"\nProcessing file {i} of {len(video_files)}: {file_path.name}")
            process_one_file(file_path)
    else:
        print(f"Error: {input_path} is not a valid file or directory")

if __name__ == "__main__":
    main() 