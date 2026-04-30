import os
import re
import json

def remove_multiple_texts_in_files(directory, remove_list):
    """
    지정된 디렉토리의 모든 .txt 파일에서 remove_list에 있는 문자열들을 찾아 제거합니다.

    :param directory: 검색할 디렉토리 경로
    :param remove_list: 삭제할 문자열들의 리스트
    """
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(".srt"):
                file_path = os.path.join(root, file)

                # 파일 읽기
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                original_content = content

                # 리스트에 있는 문자열 모두 제거
                for target_text in remove_list:
                    # content = content.replace(target_text, "")
                    content = re.sub(re.escape(target_text), "", content, flags=re.IGNORECASE)

                # 변경된 경우 저장
                if content != original_content:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    print(f"[수정됨] {file_path}")
                else:
                    print(f"[변경 없음] {file_path}")

if __name__ == "__main__":
    directory_path = r"./"  # 디렉토리 경로 지정
    
    # filters.json 파일에서 제거할 문자열들 읽기
    base_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base_dir, 'filters.json')
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            remove_targets = data.get('remove_targets', [])
    except Exception as e:
        print(f"filters.json 파일을 읽는 중 오류 발생: {e}")
        remove_targets = []

    if remove_targets:
        remove_multiple_texts_in_files(directory_path, remove_targets)
    else:
        print("제거할 문자열 목록이 없습니다.")
