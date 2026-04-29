import sys
import re
import os
import glob

def process_srt(file_path):
    if file_path.endswith('_merged.srt'):
        return False

    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
    except Exception as e:
        print(f"[{os.path.basename(file_path)}] 파일을 읽는 중 오류가 발생했습니다: {e}")
        return False

    blocks = content.strip().split('\n\n')
    parsed_blocks = []

    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            time_line = lines[1]
            if ' --> ' in time_line:
                start_time, end_time = time_line.split(' --> ')
                parsed_blocks.append({
                    'index': lines[0],
                    'start': start_time.strip(),
                    'end': end_time.strip(),
                    'text': '\n'.join(lines[2:])
                })

    if not parsed_blocks:
        print(f"[{os.path.basename(file_path)}] SRT 파일 내용이 없거나 올바른 포맷이 아닙니다.")
        return False

    merged_blocks = []
    current_block = parsed_blocks[0]

    for i in range(1, len(parsed_blocks)):
        block = parsed_blocks[i]
        text = block['text']
        prev_text = current_block['text'].strip()

        # 조건 1: 현재 대사의 첫 알파벳이 소문자인가?
        starts_with_lower = bool(re.match(r'^[^a-zA-Z]*[a-z]', text))
        
        # 조건 2: 이전 대사가 쉼표(,)로 끝나는가? (공백 무시)
        ends_with_comma = prev_text.endswith(',')

        # 두 조건 중 하나라도 만족하면 병합 진행
        if starts_with_lower or ends_with_comma:
            current_block['end'] = block['end']
            current_block['text'] += ' ' + text.strip()
        else:
            merged_blocks.append(current_block)
            current_block = block.copy()

    merged_blocks.append(current_block)

    for i, block in enumerate(merged_blocks):
        block['index'] = str(i + 1)

    base, ext = os.path.splitext(file_path)
    output_path = f"{base}_merged{ext}"

    with open(output_path, 'w', encoding='utf-8') as f:
        for block in merged_blocks:
            f.write(f"{block['index']}\n")
            f.write(f"{block['start']} --> {block['end']}\n")
            f.write(f"{block['text']}\n\n")

    print(f" - 완료: {os.path.basename(output_path)}")
    return True

def process_target(target_path):
    if os.path.isfile(target_path):
        if target_path.lower().endswith('.srt'):
            print(f"단일 파일 처리를 시작합니다: {target_path}")
            process_srt(target_path)
        else:
            print("오류: SRT 파일이 아닙니다.")
            
    elif os.path.isdir(target_path):
        search_pattern = os.path.join(target_path, '*.srt')
        all_srt_files = glob.glob(search_pattern)
        
        target_files = [f for f in all_srt_files if not f.endswith('_merged.srt')]
        
        if not target_files:
            print(f"'{target_path}' 경로에 처리할 SRT 파일이 없습니다.")
            return

        print(f"총 {len(target_files)}개의 SRT 파일을 찾았습니다. 일괄 작업을 시작합니다...\n")
        
        success_count = 0
        for file in target_files:
            if process_srt(file):
                success_count += 1
                
        print(f"\n모든 작업 완료! (총 {success_count}개 파일 처리됨)")
        
    else:
        print("오류: 유효한 파일이나 디렉토리 경로가 아닙니다.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("사용법:")
        print("  단일 파일 처리: python merge_srt.py [파일명.srt]")
        print("  폴더 일괄 처리: python merge_srt.py [디렉토리_경로]")
        sys.exit(1)

    target_path = sys.argv[1]
    
    if not os.path.exists(target_path):
        print(f"경로를 찾을 수 없습니다: {target_path}")
        sys.exit(1)

    process_target(target_path)