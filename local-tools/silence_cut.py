"""무음 구간 자동 삭제 (ffmpeg silencedetect 기반, FilmCraft 원본 코드 수정 없음).

동작:
  1. 실행 중인 FilmCraft(--control 9876)에서 현재 시퀀스의 오디오를 WAV로 내보낸다.
     (--media 를 주면 그 파일을 대신 분석한다. 이때는 파일 시간 = 시퀀스 시간으로 본다.)
  2. ffmpeg silencedetect 로 무음 구간을 찾는다 (기준 dB, 최소 길이 설정 가능).
  3. 구간마다 앞뒤 여백을 남기고, 뒤쪽 구간부터 In/Out 지정 → Extract(리플 삭제)한다.
     뒤에서부터 지우므로 앞쪽 구간의 시간이 밀리지 않는다.

사용 예:
  python silence_cut.py                          # 값을 하나씩 물어본다
  python silence_cut.py --db -35 --min 0.6 --pad 0.15
  python silence_cut.py --dry-run                # 찾기만 하고 지우지 않음
  python silence_cut.py --markers                # 지우지 않고 범위 마커만 표시

되돌리기: 구간 하나가 실행 취소(Ctrl+Z) 한 단계다. 실행 전에 프로젝트를 저장해 두는 것을 권장.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fc_control import DEFAULT_PORT, Control, ControlError, utf8_console

_START = re.compile(r"silence_start:\s*(-?[\d.]+)")
_END = re.compile(r"silence_end:\s*(-?[\d.]+)")
_DURATION = re.compile(r"Duration:\s*(\d+):(\d+):([\d.]+)")


def find_ffmpeg(explicit: str | None) -> str:
    exe = explicit or shutil.which("ffmpeg")
    if not exe:
        raise SystemExit("ffmpeg를 찾을 수 없습니다. 설치하거나 --ffmpeg 로 경로를 지정하세요.")
    return exe


def detect_silences(ffmpeg: str, media: str, db: float, min_len: float) -> tuple[list[tuple[float, float]], float]:
    """무음 구간 [(시작초, 끝초)] 과 전체 길이(초)."""
    cmd = [ffmpeg, "-hide_banner", "-nostats", "-i", media, "-vn", "-af", f"silencedetect=noise={db}dB:d={min_len}", "-f", "null", "-"]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    log = proc.stderr
    if proc.returncode != 0:
        raise SystemExit(f"ffmpeg 실행 실패:\n{log[-2000:]}")
    total = 0.0
    if m := _DURATION.search(log):
        total = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    silences: list[tuple[float, float]] = []
    start: float | None = None
    for line in log.splitlines():
        if m := _START.search(line):
            start = max(0.0, float(m.group(1)))
        elif (m := _END.search(line)) and start is not None:
            silences.append((start, float(m.group(1))))
            start = None
    if start is not None and total > start:  # 파일이 무음으로 끝남
        silences.append((start, total))
    return silences, total


def cut_ranges(silences: list[tuple[float, float]], pad: float, total: float, min_cut: float) -> list[tuple[float, float]]:
    """앞뒤로 pad 초씩 남긴 실제 삭제 구간. 파일 맨 앞/맨 끝 쪽은 여백을 남기지 않는다."""
    out = []
    for s, e in silences:
        a = s if s <= 0.0 else s + pad
        b = e if total and e >= total - 1e-3 else e - pad
        if b - a >= min_cut:
            out.append((a, b))
    return out


def fmt(t: float) -> str:
    m, s = divmod(t, 60)
    h, m = divmod(int(m), 60)
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def ask(prompt: str, default: float) -> float:
    raw = input(f"{prompt} [{default}]: ").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        print("  숫자가 아니라서 기본값을 씁니다.")
        return default


def main(argv: list[str]) -> int:
    utf8_console()
    p = argparse.ArgumentParser(description="FilmCraft 무음 구간 자동 삭제")
    p.add_argument("--db", type=float, help="이 값(dB)보다 작은 소리를 무음으로 본다 (기본 -35)")
    p.add_argument("--min", dest="min_len", type=float, help="이 길이(초) 이상 이어진 무음만 찾는다 (기본 0.5)")
    p.add_argument("--pad", type=float, help="삭제 구간 앞뒤로 남길 여백(초) (기본 0.15)")
    p.add_argument("--media", help="시퀀스 대신 이 미디어 파일을 분석 (파일 시간 = 시퀀스 시간)")
    p.add_argument("--dry-run", action="store_true", help="찾기만 하고 지우지 않음")
    p.add_argument("--markers", action="store_true", help="지우지 않고 범위 마커만 추가")
    p.add_argument("--yes", action="store_true", help="삭제 전 확인을 묻지 않음")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--ffmpeg", help="ffmpeg.exe 경로 (기본: PATH 에서 찾음)")
    a = p.parse_args(argv)

    interactive = a.db is None and a.min_len is None and a.pad is None
    if interactive:
        print("Enter 만 누르면 [기본값]을 씁니다.")
        a.db = ask("무음 기준 dB (작을수록 더 조용해야 무음, 예: -40)", -35.0)
        a.min_len = ask("최소 무음 길이(초)", 0.5)
        a.pad = ask("앞뒤로 남길 여백(초)", 0.15)
    a.db = -35.0 if a.db is None else a.db
    a.min_len = 0.5 if a.min_len is None else a.min_len
    a.pad = 0.15 if a.pad is None else max(0.0, a.pad)

    ffmpeg = find_ffmpeg(a.ffmpeg)
    try:
        with Control(port=a.port, timeout=3600) as c:
            if a.media:
                media = a.media
                tmp = None
            else:
                tmp = tempfile.mkdtemp(prefix="fc-silence-")
                media = os.path.join(tmp, "sequence.wav")
                print("시퀀스 오디오를 내보내는 중…")
                c.export_sequence_audio(media)

            print(f"무음 찾는 중 (기준 {a.db} dB, 최소 {a.min_len} 초)…")
            silences, total = detect_silences(ffmpeg, media, a.db, a.min_len)
            if tmp:
                shutil.rmtree(tmp, ignore_errors=True)
            fps = sequence_fps(c)
            frames = to_frames(cut_ranges(silences, a.pad, total, min_cut=0.05), fps)

            removed = sum(o - i + 1 for i, o in frames) / fps
            print(f"찾은 구간 {len(frames)}개, 합계 {removed:.2f}초 (전체 {total:.2f}초, {fps:g}fps)")
            for n, (i, o) in enumerate(frames, 1):
                print(f"  {n:3d}. {fmt(i / fps)} ~ {fmt((o + 1) / fps)}  ({(o - i + 1) / fps:.2f}초)")
            if not frames or a.dry_run:
                return 0

            history = len(c.execute("history.list").get("undo", []))
            if a.markers:
                for i, o in frames:
                    mark(c, i, o)
                    c.execute("markers.addRangeInOut", {"name": "무음"})
                c.execute("markers.clearInOut", {"target": "program"})
                print(f"범위 마커 {len(frames)}개를 추가했습니다.")
                return 0

            if not a.yes and input("위 구간을 리플 삭제할까요? (y/N): ").strip().lower() not in ("y", "yes", "ㅛ"):
                print("취소했습니다.")
                return 0

            for n, (i, o) in enumerate(reversed(frames), 1):
                mark(c, i, o)
                c.execute("sequence.extract", {})
                print(f"\r삭제 중… {n}/{len(frames)}", end="", flush=True)
            c.execute("markers.clearInOut", {"target": "program"})
            steps = len(c.execute("history.list").get("undo", [])) - history
            print(f"\n완료: {len(frames)}개 구간, {removed:.2f}초 삭제.")
            print(f"되돌리려면 Ctrl+Z 를 {steps}번 (In/Out 지정도 한 단계씩 남습니다).")
    except ControlError as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1
    return 0


def sequence_fps(c: Control) -> float:
    rate = c.execute("sequence.inspect").get("settings", {}).get("frame_rate", {})
    num, den = rate.get("num") or 30, rate.get("den") or 1
    return num / den


def to_frames(ranges: list[tuple[float, float]], fps: float) -> list[tuple[int, int]]:
    """초 구간 → (In 프레임, Out 프레임). Out 프레임까지 지워지므로 구간 안쪽 프레임만 고른다
    (여백이 줄어들지 않게: In 은 올림, Out 은 끝 시각 바로 앞 프레임)."""
    out = []
    for s, e in ranges:
        i = math.ceil(s * fps - 1e-6)
        o = math.floor(e * fps + 1e-6) - 1
        if o >= i:
            out.append((i, o))
    return out


def mark(c: Control, in_frame: int, out_frame: int) -> None:
    c.execute("markers.markIn", {"frame": in_frame, "target": "program"})
    c.execute("markers.markOut", {"frame": out_frame, "target": "program"})


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
