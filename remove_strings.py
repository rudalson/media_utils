import os
import re

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
    directory_path = r"d:\\_Archives\\vrew영상들\\test\\"  # 디렉토리 경로 지정
     # 제거할 문자열들
    remove_targets = [
        " (mouse clicking)", " (drum roll)", " (clicking sound)", " (whoosh sound effect)", " (whooshing sound)", " (chiming)",
        " (snaps fingers)", " (crowd clapping)", " (gasps)", " (swoosh sound)", " (screen swooshes)", " (screen whooshes)", " (applause)", " (swooshing sound)", " (harp sound)",
        " (keys clacking)", " (laughing)"," (inaudible)", " (clears throat)", " (sniffs)", " (dramatic music)", " (coins clinking)", " (chimes twinkling)", " (bell dinging)",
        " (chiming sound)", " (keyboard clacking)", " (instrumental music plays)", " (bell chiming)", " (keyboard clacks)", " (clicks tongue)"," (audience cheering and clapping)",
        " (keyboard keys clacking)", " (beep)", " (electronic sound effect)",  " (keyboard click)", " (chime)", " (electronic chime)", " (chime sounds)", " (keyboard clicks)",
        " (bell dings)", " (ding)", " (ball bounces)", " (chimes)", " (laugh)", " (typing)", " (upbeat music)", " (keyboard clicking)", " (soft instrumental music)", " (laughs)",
        " (smacks lips)"," (inhales)", " (laughter)", " (whoosh)"," (sighs)", " (applauding)", " (outro music)", " (clapping)", " (breaths in)", " (applause)"
        " (claps)", " (mouse click)", " (bell chimes)", " (Upbeat music playing)"
    ]

    remove_multiple_texts_in_files(directory_path, remove_targets)
