import os
import json
import asyncio
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError
import requests
import typing

# 프로젝트 내 타 스크립트 모듈 임포트
import pre_srt
import post_srt
from verify_srt import parse_srt_content, verify_srt_files

# .env 파일 로드
load_dotenv()

app = FastAPI(title="Media Subtitle Translator")

# 정적 파일 서빙 설정
# static 디렉토리가 없으면 자동 생성
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

class TranslateRequest(BaseModel):
    file_path: str
    primary_model: str
    fallback_model: str
    primary_provider: str = "gemini"   # 'gemini' or 'openrouter'
    fallback_provider: str = "gemini"

@app.get("/")
def read_index():
    return FileResponse("static/index.html")

@app.get("/api/key_status")
def check_key_status():
    """각 모델 제공자별 API 키 설정 여부를 반환합니다."""
    return {
        "gemini": bool(os.environ.get("GEMINI_API_KEY")),
        "openrouter": bool(os.environ.get("OPENROUTER_API_KEY"))
    }

@app.get("/api/default_directory")
def get_default_directory():
    """서버의 현재 작업 디렉토리를 반환하여 UI에 기본값으로 설정할 수 있도록 합니다."""
    return {"directory": os.getcwd()}

@app.get("/api/scan")
def scan_directory(directory: str = Query(..., description="스캔할 로컬 디렉토리 경로")):
    """지정한 디렉토리 내의 번역 대상 SRT 파일 목록을 반환합니다."""
    if not os.path.exists(directory):
        raise HTTPException(status_code=400, detail="존재하지 않는 디렉토리 경로입니다.")
    if not os.path.isdir(directory):
        raise HTTPException(status_code=400, detail="유효한 디렉토리가 아닙니다.")

    srt_files = []
    try:
        for item in os.listdir(directory):
            full_path = os.path.join(directory, item)
            # 파일이고 확장자가 .srt이되, 전처리 파일(_pre)이나 번역본((kr)), 후처리본(fixed_)은 제외
            if (os.path.isfile(full_path) and 
                item.lower().endswith(".srt") and 
                not item.endswith("_pre.srt") and 
                " (kr)" not in item and 
                not item.startswith("fixed_")):
                
                # 파일 사이즈 구하기
                size_bytes = os.path.getsize(full_path)
                
                # 자막 개수 추산 및 읽기
                try:
                    with open(full_path, 'r', encoding='utf-8-sig') as f:
                        content = f.read()
                    blocks = parse_srt_content(content)
                    block_count = len(blocks)
                except Exception:
                    block_count = 0

                srt_files.append({
                    "filename": item,
                    "path": full_path,
                    "size_bytes": size_bytes,
                    "block_count": block_count,
                    "estimated_chunks": (block_count + 99) // 100
                })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"디렉토리 스캔 오류: {str(e)}")

    return {"directory": directory, "files": srt_files}


def translate_chunk_with_gemini(client, model_name: str, chunk_blocks: list) -> list:
    """Gemini API를 사용하여 단일 청크를 번역하고 구조를 파싱합니다."""
    # 청크를 SRT 포맷 텍스트로 빌드
    srt_input = ""
    for b in chunk_blocks:
        srt_input += f"{b['index']}\n{b['start']} --> {b['end']}\n{b['text']}\n\n"
        
    system_instruction = (
        "You are an expert subtitle translator. Translate the English subtitles into Korean.\n"
        "Strict Guidelines:\n"
        "1. Maintain a strict 1:1 match for indices and timestamps. Every block index and timestamp in the translation must match the source exactly (to the millisecond). Do not skip, merge, or change indices or time codes.\n"
        "2. Translate into natural, polite conversational Korean using polite sentence endings like '~요' or '~습니다'. Never use informal language (반말/해라체).\n"
        "3. Output ONLY the raw translated SRT text. Do not include markdown code fences (like ```), explanations, notes, or introductions."
    )
    
    prompt = f"Please translate the following SRT content into Korean, keeping the exact same structure and timestamps:\n\n{srt_input}"
    
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2, # 일관성 있는 포맷 유지를 위해 낮은 온도 사용
        )
    )
    
    translated_text = response.text.strip()
    
    # 마크다운 코드 블록 제거용 정제
    if translated_text.startswith("```"):
        lines = translated_text.split('\n')
        filtered_lines = [l for l in lines if not (l.startswith("```") or l.strip() == "srt")]
        translated_text = '\n'.join(filtered_lines).strip()
        
    return parse_srt_content(translated_text)


def translate_chunk_with_openrouter(api_key: str, base_url: typing.Optional[str], model_name: str, chunk_blocks: list, temperature: float = 0.2) -> list:
    """OpenRouter-compatible HTTP endpoint로 단일 청크를 번역 요청합니다.

    이 함수는 여러 OpenRouter 호환 엔드포인트 형태를 시도하여 가장 적합한 응답 필드를 추출하려고 합니다.
    응답에서 텍스트 추출에 실패하면 예외를 발생시킵니다.
    """
    srt_input = ""
    for b in chunk_blocks:
        srt_input += f"{b['index']}\n{b['start']} --> {b['end']}\n{b['text']}\n\n"

    system_instruction = (
        "You are an expert subtitle translator. Translate the English subtitles into Korean.\n"
        "Strict Guidelines:\n"
        "1. Maintain a strict 1:1 match for indices and timestamps. Every block index and timestamp in the translation must match the source exactly (to the millisecond). Do not skip, merge, or change indices or time codes.\n"
        "2. Translate into natural, polite conversational Korean using polite sentence endings like '~요' or '~습니다'. Never use informal language (반말/해라체).\n"
        "3. Output ONLY the raw translated SRT text. Do not include markdown code fences (like ```), explanations, notes, or introductions."
    )

    prompt = f"Please translate the following SRT content into Korean, keeping the exact same structure and timestamps:\n\n{srt_input}"

    # 기본 베이스 URL 선택
    endpoints = []
    if base_url:
        # 사용자가 base_url을 제공하면 여러 후보 조합 시도
        endpoints.extend([
            base_url.rstrip('/') + '/responses',
            base_url.rstrip('/') + '/v1/responses',
            base_url.rstrip('/') + '/v1/chat/completions',
            base_url.rstrip('/') + '/chat/completions',
        ])
    # 공용 OpenRouter 기본 엔드포인트
    endpoints.extend([
        'https://api.openrouter.ai/v1/responses',
        'https://api.openrouter.ai/v1/chat/completions',
        'https://api.openrouter.ai/v1/completions',
    ])

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    last_exc = None
    for url in endpoints:
        try:
            # 시도 1: /responses 스타일
            if url.endswith('/responses'):
                body = {
                    'model': model_name,
                    'input': prompt,
                    'temperature': temperature,
                }
                resp = requests.post(url, json=body, headers=headers, timeout=60)
                resp.raise_for_status()
                j = resp.json()
                # OpenRouter /responses 응답에서 텍스트 찾기
                # 예상: { output: [ { content: [ { type: 'output_text', text: '...' } ] } ] }
                if isinstance(j, dict):
                    out = None
                    if 'output' in j and isinstance(j['output'], list) and j['output']:
                        first = j['output'][0]
                        if isinstance(first, dict) and 'content' in first and isinstance(first['content'], list):
                            # join all text pieces
                            texts = []
                            for c in first['content']:
                                if isinstance(c, dict) and 'text' in c:
                                    texts.append(c['text'])
                            if texts:
                                out = '\n'.join(texts)
                    if out:
                        return parse_srt_content(out)

            # 시도 2: /chat/completions 스타일
            if 'chat.completions' in url:
                messages = [
                    { 'role': 'system', 'content': system_instruction },
                    { 'role': 'user', 'content': prompt }
                ]
                body = {
                    'model': model_name,
                    'messages': messages,
                    'temperature': temperature
                }
                resp = requests.post(url, json=body, headers=headers, timeout=60)
                resp.raise_for_status()
                j = resp.json()
                # 일반적인 OpenAI형 응답 처리
                if isinstance(j, dict) and 'choices' in j and isinstance(j['choices'], list) and j['choices']:
                    text = None
                    choice = j['choices'][0]
                    if isinstance(choice, dict):
                        if 'message' in choice and isinstance(choice['message'], dict) and 'content' in choice['message']:
                            text = choice['message']['content']
                        elif 'text' in choice:
                            text = choice['text']
                    if text:
                        return parse_srt_content(text)

            # 시도 3: /completions 스타일
            if url.endswith('/completions') or url.endswith('/v1/completions'):
                body = {
                    'model': model_name,
                    'prompt': system_instruction + '\n' + prompt,
                    'temperature': temperature,
                    'max_tokens': 2000
                }
                resp = requests.post(url, json=body, headers=headers, timeout=60)
                resp.raise_for_status()
                j = resp.json()
                if isinstance(j, dict) and 'choices' in j and j['choices']:
                    c = j['choices'][0]
                    if isinstance(c, dict) and 'text' in c:
                        return parse_srt_content(c['text'])

        except Exception as e:
            last_exc = e
            # 다른 엔드포인트를 시도
            continue

    # 모든 시도 실패
    raise Exception(f"OpenRouter 요청/파싱 실패. 마지막 오류: {last_exc}")


def translate_chunk(provider: str, api_key: str, base_url: typing.Optional[str], model_name: str, chunk_blocks: list) -> list:
    """플러그형 번역 호출. provider에 따라 내부 호출을 분기."""
    if provider == 'gemini':
        client = genai.Client(api_key=api_key)
        return translate_chunk_with_gemini(client, model_name, chunk_blocks)
    elif provider == 'openrouter':
        return translate_chunk_with_openrouter(api_key, base_url, model_name, chunk_blocks)
    else:
        raise Exception(f"Unknown provider: {provider}")


def verify_chunk(original_chunk: list, translated_chunk: list) -> bool:
    """단일 청크 내의 블록 개수, 인덱스, 타임스탬프 1:1 일치 여부를 검증합니다."""
    if len(original_chunk) != len(translated_chunk):
        return False
    for i in range(len(original_chunk)):
        orig = original_chunk[i]
        trans = translated_chunk[i]
        if orig['index'] != trans['index']:
            return False
        if orig['start'] != trans['start'] or orig['end'] != trans['end']:
            return False
        if not trans['text'].strip():
            return False
    return True


@app.post("/api/translate")
async def translate_srt(request: TranslateRequest):
    """자막 번역 실행 파이프라인 (SSE 스트리밍으로 로그 및 진행률 반환)"""
    
    async def sse_generator():
        # helper to send json logs
        def log_event(step: str, status: str, message: str, percent: int = 0, extra: dict = None):
            # 표준 출력으로 진행 상황 출력
            print(f"[{step.upper()}] {message} ({percent}%)", flush=True)
            data = {"step": step, "status": status, "message": message, "percent": percent}
            if extra:
                data.update(extra)
            return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        # 기본 API 키 상태 (개별 청크 호출 시 각 provider의 키를 검증함)
        gemini_key = os.environ.get("GEMINI_API_KEY")
        openrouter_key = os.environ.get("OPENROUTER_API_KEY")
        if not gemini_key and not openrouter_key:
            yield log_event("init", "error", "지원되는 모델 제공자(GEMINI_API_KEY 또는 OPENROUTER_API_KEY)가 설정되어 있지 않습니다. .env 파일을 작성해 주세요.")
            return

        file_path = request.file_path
        if not os.path.exists(file_path):
            yield log_event("init", "error", f"파일을 찾을 수 없습니다: {file_path}")
            return

        directory = os.path.dirname(file_path)
        filename = os.path.basename(file_path)
        base, ext = os.path.splitext(filename)
        
        yield log_event("init", "success", f"번역 작업을 준비 중입니다: {filename}", percent=5)
        await asyncio.sleep(0.1)

        # ----------------------------------------------------
        # 1. 번역 전처리 (pre_srt.py 실행)
        # ----------------------------------------------------
        yield log_event("pre_process", "running", "영어 자막 문장 구분 조정 전처리 실행 중 (pre_srt.py)...", percent=10)
        await asyncio.sleep(0.1)
        
        try:
            remove_targets = pre_srt.load_remove_targets()
            # pre_srt는 process_file 함수를 노출함
            success = pre_srt.process_file(file_path, remove_targets)
            if not success:
                yield log_event("pre_process", "error", "전처리 스크립트 실행에 실패했습니다.")
                return
        except Exception as e:
            yield log_event("pre_process", "error", f"전처리 실행 중 예외 발생: {str(e)}")
            return

        pre_file_path = f"{os.path.join(directory, base)}_pre{ext}"
        if not os.path.exists(pre_file_path):
            yield log_event("pre_process", "error", f"전처리 파일 생성 확인 실패: {pre_file_path}")
            return

        yield log_event("pre_process", "success", f"전처리 완료: {os.path.basename(pre_file_path)} 생성됨.", percent=20)
        await asyncio.sleep(0.1)

        # ----------------------------------------------------
        # 2. 전처리 파일 로드 및 100개 단위 청크 분류
        # ----------------------------------------------------
        try:
            with open(pre_file_path, 'r', encoding='utf-8-sig') as f:
                pre_content = f.read()
            pre_blocks = parse_srt_content(pre_content)
        except Exception as e:
            yield log_event("chunking", "error", f"전처리 파일 분석 실패: {str(e)}")
            return

        total_blocks = len(pre_blocks)
        if total_blocks == 0:
            yield log_event("chunking", "error", "전처리 파일에 파싱할 수 있는 자막 블록이 없습니다.")
            return

        chunk_size = 100
        chunks = [pre_blocks[i:i + chunk_size] for i in range(0, total_blocks, chunk_size)]
        total_chunks = len(chunks)
        
        yield log_event("chunking", "success", f"총 {total_blocks}개의 자막 블록 로드. {total_chunks}개 청크(100개 단위)로 분할 완료.", percent=25)
        await asyncio.sleep(0.1)

        # ----------------------------------------------------
        # 3. 청크별 번역 루프 (기본 모델 -> 실패 시 대체 모델)
        # ----------------------------------------------------
        all_translated_blocks = []

        # OpenRouter 설정 읽기
        openrouter_api_key = os.environ.get('OPENROUTER_API_KEY')
        openrouter_base = os.environ.get('OPENROUTER_BASE_URL')

        for idx, chunk in enumerate(chunks):
            chunk_num = idx + 1
            progress_percent = int(25 + (chunk_num / total_chunks) * 55) # 번역 구간은 25% ~ 80% 가중치

            success = False
            translated_chunk = []

            # ----------------------------------------------------
            # 3-1. 기본 모델로 시도 (429/503 에러 발생 시 자동 대기 재시도)
            # ----------------------------------------------------
            api_retry = 0
            max_api_retries = 3
            
            while api_retry < max_api_retries:
                api_retry += 1
                yield log_event(
                    "translate",
                    "running",
                    f"청크 {chunk_num}/{total_chunks} 번역 요청 중 ({request.primary_model} @ {request.primary_provider})... (시도 {api_retry}/{max_api_retries})",
                    percent=progress_percent,
                    extra={"chunk": chunk_num, "total_chunks": total_chunks}
                )

                try:
                    loop = asyncio.get_event_loop()
                    # provider별로 적절한 키/endpoint를 선택하여 호출
                    primary_provider = (request.primary_provider or 'gemini').lower()
                    if primary_provider == 'gemini':
                        gemini_key = os.environ.get('GEMINI_API_KEY')
                        if not gemini_key:
                            raise Exception('GEMINI_API_KEY가 설정되어 있지 않습니다.')
                        translated_chunk = await loop.run_in_executor(
                            None, translate_chunk, 'gemini', gemini_key, None, request.primary_model, chunk
                        )
                    elif primary_provider == 'openrouter':
                        or_key = os.environ.get('OPENROUTER_API_KEY')
                        if not or_key:
                            raise Exception('OPENROUTER_API_KEY가 설정되어 있지 않습니다.')
                        or_base = os.environ.get('OPENROUTER_BASE_URL')
                        translated_chunk = await loop.run_in_executor(
                            None, translate_chunk, 'openrouter', or_key, or_base, request.primary_model, chunk
                        )
                    else:
                        raise Exception(f"지원되지 않는 provider: {primary_provider}")

                    if verify_chunk(chunk, translated_chunk):
                        success = True
                        yield log_event(
                            "translate",
                            "success_chunk",
                            f"청크 {chunk_num} 검증 성공 ({request.primary_model} @ {primary_provider})",
                            percent=progress_percent,
                            extra={"chunk": chunk_num, "total_chunks": total_chunks}
                        )
                        break
                    else:
                        # API 호출은 정상이었으나 검증 실패 (개수/타임스탬프 불일치)
                        yield log_event(
                            "translate",
                            "warning",
                            f"청크 {chunk_num} 검증 실패 (개수 또는 타임스탬프 불일치).",
                            percent=progress_percent,
                            extra={"chunk": chunk_num, "total_chunks": total_chunks}
                        )
                        # 즉시 루프를 빠져나와 대체 모델로 전환
                        break

                except Exception as e:
                    err_msg = str(e)
                    is_retryable = False
                    is_429 = False
                    is_503 = False
                    
                    if isinstance(e, APIError):
                        if e.code == 429:
                            is_429 = True
                            is_retryable = True
                        elif e.code == 503:
                            is_503 = True
                            is_retryable = True
                    else:
                        if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                            is_429 = True
                            is_retryable = True
                        elif "503" in err_msg or "UNAVAILABLE" in err_msg:
                            is_503 = True
                            is_retryable = True
                            
                    if is_retryable and api_retry < max_api_retries:
                        if is_429:
                            wait_time = 20
                            import re
                            match = re.search(r'retry in ([\d\.]+)s', err_msg, re.IGNORECASE)
                            if match:
                                try:
                                    wait_time = int(float(match.group(1))) + 2
                                except Exception:
                                    pass
                            yield log_event(
                                "translate", 
                                "warning", 
                                f"청크 {chunk_num} 번역 중 API 할당량 초과(429) 감지. {wait_time}초 대기 후 재시도합니다...", 
                                percent=progress_percent,
                                extra={"chunk": chunk_num, "total_chunks": total_chunks}
                            )
                        elif is_503:
                            wait_time = 8  # 503 일시적 장애는 8초 대기 후 재시도
                            yield log_event(
                                "translate", 
                                "warning", 
                                f"청크 {chunk_num} 번역 중 서버 부하(503) 감지. {wait_time}초 대기 후 재시도합니다...", 
                                percent=progress_percent,
                                extra={"chunk": chunk_num, "total_chunks": total_chunks}
                            )
                        await asyncio.sleep(wait_time)
                    else:
                        # 재시도 불가 오류이거나 최대 시도 횟수 초과
                        yield log_event(
                            "translate", 
                            "warning", 
                            f"청크 {chunk_num} 번역 중 오류 발생: {err_msg}.", 
                            percent=progress_percent,
                            extra={"chunk": chunk_num, "total_chunks": total_chunks}
                        )
                        # 즉시 루프를 빠져나와 대체 모델로 전환
                        break

            # ----------------------------------------------------
            # 3-2. 기본 모델 실패 시 대체 모델로 시도 (429/503 에러 발생 시 자동 대기 재시도)
            # ----------------------------------------------------
            if not success:
                api_retry = 0
                max_api_retries = 3
                
                while api_retry < max_api_retries:
                    api_retry += 1
                    yield log_event(
                        "translate", 
                        "running", 
                                    f"청크 {chunk_num}/{total_chunks} 대체 모델 재시도 중 ({request.fallback_model} @ {request.fallback_provider})... (시도 {api_retry}/{max_api_retries})", 
                        percent=progress_percent,
                        extra={"chunk": chunk_num, "total_chunks": total_chunks}
                    )
                    
                    try:
                        loop = asyncio.get_event_loop()
                        fallback_provider = (request.fallback_provider or 'gemini').lower()
                        if fallback_provider == 'gemini':
                            gemini_key = os.environ.get('GEMINI_API_KEY')
                            if not gemini_key:
                                raise Exception('GEMINI_API_KEY가 설정되어 있지 않습니다.')
                            translated_chunk = await loop.run_in_executor(
                                None, translate_chunk, 'gemini', gemini_key, None, request.fallback_model, chunk
                            )
                        elif fallback_provider == 'openrouter':
                            or_key = os.environ.get('OPENROUTER_API_KEY')
                            if not or_key:
                                raise Exception('OPENROUTER_API_KEY가 설정되어 있지 않습니다.')
                            or_base = os.environ.get('OPENROUTER_BASE_URL')
                            translated_chunk = await loop.run_in_executor(
                                None, translate_chunk, 'openrouter', or_key, or_base, request.fallback_model, chunk
                            )
                        else:
                            raise Exception(f"지원되지 않는 provider: {fallback_provider}")

                        if verify_chunk(chunk, translated_chunk):
                            success = True
                            yield log_event(
                                "translate",
                                "success_chunk",
                                f"청크 {chunk_num} 대체 모델 번역 및 검증 성공 ({request.fallback_model} @ {fallback_provider})",
                                percent=progress_percent,
                                extra={"chunk": chunk_num, "total_chunks": total_chunks}
                            )
                            break
                        else:
                            yield log_event(
                                "translate",
                                "error",
                                f"대체 모델({request.fallback_model})에서도 청크 {chunk_num} 검증 실패 (개수/타임스탬프 불일치).",
                                percent=progress_percent,
                                extra={"chunk": chunk_num, "total_chunks": total_chunks}
                            )
                            return # 최종 실패

                    except Exception as e:
                        err_msg = str(e)
                        is_retryable = False
                        is_429 = False
                        is_503 = False
                        
                        if isinstance(e, APIError):
                            if e.code == 429:
                                is_429 = True
                                is_retryable = True
                            elif e.code == 503:
                                is_503 = True
                                is_retryable = True
                        else:
                            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                                is_429 = True
                                is_retryable = True
                            elif "503" in err_msg or "UNAVAILABLE" in err_msg:
                                is_503 = True
                                is_retryable = True
                                
                        if is_retryable and api_retry < max_api_retries:
                            if is_429:
                                wait_time = 20
                                import re
                                match = re.search(r'retry in ([\d\.]+)s', err_msg, re.IGNORECASE)
                                if match:
                                    try:
                                        wait_time = int(float(match.group(1))) + 2
                                    except Exception:
                                        pass
                                yield log_event(
                                    "translate", 
                                    "warning", 
                                    f"대체 모델 청크 {chunk_num} 번역 중 API 할당량 초과(429) 감지. {wait_time}초 대기 후 재시도합니다...", 
                                    percent=progress_percent,
                                    extra={"chunk": chunk_num, "total_chunks": total_chunks}
                                )
                            elif is_503:
                                wait_time = 8
                                yield log_event(
                                    "translate", 
                                    "warning", 
                                    f"대체 모델 청크 {chunk_num} 번역 중 서버 부하(503) 감지. {wait_time}초 대기 후 재시도합니다...", 
                                    percent=progress_percent,
                                    extra={"chunk": chunk_num, "total_chunks": total_chunks}
                                )
                            await asyncio.sleep(wait_time)
                        else:
                            yield log_event(
                                "translate", 
                                "error", 
                                f"대체 모델 번역 중 오류 발생 (청크 {chunk_num}): {err_msg}", 
                                percent=progress_percent,
                                extra={"chunk": chunk_num, "total_chunks": total_chunks}
                            )
                            return # 최종 실패
                
                # 3회 시도 후 루프가 성공 없이 끝난 경우
                if not success:
                    yield log_event(
                        "translate", 
                        "error", 
                        f"대체 모델({request.fallback_model})에서 최대 재시도 후에도 청크 {chunk_num} 번역에 실패했습니다.", 
                        percent=progress_percent,
                        extra={"chunk": chunk_num, "total_chunks": total_chunks}
                    )
                    return

            all_translated_blocks.extend(translated_chunk)
            await asyncio.sleep(0.05)

        # ----------------------------------------------------
        # 4. 전체 파일 결합 및 로컬 저장
        # ----------------------------------------------------
        kr_file_path = f"{os.path.join(directory, base)} (kr){ext}"
        yield log_event("save", "running", f"번역 자막 결합 및 임시 저장 중... ({os.path.basename(kr_file_path)})", percent=82)
        await asyncio.sleep(0.1)

        try:
            with open(kr_file_path, 'w', encoding='utf-8') as f:
                for block in all_translated_blocks:
                    f.write(f"{block['index']}\n{block['start']} --> {block['end']}\n{block['text']}\n\n")
        except Exception as e:
            yield log_event("save", "error", f"파일 저장 오류: {str(e)}")
            return

        # ----------------------------------------------------
        # 5. 전체 정합성 최종 검증 (verify_srt_files 실행)
        # ----------------------------------------------------
        yield log_event("verify", "running", "최종 정합성 검증 스크립트 실행 중...", percent=87)
        await asyncio.sleep(0.1)
        
        is_valid, verify_msg = verify_srt_files(pre_file_path, kr_file_path)
        if not is_valid:
            yield log_event("verify", "error", f"최종 검증 실패: {verify_msg}")
            return
            
        yield log_event("verify", "success", f"최종 검증 성공: {verify_msg}", percent=90)
        await asyncio.sleep(0.1)

        # ----------------------------------------------------
        # 6. 후처리 파일 실행 (post_srt.py 실행 후 덮어쓰기)
        # ----------------------------------------------------
        yield log_event("post_process", "running", "자막 후처리 실행 중 (post_srt.py)...", percent=92)
        await asyncio.sleep(0.1)

        try:
            # post_srt 실행 전 디렉토리의 기존 fixed_*.srt 파일 리스트 기록
            existing_fixed = {
                f for f in os.listdir(directory) if f.startswith("fixed_") and f.endswith(".srt")
            }

            # post_srt의 process_srt는 디렉토리를 통째로 후처리
            # 디렉토리 내의 모든 .srt 파일에 대해 fixed_ 파일들을 생성
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, post_srt.process_srt, directory)

            # 생성된 fixed_a (kr).srt 확인 및 덮어쓰기
            fixed_kr_filename = f"fixed_{base} (kr){ext}"
            fixed_kr_path = os.path.join(directory, fixed_kr_filename)

            if os.path.exists(fixed_kr_path):
                # 기존 a (kr).srt 삭제 후 이름 변경하여 덮어쓰기
                if os.path.exists(kr_file_path):
                    os.remove(kr_file_path)
                os.rename(fixed_kr_path, kr_file_path)
            else:
                yield log_event("post_process", "error", f"후처리 결과 파일을 찾을 수 없습니다: {fixed_kr_filename}")
                return

            # 이번 작업으로 새롭게 생긴 불필요한 fixed_*.srt 파일들 정리
            # (예: fixed_a.srt, fixed_a_pre.srt)
            for item in os.listdir(directory):
                if (item.startswith("fixed_") and 
                    item.endswith(".srt") and 
                    item not in existing_fixed and 
                    item != fixed_kr_filename):
                    
                    try:
                        os.remove(os.path.join(directory, item))
                    except Exception:
                        pass

        except Exception as e:
            yield log_event("post_process", "error", f"후처리 실행 중 오류 발생: {str(e)}")
            return

        yield log_event("post_process", "success", "후처리 완료 및 최종본 덮어쓰기 성공.", percent=98)
        await asyncio.sleep(0.1)

        # ----------------------------------------------------
        # 7. 번역 프로세스 최종 성공 종료
        # ----------------------------------------------------
        yield log_event(
            "complete", 
            "success", 
            f"번역 및 후처리가 완료되었습니다! 최종 파일: {base} (kr){ext}", 
            percent=100,
            extra={"final_file": kr_file_path}
        )

    return StreamingResponse(sse_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    # uvicorn 실행
    uvicorn.run("web_server:app", host="127.0.0.1", port=8000, reload=True)
