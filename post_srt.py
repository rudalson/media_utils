import os
import re
import argparse
from pathlib import Path

def process_srt(target="."):
    # 패턴 1: 문장 부호 뒤의 확인성 어미 정리
    # 마지막에 '?'를 제거하여 [.\?] 즉, 마침표나 물음표가 반드시 뒤따를 때만 매칭되도록 수정했습니다.
    # 이렇게 하면 ', 여러분도'나 ', 아시겠죠라고' 처럼 뒤에 조사가 붙는 경우는 건너뜁니다.
    p1 = re.compile(r'[\.,]\s*(괜찮죠|맞죠|알겠죠|그렇죠|맞나요|아시겠죠|여러분)[\.\?]')
    
    # 패턴 2: 문장 시작점의 추임새 삭제
    # (?<!\S)는 줄의 시작이나 공백 뒤에서만 작동합니다.
    p2 = re.compile(r'(?<!\S)(어|음|네),\s*')

    path = Path(target).resolve()
    if not path.exists():
        print(f"Error: '{target}'는 유효한 디렉토리 또는 파일이 아닙니다.")
        return

    if path.is_file():
        if path.suffix.lower() != '.srt':
            print(f"Error: '{target}'는 .srt 파일이 아닙니다.")
            return
        srt_files = [path]
        print(f"작업 파일: {path}")
    elif path.is_dir():
        print(f"작업 디렉토리: {path}")
        srt_files = [f for f in path.iterdir() if f.is_file() and f.suffix.lower() == '.srt']
        if not srt_files:
            print("처리할 .srt 파일이 없습니다.")
            return
    else:
        print(f"Error: '{target}'는 유효한 디렉토리 또는 파일이 아닙니다.")
        return

    print(f"총 {len(srt_files)}개의 파일을 찾았습니다. 정제 작업을 시작합니다...")

    for srt_path in srt_files:
        try:
            with open(srt_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()

            # 1. ', 여러분.' -> '.' 형태로 변환 (요청하신 대로 뒤에 문장 부호가 있을 때만 작동)
            content = p1.sub('.', content)

            # 2. 문장 시작 추임새 삭제
            content = p2.sub('', content)

            # 파일명을 변경하지 않고 input 파일명 그대로 덮어쓰기 저장
            with open(srt_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"[OK] 완료: {srt_path.name}")

        except Exception as e:
            print(f"[FAIL] 실패: {srt_path.name} (사유: {e})")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="자막 파일 추임새 정리 스크립트")
    parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="srt 파일 또는 srt 파일들이 들어있는 디렉토리 경로 (지정하지 않을 경우 현재 디렉토리)"
    )
    
    args = parser.parse_args()
    process_srt(args.target)