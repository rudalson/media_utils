import os
import re
import argparse
from pathlib import Path

def process_srt(directory):
    # 패턴 1: 문장 부호 뒤의 확인성 어미 정리
    # 마지막에 '?'를 제거하여 [.\?] 즉, 마침표나 물음표가 반드시 뒤따를 때만 매칭되도록 수정했습니다.
    # 이렇게 하면 ', 여러분도'나 ', 아시겠죠라고' 처럼 뒤에 조사가 붙는 경우는 건너뜁니다.
    p1 = re.compile(r'[\.,]\s*(괜찮죠|맞죠|그렇죠|맞나요|아시겠죠|여러분)[\.\?]')
    
    # 패턴 2: 문장 시작점의 추임새 삭제
    # (?<!\S)는 줄의 시작이나 공백 뒤에서만 작동합니다.
    p2 = re.compile(r'(?<!\S)(어|음|네),\s*')

    path = Path(directory)
    if not path.exists() or not path.is_dir():
        print(f"Error: '{directory}'는 유효한 디렉토리가 아닙니다.")
        return

    srt_files = list(path.glob('*.srt'))
    if not srt_files:
        print("처리할 .srt 파일이 없습니다.")
        return

    print(f"총 {len(srt_files)}개의 파일을 찾았습니다. 정제 작업을 시작합니다...")

    for srt_path in srt_files:
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 1. ', 여러분.' -> '.' 형태로 변환 (요청하신 대로 뒤에 문장 부호가 있을 때만 작동)
            content = p1.sub('.', content)

            # 2. 문장 시작 추임새 삭제
            content = p2.sub('', content)
            
            new_filename = f"fixed_{srt_path.name}"
            new_path = srt_path.parent / new_filename

            with open(new_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"✅ 완료: {srt_path.name}")

        except Exception as e:
            print(f"❌ 실패: {srt_path.name} (사유: {e})")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="자막 파일 추임새 정리 스크립트")
    parser.add_argument("directory", help="srt 파일들이 들어있는 디렉토리 경로")
    
    args = parser.parse_args()
    process_srt(args.directory)