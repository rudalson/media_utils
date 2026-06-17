import sys
import re
import os

def parse_srt_content(content):
    """
    SRT 파일 내용을 파싱하여 개별 자막 블록 리스트를 반환합니다.
    """
    # 줄바꿈 통일 및 양 끝 공백 제거
    normalized = content.replace('\r\n', '\n').strip()
    # 블록 간 빈 줄 분할 (여러 빈 줄 대응)
    raw_blocks = re.split(r'\n\s*\n', normalized)
    
    parsed_blocks = []
    for raw in raw_blocks:
        raw = raw.strip()
        if not raw:
            continue
        lines = raw.split('\n')
        if len(lines) >= 2:
            idx = lines[0].strip()
            time_line = lines[1].strip()
            if ' --> ' in time_line:
                start_t, end_t = time_line.split(' --> ')
                text = '\n'.join(lines[2:])
                parsed_blocks.append({
                    'index': idx,
                    'start': start_t.strip(),
                    'end': end_t.strip(),
                    'text': text.strip()
                })
    return parsed_blocks

def verify_srt_files(pre_file_path, kr_file_path):
    """
    두 SRT 파일의 개수, 인덱스, 타임스탬프를 1:1 비교 검증합니다.
    (is_valid, message) 튜플을 반환합니다.
    """
    if not os.path.exists(pre_file_path):
        return False, f"오류: 원본 전처리 파일 '{pre_file_path}'이(가) 존재하지 않습니다."
    if not os.path.exists(kr_file_path):
        return False, f"오류: 번역 파일 '{kr_file_path}'이(가) 존재하지 않습니다."

    try:
        with open(pre_file_path, 'r', encoding='utf-8-sig') as f:
            pre_content = f.read()
        with open(kr_file_path, 'r', encoding='utf-8-sig') as f:
            kr_content = f.read()
    except Exception as e:
        return False, f"파일을 읽는 도중 오류 발생: {e}"

    pre_blocks = parse_srt_content(pre_content)
    kr_blocks = parse_srt_content(kr_content)

    pre_len = len(pre_blocks)
    kr_len = len(kr_blocks)

    if pre_len != kr_len:
        return False, f"자막 개수가 일치하지 않습니다. (원본: {pre_len}개, 번역본: {kr_len}개)"

    for i in range(pre_len):
        pre_b = pre_blocks[i]
        kr_b = kr_blocks[i]

        # 1. 인덱스 검증
        if pre_b['index'] != kr_b['index']:
            return False, f"인덱스 불일치 (순서 {i+1}번째) - 원본: '{pre_b['index']}', 번역본: '{kr_b['index']}'"

        # 2. 시작 시간 검증
        if pre_b['start'] != kr_b['start']:
            return False, f"시작 시간 불일치 (인덱스 {pre_b['index']}번) - 원본: '{pre_b['start']}', 번역본: '{kr_b['start']}'"

        # 3. 종료 시간 검증
        if pre_b['end'] != kr_b['end']:
            return False, f"종료 시간 불일치 (인덱스 {pre_b['index']}번) - 원본: '{pre_b['end']}', 번역본: '{kr_b['end']}'"

        # 4. 번역 내용 비어있는지 확인
        if not kr_b['text']:
            return False, f"번역 내용이 비어있습니다. (인덱스 {pre_b['index']}번)"

    return True, f"성공: 모든 자막 개수 및 타임스탬프가 1:1로 일치합니다. (총 {pre_len}개)"

def main():
    if len(sys.argv) < 3:
        print("사용법: python verify_srt.py [원본_pre.srt 경로] [번역_kr.srt 경로]")
        sys.exit(1)

    pre_file = sys.argv[1]
    kr_file = sys.argv[2]

    is_valid, msg = verify_srt_files(pre_file, kr_file)
    print(msg)
    
    if is_valid:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
