import sys
import re
import os

def process_srt(file_path):
    # utf-8-sig로 읽어 BOM(Byte Order Mark) 문제를 방지합니다.
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
    except Exception as e:
        print(f"파일을 읽는 중 오류가 발생했습니다: {e}")
        return

    # 빈 줄을 기준으로 SRT 블록을 분리합니다.
    blocks = content.strip().split('\n\n')
    parsed_blocks = []

    for block in blocks:
        lines = block.strip().split('\n')
        # 인덱스, 시간, 대사가 모두 있는지 확인
        if len(lines) >= 3:
            time_line = lines[1]
            if ' --> ' in time_line:
                start_time, end_time = time_line.split(' --> ')
                parsed_blocks.append({
                    'index': lines[0],
                    'start': start_time.strip(),
                    'end': end_time.strip(),
                    'text': '\n'.join(lines[2:]) # 2줄 이상의 대사도 그대로 보존
                })

    if not parsed_blocks:
        print("SRT 파일 내용이 없거나 올바른 포맷이 아닙니다.")
        return

    merged_blocks = []
    current_block = parsed_blocks[0]

    for i in range(1, len(parsed_blocks)):
        block = parsed_blocks[i]
        text = block['text']

        # 대사의 가장 첫 번째 영문 알파벳이 소문자인지 검사 (특수문자나 공백 무시)
        if re.match(r'^[^a-zA-Z]*[a-z]', text):
            # 1. 종료 시간을 현재 블록의 종료 시간으로 연장
            current_block['end'] = block['end']
            # 2. 앞 대사와 스페이스 문자를 사이에 두고 합치기
            # (만약 병합 시 기존 대사의 줄바꿈을 없애고 싶다면 replace('\n', ' ')를 추가 응용할 수 있습니다)
            current_block['text'] += ' ' + text.strip()
        else:
            # 대문자로 시작하면 병합하지 않고 목록에 추가 후, 현재 블록을 교체
            merged_blocks.append(current_block)
            current_block = block.copy()

    # 마지막 블록 추가
    merged_blocks.append(current_block)

    # 병합이 끝난 후 인덱스(순번)를 1번부터 다시 순차적으로 재정렬합니다.
    for i, block in enumerate(merged_blocks):
        block['index'] = str(i + 1)

    # 원본 파일명 뒤에 _merged를 붙여 새로운 파일로 저장합니다.
    base, ext = os.path.splitext(file_path)
    output_path = f"{base}_merged{ext}"

    with open(output_path, 'w', encoding='utf-8') as f:
        for block in merged_blocks:
            f.write(f"{block['index']}\n")
            f.write(f"{block['start']} --> {block['end']}\n")
            f.write(f"{block['text']}\n\n")

    print(f"작업 완료! 저장된 파일: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("사용법: python [py파일명] [srt파일경로]")
        print("예시: python merge_srt.py subtitle.srt")
        sys.exit(1)

    srt_path = sys.argv[1]
    
    if not os.path.exists(srt_path):
        print(f"파일을 찾을 수 없습니다: {srt_path}")
        sys.exit(1)

    process_srt(srt_path)
    