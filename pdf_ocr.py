"""
PDF OCR & Searchable PDF Generator (Korean-optimized)
=====================================================
PDF 파일에 한글 인식률이 뛰어난 딥러닝 기반 OCR(EasyOCR)을 적용하고,
원본 레이아웃과 일치하는 위치에 투명 텍스트 레이어(Searchable Text Layer)를 주입하여
검색 및 텍스트 복사가 가능한 PDF(Searchable PDF)로 변환하는 고성능 스크립트입니다.

주요 특징:
- 와일드카드 패턴(*.pdf, docs/*.pdf 등) 및 대량 일괄 처리
- 이미 텍스트가 존재하는 디지털 PDF 자동 스킵 (속도 극대화)
- 이미 변환 완료된 파일 자동 건너뛰기 (--resume)
- GPU(CUDA) 배치 가속 및 메모리 누수 방지
- 깔끔한 진행률 표시 (tqdm 지원) 및 불필요한 시스템 경고 차단
"""

import os
import sys
import glob
import argparse
import io
import math
import gc
import warnings
from typing import List, Optional, Tuple

# 불필요한 PyTorch / 라이브러리 경고 메시지 억제
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# Windows 콘솔 인코딩 호환성 보장
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# PyMuPDF FutureWarning 방지 및 호환 import
try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

try:
    import easyocr
except ImportError:
    easyocr = None

try:
    import numpy as np
    from PIL import Image
except ImportError:
    np = None
    Image = None

try:
    import torch
except ImportError:
    torch = None

# 진행률 표시줄 라이브러리 (선택적)
try:
    from tqdm import tqdm
except ImportError:
    tqdm = None


def find_korean_font() -> Optional[str]:
    """
    운영체제별 시스템 한글 폰트 경로를 자동으로 탐색합니다.
    PyMuPDF에서 투명 텍스트 레이어를 삽입할 때 정확한 한글 너비/글리프 계산에 필요합니다.
    """
    font_candidates = [
        # Windows
        r"C:\Windows\Fonts\malgun.ttf",       # 맑은 고딕
        r"C:\Windows\Fonts\gulim.ttc",        # 굴림
        r"C:\Windows\Fonts\batang.ttc",       # 바탕
        # Linux
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        # macOS
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    ]
    for path in font_candidates:
        if os.path.exists(path):
            return path
    return None


def get_default_output_path(input_path: str, output_dir: Optional[str] = None) -> str:
    """
    출력 파일 경로를 생성합니다.
    기본 동작: 원본 디렉토리 하위의 'ocr' 서브 디렉토리에 원본 파일명 그대로 저장합니다.
    (예: C:/path/document.pdf -> C:/path/ocr/document.pdf)
    """
    dir_name, base_name = os.path.split(input_path)
    target_dir = output_dir if output_dir else os.path.join(dir_name, "ocr")
    os.makedirs(target_dir, exist_ok=True)
    return os.path.join(target_dir, base_name)


def check_dependencies():
    """필수 라이브러리 설치 여부를 점검합니다."""
    missing = []
    if fitz is None:
        missing.append("pymupdf")
    if easyocr is None:
        missing.append("easyocr")
    if np is None or Image is None:
        missing.append("Pillow numpy")

    if missing:
        print("[오류] OCR 변환에 필요한 파이썬 패키지가 설치되지 않았습니다.")
        print("다음 명령어를 실행하여 설치해 주세요:\n")
        print(f"  pip install {' '.join(missing)}")
        print("\n* GPU 가속(CUDA)을 사용하려면 PyTorch 공식 사이트에서 CUDA 버전에 맞는 torch를 설치하세요.")
        sys.exit(1)


def expand_input_files(patterns: List[str], exclude_ocr_outputs: bool = True) -> List[str]:
    """
    입력된 경로 및 와일드카드 패턴(*.pdf 등)을 확장하여 대상 파일 목록을 반환합니다.
    'ocr' 서브 디렉토리 내의 파일이나 이전 '_ocr.pdf' 파일은 기본적으로 대상에서 제외합니다.
    """
    matched_files = []
    for pattern in patterns:
        has_wildcard = any(ch in pattern for ch in ["*", "?", "[", "]"])
        found = glob.glob(pattern, recursive=True)
        if found:
            for f in found:
                if os.path.isfile(f):
                    if has_wildcard and exclude_ocr_outputs:
                        norm_parts = [p.lower() for p in os.path.normpath(f).split(os.sep)]
                        if "ocr" in norm_parts or f.lower().endswith("_ocr.pdf"):
                            continue
                    matched_files.append(os.path.abspath(f))
        elif os.path.isfile(pattern):
            matched_files.append(os.path.abspath(pattern))

    return list(dict.fromkeys(matched_files))


def process_pdf_ocr(
    input_path: str,
    output_path: Optional[str] = None,
    reader: Optional["easyocr.Reader"] = None,
    languages: Optional[List[str]] = None,
    dpi: int = 300,
    use_gpu: Optional[bool] = None,
    min_confidence: float = 0.25,
    skip_text_pages: bool = True,
    text_threshold: int = 40,
    paragraph: bool = False,
    batch_size: int = 4,
    font_path: Optional[str] = None,
    verbose: bool = True,
) -> Tuple[str, dict]:
    """
    단일 PDF 파일에 한글 OCR을 수행하고 텍스트 레이어를 추가합니다.

    Returns:
        (output_path, stats_dict)
    """
    check_dependencies()

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {input_path}")

    if output_path is None:
        output_path = get_default_output_path(input_path)
    else:
        if os.path.isdir(output_path):
            output_path = get_default_output_path(input_path, output_dir=output_path)
        else:
            out_dir = os.path.dirname(output_path)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)

    if languages is None:
        languages = ["ko", "en"]

    if use_gpu is None:
        use_gpu = torch is not None and torch.cuda.is_available()

    if font_path is None or not os.path.exists(font_path):
        font_path = find_korean_font()

    if reader is None:
        if verbose:
            print("[*] EasyOCR 모델을 로딩 중입니다...")
        reader = easyocr.Reader(languages, gpu=use_gpu)

    doc = fitz.open(input_path)
    total_pages = len(doc)

    stats = {
        "total_pages": total_pages,
        "ocr_pages": 0,
        "skipped_pages": 0,
        "total_inserted": 0,
    }

    # 페이지 반복 처리 (tqdm 지원 시 프로그레스 바 사용)
    page_iter = range(total_pages)
    pbar = None
    if verbose and tqdm is not None and total_pages > 1:
        pbar = tqdm(page_iter, desc=f"  진행", unit="p", leave=False)
        iterator = pbar
    else:
        iterator = page_iter

    for page_idx in iterator:
        page = doc[page_idx]
        page_num = page_idx + 1

        # 1. 스마트 스킵: 이미 텍스트 레이어가 풍부하게 존재하는 페이지 건너뛰기
        existing_text = page.get_text().strip()
        if skip_text_pages and len(existing_text) >= text_threshold:
            stats["skipped_pages"] += 1
            if pbar:
                pbar.set_postfix({"상태": f"{page_num}p 기존텍스트 스킵"})
            elif verbose:
                print(f"  [{page_num}/{total_pages}p] 기존 텍스트 레이어 유지 (OCR 건너뜀)")
            continue

        stats["ocr_pages"] += 1

        # 2. 고해상도 렌더링
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix, alpha=False)

        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        np_img = np.array(img)

        # 3. EasyOCR 실행
        results = reader.readtext(
            np_img,
            paragraph=paragraph,
            batch_size=batch_size if use_gpu else 1,
        )

        scale_x = page.rect.width / pix.width
        scale_y = page.rect.height / pix.height

        inserted_count = 0
        filtered_count = 0

        # 4. 투명 텍스트 레이어 주입
        for item in results:
            if len(item) == 2:
                bbox, text = item[0], item[1]
                conf = 1.0
            elif len(item) >= 3:
                bbox, text, conf = item[0], item[1], item[2]
            else:
                continue

            if conf < min_confidence or not text.strip():
                filtered_count += 1
                continue

            xs = [pt[0] for pt in bbox]
            ys = [pt[1] for pt in bbox]
            x_min, x_max = min(xs), max(xs)
            y_min, y_max = min(ys), max(ys)

            pdf_x0 = x_min * scale_x
            pdf_y0 = y_min * scale_y
            pdf_x1 = x_max * scale_x
            pdf_y1 = y_max * scale_y

            rect = fitz.Rect(pdf_x0, pdf_y0, pdf_x1, pdf_y1)
            rect_h = max(1.0, rect.height)
            font_size = max(4.0, rect_h * 0.75)

            kw = {
                "render_mode": 3,
                "align": fitz.TEXT_ALIGN_LEFT,
            }
            if font_path:
                kw["fontfile"] = font_path
            else:
                kw["fontname"] = "cjk"

            placed = False
            cur_size = font_size
            while cur_size >= 4.0:
                kw["fontsize"] = cur_size
                res = page.insert_textbox(rect, text, **kw)
                if res >= 0:
                    placed = True
                    break
                cur_size -= 0.5

            if not placed:
                origin = fitz.Point(rect.x0, rect.y1 - (rect_h * 0.2))
                kw.pop("align", None)
                kw["point"] = origin
                kw["text"] = text
                kw["fontsize"] = cur_size
                page.insert_text(**kw)

            inserted_count += 1

        stats["total_inserted"] += inserted_count

        if pbar:
            pbar.set_postfix({"상태": f"{page_num}p OCR 완료 ({inserted_count}개)"})
        elif verbose:
            filter_info = f" (신뢰도 미달 제외 {filtered_count}개)" if filtered_count > 0 else ""
            print(f"  [{page_num}/{total_pages}p] 인식: {len(results)}개, 삽입: {inserted_count}개{filter_info}")

    if pbar:
        pbar.close()

    # 5. 최적화 저장
    doc.save(output_path, garbage=4, deflate=True)
    doc.close()

    # 메모리 정리
    if use_gpu and torch is not None and torch.cuda.is_available():
        torch.cuda.empty_cache()
    gc.collect()

    return output_path, stats


def main():
    parser = argparse.ArgumentParser(
        description="PDF 파일(또는 와일드카드 *.pdf)에 고정밀 한글 OCR을 수행하고 검색 가능한 투명 텍스트 레이어를 추가합니다."
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        default=["*.pdf"],
        help="입력 PDF 파일 경로 또는 패턴 (예: document.pdf, *.pdf, docs/*.pdf). 생략 시 현재 폴더의 *.pdf 처리",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="출력 파일 경로 또는 출력 디렉토리 (미지정 시 <원본경로>/ocr/<파일명>.pdf 로 자동 저장)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=250,
        help="OCR 렌더링 해상도 (기본값: 250 DPI. 스캔 품질에 따라 200~300 권장)",
    )
    parser.add_argument(
        "--lang",
        default="ko,en",
        help="OCR 언어 쉼표 구분 목록 (기본값: 'ko,en')",
    )
    parser.add_argument(
        "--gpu",
        action="store_true",
        default=None,
        help="GPU 가속 강제 활성화",
    )
    parser.add_argument(
        "--no-gpu",
        dest="gpu",
        action="store_false",
        help="GPU 가속 비활성화 (CPU 강제 사용)",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.25,
        help="텍스트 레이어로 삽입할 최소 OCR 신뢰도 (0.0~1.0, 기본값: 0.25)",
    )
    parser.add_argument(
        "--force-ocr",
        action="store_true",
        help="기존에 텍스트가 풍부한 페이지라도 건너뛰지 않고 무조건 OCR을 강제 실행합니다.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="이미 ocr/<파일명>.pdf 결과 파일이 존재하는 경우 해당 파일 처리를 건너뜁니다.",
    )
    parser.add_argument(
        "--paragraph",
        action="store_true",
        help="인접 단어를 문단/문장 단위로 묶어서 텍스트 레이어 생성 (드래그/복사 품질 향상)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=4,
        help="OCR 인식 배치 크기 (GPU 가속 시 4~8 권장, 기본값: 4)",
    )
    parser.add_argument(
        "--font",
        default=None,
        help="사용자 정의 한글 TTF/TTC 폰트 파일 경로",
    )
    parser.add_argument(
        "--include-ocr-files",
        action="store_true",
        help="와일드카드 검색 시 'ocr' 폴더 내의 파일도 대상에 포함합니다.",
    )

    args = parser.parse_args()
    lang_list = [l.strip() for l in args.lang.split(",") if l.strip()]

    target_files = expand_input_files(
        args.inputs,
        exclude_ocr_outputs=not args.include_ocr_files
    )

    if not target_files:
        print(f"[알림] 처리할 PDF 파일을 찾지 못했습니다. (입력 패턴: {' '.join(args.inputs)})")
        sys.exit(0)

    check_dependencies()

    use_gpu = args.gpu
    if use_gpu is None:
        use_gpu = torch is not None and torch.cuda.is_available()

    font_path = args.font if (args.font and os.path.exists(args.font)) else find_korean_font()

    print(f"==================================================")
    print(f"[*] 처리 대상 PDF 파일 수: {len(target_files)}개")
    print(f"[*] OCR 언어: {', '.join(lang_list)}")
    print(f"[*] 하드웨어 가속: {'GPU (CUDA)' if use_gpu else 'CPU (GPU 미활성화)'}")
    if not use_gpu and torch is not None:
        print(f"    - Tip: NVIDIA GPU가 있는 경우 CUDA용 PyTorch 설치 시 10~20배 이상 빨라집니다.")
    print(f"[*] 렌더링 해상도: {args.dpi} DPI")
    print(f"[*] 스마트 스킵: {'비활성화 (--force-ocr)' if args.force_ocr else '활성화 (기존 디지털 텍스트 페이지 자동 패스)'}")
    print(f"[*] 한글 폰트 매핑: {font_path if font_path else 'PyMuPDF 기본 CJK 폰트'}")
    print(f"==================================================\n")

    print("[*] EasyOCR 모델을 메모리에 로드 중입니다...")
    reader = easyocr.Reader(lang_list, gpu=use_gpu)
    print("[*] 로드 완료. 작업을 시작합니다.\n")

    success_count = 0
    fail_count = 0
    skipped_count = 0

    for idx, input_file in enumerate(target_files, 1):
        filename = os.path.basename(input_file)
        print(f"--- [{idx}/{len(target_files)}] {filename} ---")

        file_output = None
        if args.output:
            if len(target_files) == 1 and not os.path.isdir(args.output) and args.output.lower().endswith(".pdf"):
                file_output = args.output
            else:
                file_output = get_default_output_path(input_file, output_dir=args.output)
        else:
            file_output = get_default_output_path(input_file)

        # --resume 옵션: 이미 출력 파일이 존재하면 스킵
        if args.resume and os.path.exists(file_output):
            print(f"  [건너뜀] 이미 결과 파일이 존재합니다: {os.path.basename(file_output)}\n")
            skipped_count += 1
            continue

        try:
            out_path, stats = process_pdf_ocr(
                input_path=input_file,
                output_path=file_output,
                reader=reader,
                languages=lang_list,
                dpi=args.dpi,
                use_gpu=use_gpu,
                min_confidence=args.confidence,
                skip_text_pages=not args.force_ocr,
                paragraph=args.paragraph,
                batch_size=args.batch_size,
                font_path=font_path,
                verbose=True,
            )
            print(f"  [+] 완료: {out_path}")
            print(f"      (총 {stats['total_pages']}p 중 OCR 처리: {stats['ocr_pages']}p, 기존텍스트 패스: {stats['skipped_pages']}p, 주입된 텍스트 블록: {stats['total_inserted']}개)\n")
            success_count += 1
        except Exception as e:
            print(f"  [!] 파일 처리 중 오류 발생: {e}\n", file=sys.stderr)
            fail_count += 1

    print(f"==================================================")
    print(f"[*] 전체 작업 완료: 성공 {success_count}개, 건너뜀 {skipped_count}개, 실패 {fail_count}개")
    print(f"==================================================")


if __name__ == "__main__":
    main()
