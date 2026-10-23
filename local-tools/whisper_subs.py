"""Whisper large-v3 로 한국어 자막 생성 (로컬 실행, FilmCraft 원본 코드 수정 없음).

동작:
  1. 실행 중인 FilmCraft(--control 9876)에서 현재 시퀀스의 오디오를 WAV로 내보낸다.
     (--media 를 주면 그 파일을 대신 쓴다. 이때는 파일 시간 = 시퀀스 시간으로 본다.)
  2. faster-whisper 로 받아쓴다 (NVIDIA GPU가 있으면 GPU, 없으면 CPU).
  3. 단어 시간에 맞춰 자막 단위로 나눠 SRT 를 만들고, FilmCraft 에 새 자막 트랙으로 가져온다.

모델은 처음 한 번만 내려받고(large-v3 약 3GB) 그 뒤로는 오프라인으로 동작한다.
준비: powershell -ExecutionPolicy Bypass -File setup.ps1

사용 예:
  whisper-subs.bat                         # 현재 시퀀스 → 자막 트랙
  whisper-subs.bat --media 인터뷰.mp4 --no-import --out 인터뷰.srt
"""

from __future__ import annotations

import argparse
import os
import sys
import sysconfig
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fc_control import DEFAULT_PORT, Control, ControlError, utf8_console


def add_cuda_dlls() -> None:
    """pip 으로 설치한 cuBLAS / cuDNN DLL 을 CTranslate2 가 찾을 수 있게 PATH 에 추가."""
    base = os.path.join(sysconfig.get_paths()["purelib"], "nvidia")
    for sub in ("cublas", "cudnn"):
        d = os.path.join(base, sub, "bin")
        if os.path.isdir(d):
            os.add_dll_directory(d)
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")


def load_model(name: str, device: str):
    from faster_whisper import WhisperModel
    import ctranslate2

    if device == "auto":
        device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    if device == "cuda":
        try:
            return WhisperModel(name, device="cuda", compute_type="float16"), "GPU"
        except Exception as e:  # GPU 드라이버/라이브러리 문제 → CPU 로 계속
            print(f"GPU를 쓸 수 없어 CPU로 진행합니다: {e}")
    return WhisperModel(name, device="cpu", compute_type="int8"), "CPU"


def build_captions(words, max_chars: int, max_lines: int, max_seconds: float, gap: float, min_seconds: float = 1.0):
    """[(시작, 끝, 텍스트)] — 글자 수, 길이, 말 사이 쉼, 문장 끝에서 나눈다."""
    caps, cur = [], []

    def flush():
        if cur:
            caps.append((cur[0].start, cur[-1].end, "".join(w.word for w in cur).strip()))
            cur.clear()

    limit = max_chars * max_lines
    for w in words:
        if cur:
            length = len("".join(x.word for x in cur).strip()) + len(w.word)
            if length > limit or w.start - cur[-1].end > gap or w.end - cur[0].start > max_seconds:
                flush()
        cur.append(w)
        if w.word.strip().endswith((".", "?", "!", "。")):
            flush()
    flush()
    # 너무 짧게 지나가는 자막은 다음 자막과 겹치지 않는 선에서 최소 길이까지 늘린다
    for i, (s, e, t) in enumerate(caps):
        nxt = caps[i + 1][0] if i + 1 < len(caps) else e + min_seconds
        caps[i] = (s, max(e, min(s + min_seconds, nxt)), t)
    return caps


def wrap(text: str, max_chars: int, max_lines: int) -> str:
    """한 줄이 max_chars 를 넘으면 가운데에 가까운 띄어쓰기에서 줄을 나눈다."""
    if len(text) <= max_chars or max_lines < 2:
        return text
    spaces = [i for i, ch in enumerate(text) if ch == " "]
    if not spaces:
        return text
    mid = len(text) / 2
    i = min(spaces, key=lambda s: abs(s - mid))
    return text[:i].rstrip() + "\n" + text[i + 1 :].lstrip()


def srt_time(t: float) -> str:
    ms = int(round(max(0.0, t) * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(path: str, caps, max_chars: int, max_lines: int) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for n, (s, e, text) in enumerate(caps, 1):
            f.write(f"{n}\n{srt_time(s)} --> {srt_time(e)}\n{wrap(text, max_chars, max_lines)}\n\n")


def main(argv: list[str]) -> int:
    utf8_console()
    p = argparse.ArgumentParser(description="Whisper 로 자막 생성 → FilmCraft 자막 트랙")
    p.add_argument("--media", help="시퀀스 대신 이 미디어 파일을 받아쓰기")
    p.add_argument("--model", default="large-v3", help="Whisper 모델 (기본 large-v3; 빠르게: large-v3-turbo)")
    p.add_argument("--language", default="ko", help="언어 코드 (기본 ko, 자동 감지: auto)")
    p.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"])
    p.add_argument("--max-chars", type=int, default=18, help="자막 한 줄 최대 글자 수 (기본 18)")
    p.add_argument("--lines", type=int, default=2, help="자막 최대 줄 수 (기본 2)")
    p.add_argument("--max-seconds", type=float, default=6.0, help="자막 하나의 최대 길이(초)")
    p.add_argument("--out", help="SRT 저장 경로 (기본: 임시 폴더)")
    p.add_argument("--no-import", action="store_true", help="FilmCraft 로 가져오지 않고 SRT 만 만든다")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    a = p.parse_args(argv)

    if a.no_import and not a.media:
        p.error("--no-import 는 --media 와 함께 쓰세요")

    add_cuda_dlls()
    tmp = tempfile.mkdtemp(prefix="fc-whisper-")
    out = a.out or os.path.join(tmp, "whisper.srt")
    c = None
    try:
        if not a.no_import:
            c = Control(port=a.port, timeout=3600)
        if a.media:
            media = a.media
        else:
            media = os.path.join(tmp, "sequence.wav")
            print("시퀀스 오디오를 내보내는 중…")
            c.export_sequence_audio(media)

        print(f"모델 {a.model} 불러오는 중… (처음에는 내려받느라 오래 걸립니다)")
        model, where = load_model(a.model, a.device)
        print(f"받아쓰는 중 ({where})…")
        t0 = time.time()
        segments, info = model.transcribe(
            media,
            language=None if a.language == "auto" else a.language,
            beam_size=5,
            vad_filter=True,
            word_timestamps=True,
            condition_on_previous_text=False,
        )
        words = []
        for seg in segments:
            words.extend(seg.words or [])
            print(f"\r  {seg.end:7.1f} / {info.duration:.1f}초", end="", flush=True)
        print(f"\n받아쓰기 완료: {time.time() - t0:.0f}초 걸림")

        caps = build_captions(words, a.max_chars, a.lines, a.max_seconds, gap=0.8)
        if not caps:
            print("인식된 말이 없습니다.")
            return 0
        write_srt(out, caps, a.max_chars, a.lines)
        print(f"자막 {len(caps)}개 → {out}")

        if c and not a.no_import:
            c.execute("captions.import", {"path": out, "name": f"Whisper {a.model}"})
            print("FilmCraft 에 새 자막 트랙으로 가져왔습니다. (텍스트 패널 ▸ 자막에서 수정)")
    except ControlError as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1
    finally:
        if c:
            c.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
