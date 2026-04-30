import os
import re
import sys
import json

def load_remove_targets(json_path='filters.json'):
    """JSON 파일에서 제거 대상 리스트를 불러옵니다."""
    try:
        # 스크립트 파일과 같은 위치에서 json 찾기
        script_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(script_dir, json_path)
        
        with open(full_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('remove_targets', [])
    except Exception as e:
        print(f"경고: {json_path} 파일을 불러올 수 없습니다. 정제 기능을 건너뜁니다. ({e})")
        return []

def clean_noise(text, remove_targets):
    """텍스트에서 노이즈를 제거합니다."""
    for target in remove_targets:
        text = re.sub(re.escape(target), "", text, flags=re.IGNORECASE)
    return text

def merge_logic(blocks):
    """SRT 블록 리스트 병합 로직"""
    if not blocks: return []
    merged_blocks = []
    current_block = blocks[0]

    for i in range(1, len(blocks)):
        block = blocks[i]
        text = block['text'].strip()
        prev_text = current_block['text'].strip()

        starts_with_lower = bool(re.match(r'^[^a-zA-Z]*[a-z]', text))
        ends_with_comma = prev_text.endswith(',')

        if starts_with_lower or ends_with_comma:
            current_block['end'] = block['end']
            combined_text = prev_text + " " + text
            current_block['text'] = combined_text.replace("  ", " ").strip()
        else:
            merged_blocks.append(current_block)
            current_block = block.copy()

    merged_blocks.append(current_block)
    for i, block in enumerate(merged_blocks):
        block['index'] = str(i + 1)
    return merged_blocks

def process_file(file_path, remove_targets):
    """개별 파일 처리"""
    if file_path.endswith('_pre.srt'): return False
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()

        content = clean_noise(content, remove_targets)
        raw_blocks = content.strip().split('\n\n')
        parsed_blocks = []
        for b in raw_blocks:
            lines = b.strip().split('\n')
            if len(lines) >= 3 and ' --> ' in lines[1]:
                start_t, end_t = lines[1].split(' --> ')
                parsed_blocks.append({
                    'index': lines[0], 'start': start_t.strip(), 'end': end_t.strip(),
                    'text': ' '.join(lines[2:])
                })

        if not parsed_blocks: return False
        final_blocks = merge_logic(parsed_blocks)

        base, ext = os.path.splitext(file_path)
        output_path = f"{base}_merged{ext}"
        with open(output_path, 'w', encoding='utf-8') as f:
            for block in final_blocks:
                f.write(f"{block['index']}\n{block['start']} --> {block['end']}\n{block['text']}\n\n")
        print(f" - [성공] {os.path.basename(output_path)}")
        return True
    except Exception as e:
        print(f" - [오류] {os.path.basename(file_path)}: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("사용법: python pre_srt.py [디렉토리_경로]")
        return

    raw_path = " ".join(sys.argv[1:])
    target_dir = raw_path.strip().strip('"').strip("'")
    if target_dir.endswith('\\'): target_dir = target_dir[:-1]

    if not os.path.isdir(target_dir):
        print(f"오류: '{target_dir}'은(는) 유효한 디렉토리가 아닙니다.")
        return

    # 설정 로드 및 작업 시작
    remove_targets = load_remove_targets()
    print(f"작업 디렉토리: {target_dir} (하위 폴더 제외)")
    print("-" * 50)

    success_count = 0
    # os.walk 대신 os.listdir을 사용하여 지정된 폴더 내부만 확인
    for item in os.listdir(target_dir):
        file_path = os.path.join(target_dir, item)
        # 폴더가 아닌 파일이면서 .srt인 경우만 처리
        if os.path.isfile(file_path) and item.lower().endswith(".srt") and not item.endswith("_merged.srt"):
            if process_file(file_path, remove_targets):
                success_count += 1

    print("-" * 50)
    print(f"작업 완료! 총 {success_count}개의 파일이 생성되었습니다.")

if __name__ == "__main__":
    main()