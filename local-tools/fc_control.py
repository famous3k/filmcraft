"""FilmCraft 컨트롤 채널 클라이언트 (표준 라이브러리만 사용).

앱을 `filmcraft.exe --control 9876` 으로 실행해 두면, 이 모듈로 엔진 명령을 보낼 수 있다.
프로토콜: 한 줄에 JSON 하나 (docs/control-protocol.md).

    python fc_control.py engine.commands
    python fc_control.py engine.execute '{"command": "sequence.addEdit", "params": {"seconds": 3}}'
"""

from __future__ import annotations

import json
import os
import socket
import sys
import time

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9876


class ControlError(RuntimeError):
    pass


class Control:
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = 600.0):
        try:
            self._sock = socket.create_connection((host, port), timeout=timeout)
        except OSError as e:
            raise ControlError(
                f"FilmCraft에 연결할 수 없습니다 ({host}:{port}). "
                f"앱을 '--control {port}' 옵션으로 실행했는지 확인하세요. ({e})"
            ) from e
        self._file = self._sock.makefile("rwb")
        self._next_id = 1

    def call(self, method: str, params: dict | None = None):
        msg = {"id": self._next_id, "method": method, "params": params or {}}
        self._next_id += 1
        self._file.write((json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8"))
        self._file.flush()
        line = self._file.readline()
        if not line:
            raise ControlError("FilmCraft가 연결을 닫았습니다.")
        reply = json.loads(line.decode("utf-8"))
        if not reply.get("ok"):
            raise ControlError(str(reply.get("error", reply)))
        return reply.get("result")

    def execute(self, command: str, params: dict | None = None):
        return self.call("engine.execute", {"command": command, "params": params or {}})

    def export_sequence_audio(self, path: str, timeout: float = 3600.0) -> None:
        """현재 시퀀스 전체의 오디오를 WAV 로 내보내고 끝날 때까지 기다린다.

        file.exportMedia 는 백그라운드 작업(job)으로 돌아가므로 jobs.list 로 끝났는지 확인한다.
        """
        # In/Out 이 있으면 그 범위만 내보내질 수 있으므로 먼저 지운다
        self.execute("markers.clearInOut", {"target": "program"})
        job = (self.execute("file.exportMedia", {"path": path, "format": "wav"}) or {}).get("job")
        deadline = time.monotonic() + timeout
        while job is not None:
            entry = next((j for j in self.execute("jobs.list") or [] if j.get("id") == job), None)
            if entry is None or entry.get("finished"):
                if entry and not (entry.get("result") or {}).get("bytes"):
                    raise ControlError(f"오디오 내보내기 실패: {entry.get('status')}")
                break
            if time.monotonic() > deadline:
                raise ControlError("오디오 내보내기가 너무 오래 걸립니다.")
            time.sleep(0.3)
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            raise ControlError("시퀀스 오디오를 내보내지 못했습니다. 시퀀스가 열려 있는지 확인하세요.")

    def close(self) -> None:
        try:
            self._file.close()
        finally:
            self._sock.close()

    def __enter__(self) -> "Control":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def utf8_console() -> None:
    # Windows 콘솔 기본 인코딩(cp949)으로는 일부 문자를 못 찍는다
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def main(argv: list[str]) -> int:
    utf8_console()
    if not argv:
        print(__doc__)
        return 2
    params = json.loads(argv[1]) if len(argv) > 1 else {}
    try:
        with Control() as c:
            print(json.dumps(c.call(argv[0], params), ensure_ascii=False, indent=2))
    except ControlError as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
