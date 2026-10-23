# local-tools — 내 FilmCraft 도구 모음

모두 내 PC 에서만 돌아가고 AI 토큰이 들지 않는다. 원본 코드에 무엇을 왜 바꿨는지는 [LOCAL_PATCHES.md](LOCAL_PATCHES.md).

## 처음 한 번
```
powershell -ExecutionPolicy Bypass -File local-tools\setup.ps1
```
Whisper 도구용 Python 환경(`.venv`)을 만든다. 무음 삭제 도구는 이 단계 없이도 된다(ffmpeg 만 필요).

## 매번
1. **`run-filmcraft.bat`** 으로 FilmCraft 를 실행한다 (도구가 앱에 명령을 보낼 수 있게 포트 9876 을 연다).
2. 시퀀스를 열어 둔다.
3. 필요한 도구를 더블클릭한다.

| 파일 | 하는 일 |
|---|---|
| `silence-cut.bat` | 무음 구간 자동 삭제. 실행하면 기준 dB / 최소 무음 길이 / 남길 여백을 물어보고, 찾은 구간 목록을 보여준 뒤 `y` 를 누르면 리플 삭제한다. |
| `whisper-subs.bat` | 현재 시퀀스를 Whisper large-v3 로 받아써 새 자막 트랙으로 가져온다. 수정은 텍스트 패널 ▸ 자막. |
| `update.ps1` | 원본 업데이트를 받아 내 수정을 다시 얹고 빌드한다. 충돌하면 아무것도 바꾸지 않고 멈춘다. |

### 무음 삭제 옵션 (`silence-cut.bat --help`)
- `--db -35` : 이보다 작은 소리를 무음으로 본다. 배경 소음이 있으면 -30 쪽으로, 조용한 녹음이면 -40 쪽으로.
- `--min 0.5` : 이 길이(초) 이상 이어진 무음만 지운다.
- `--pad 0.15` : 지울 구간 앞뒤로 남길 여백(초). 말이 잘리면 늘린다.
- `--dry-run` : 찾기만 하고 지우지 않음 · `--markers` : 지우지 않고 범위 마커만 표시
- 되돌리기: 구간 하나가 Ctrl+Z 한 번. 실행 전에 프로젝트를 저장해 두자.

### Whisper 옵션 (`whisper-subs.bat --help`)
- `--model large-v3-turbo` : 더 빠르지만 조금 덜 정확.
- `--max-chars 18 --lines 2` : 자막 한 줄 글자 수와 줄 수.
- `--media 파일.mp4 --no-import --out 파일.srt` : 앱 없이 파일에서 SRT 만 만들기.
- 시간: RTX 3070 Ti 기준 대략 영상 길이의 몇 분의 1. CPU 로는 훨씬 느리다.

## 원본 업데이트 받기
```
powershell -ExecutionPolicy Bypass -File local-tools\update.ps1
```
`-Push` 를 붙이면 끝난 뒤 내 GitHub 포크에도 올린다. 충돌로 멈추면 LOCAL_PATCHES.md 의 "다시 적용하는 법".
