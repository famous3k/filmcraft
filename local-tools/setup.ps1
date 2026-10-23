# local-tools 준비: Whisper 자막 도구용 Python 가상환경(.venv)을 만든다. 한 번만 실행하면 된다.
#   powershell -ExecutionPolicy Bypass -File local-tools\setup.ps1
# 무음 삭제 도구(silence_cut.py)는 표준 라이브러리만 쓰므로 이 단계가 필요 없다 (ffmpeg만 필요).
# ($ErrorActionPreference = "Stop" 은 쓰지 않는다: PowerShell 5.1 은 pip 의 경고 출력도 오류로 보고 멈춘다)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv = Join-Path $here ".venv"
if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) {
    python -m venv $venv
}
$py = Join-Path $venv "Scripts\python.exe"
& $py -m pip install --upgrade pip
# faster-whisper(CTranslate2) + NVIDIA GPU에서 돌리기 위한 cuBLAS / cuDNN 런타임
& $py -m pip install faster-whisper nvidia-cublas-cu12 "nvidia-cudnn-cu12>=9,<10"
if ($LASTEXITCODE -ne 0) { Write-Host "pip 설치 실패 (위 메시지 확인)"; exit 1 }
& $py -c "import faster_whisper, ctranslate2; print('faster-whisper', faster_whisper.__version__, '| CUDA 장치 수:', ctranslate2.get_cuda_device_count())"
