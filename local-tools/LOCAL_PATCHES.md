# 내 수정 기록 (ko-local 브랜치)

원본: <https://github.com/storytold/filmcraft> (`upstream`) · 내 포크: <https://github.com/famous3k/filmcraft> (`origin`)
기준 원본 커밋: `07f2d3a2` (2026-10-22, v0.11.0 이후)

원칙: **원본 코드는 꼭 필요한 곳만 최소로 고친다.** 새 기능(무음 삭제, Whisper 자막)은 원본을 건드리지 않는
`local-tools/` 폴더의 독립 도구로 두고, 앱과는 컨트롤 채널(포트 9876)의 엔진 명령으로만 연결한다.
그래서 원본이 업데이트돼도 충돌 가능성이 있는 곳은 아래 패치 1개뿐이다.

| # | 종류 | 파일 | 원본 수정 |
|---|---|---|---|
| 1 | 버그 수정 | `crates/ui-egui/src/panels/graphics.rs`, `crates/ui-egui/tests/graphics_handles_ui.rs` | 예 (+35줄, 테스트 +31줄) |
| 2 | 새 도구 | `local-tools/silence_cut.py` | 아니오 |
| 3 | 새 도구 | `local-tools/whisper_subs.py` | 아니오 |

---

## 패치 1. 프로그램 모니터에서 문자 도구로 한글 입력이 안 되던 문제

### 증상
- 프로그램 모니터에서 문자 도구(Type tool)로 직접 입력하면 영어는 바로 써지지만 한글은 아무 반응이 없다.
- 텍스트 패널의 입력칸에서는 한글이 잘 써진다.

### 원인
- 프로그램 모니터의 텍스트 편집기는 egui 표준 `TextEdit` 가 아니라 `graphics.rs` 의 자체 편집기(`fn text_edit`)다.
- 이 편집기는 입력기(IME)의 **확정 글자(`ImeEvent::Commit`)만** 받고, **조합 중 글자(`ImeEvent::Preedit`)는 버렸다.**
- 한국어 IME 는 음절마다 조합 상태로 두다가 다음 음절을 시작할 때에야 앞 음절을 확정한다.
  그래서 치는 동안 화면에 아무것도 나오지 않았고, 편집을 끝내면 마지막 음절이 사라졌다.
  (중국어 병음처럼 후보를 고르는 입력기는 확정 위주라 증상이 드러나지 않았다. 원본 #1083 이 Commit 만 고친 이유.)
- Windows 에서는 egui-winit 이 IME 가 처리한 키 입력을 걸러내므로, 조합 중에는 `Text`/`Key` 이벤트도 오지 않는다.
- 폰트 문제는 아니다: 한글 텍스트 레이어는 모니터에 정상으로 그려진다(확인함).

### 수정 내용 (`graphics.rs` 의 `fn text_edit` 와 `fn end_edit`)
egui 표준 `TextEdit` 와 같은 방식으로 처리한다.
1. `ImeEvent::Preedit(text)` 가 오면 조합 중 글자를 레이어 텍스트에 넣고 그 범위를 선택(`anchor..caret`)으로 둔다.
   다음 Preedit 은 그 선택 범위를 바꿔 끼운다. 빈 Preedit 은 조합 중 글자를 지운다.
2. `Commit`(그리고 `Text`/`Paste`)이 오면 조합 중 글자 범위를 먼저 지우고 확정 글자를 넣는다.
3. "조합 중" 상태는 egui 임시 데이터 `Id("gfx-text-edit").with("ime")` 에 `(clip, layer)` 로 저장한다
   (`state.rs` 의 `GfxEdit` 구조체를 바꾸지 않으려고). 조합 중이 아닐 때 오는 빈 Preedit 은 무시한다
   (진짜 선택 영역을 지우지 않도록).
4. IME 를 거치지 않은 키(`Key` 이벤트)가 오면 조합을 끝난 것으로 본다(조합 글자는 그대로 남는다).
5. `end_edit` 에서 조합 상태를 지운다.

### 테스트
`crates/ui-egui/tests/graphics_handles_ui.rs` 의 `korean_composed_by_an_input_method_shows_while_typing`:
Microsoft 한국어 IME 가 `ㅎ ㅏ ㄴ ㄱ ㅡ ㄹ` 입력에 보내는 이벤트 순서를 그대로 흉내 내 `A한글` → 백스페이스 → `A한그` → 확정 → `B` 를 확인한다.
수정 전 코드에서는 `"A"` 만 남아 실패한다(확인함).
```
cargo test -p filmcraft-ui-egui --test graphics_handles_ui -- input_method korean
```

### 다시 적용하는 법 (원본이 바뀌어 `update.ps1` 이 충돌로 멈췄을 때)
1. `git log --oneline upstream/main..ko-local` 로 이 패치 커밋을 찾는다 (제목: `ui: show IME pre-edit text …`).
2. `git checkout -B ko-local upstream/main` 후 `git cherry-pick <커밋>`.
3. 충돌하면 `graphics.rs` 에서 `fn text_edit` 의 이벤트 처리 `match` 를 찾아 위 "수정 내용" 1~5를 다시 넣는다.
   - 원본이 이미 `ImeEvent::Preedit` 를 처리하고 있다면(원본에서 고쳐졌다면) 이 패치는 버리면 된다.
4. 위 테스트가 통과하는지 확인한다.

---

## 도구 2. 무음 구간 자동 삭제 — `local-tools/silence_cut.py`
- 원본 수정 없음. 사용하는 엔진 명령: `file.exportMedia`(WAV), `markers.markIn`, `markers.markOut`,
  `sequence.extract`, `markers.addRangeInOut`, `markers.clearInOut`.
- ffmpeg `silencedetect`(기준 dB, 최소 길이)로 찾은 구간을 앞뒤 여백만큼 줄여, **뒤쪽 구간부터** In/Out 지정 후 Extract.
- 원본에 비슷한 `transcript.removePauses` 가 있지만 이건 받아쓰기의 "단어 사이" 기준이라 음악·효과음 구간에는 맞지 않는다.
- 원본 업데이트로 깨질 수 있는 곳: 위 명령 이름이나 파라미터가 바뀌는 경우뿐.
  확인: `python local-tools\fc_control.py engine.commands`

## 도구 3. Whisper large-v3 자막 생성 — `local-tools/whisper_subs.py`
- 원본 수정 없음. 사용하는 엔진 명령: `file.exportMedia`(WAV), `captions.import`, `markers.clearInOut`.
- faster-whisper(CTranslate2) + NVIDIA GPU(float16), GPU 가 없으면 CPU(int8). 모델은 Hugging Face 에서 한 번 내려받아
  `%USERPROFILE%\.cache\huggingface` 에 둔다.
- 원본 내장 Whisper(`transcript.generate`, `--features whisper`)는 small 까지만 있고 CPU 전용이라,
  large 를 넣으려면 원본 음성 엔진을 고쳐야 해서 독립 도구로 만들었다.
