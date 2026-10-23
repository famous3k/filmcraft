# 원본(storytold/filmcraft) 업데이트를 받아 내 수정(ko-local 브랜치)을 그 위에 다시 얹고 빌드한다.
#   powershell -ExecutionPolicy Bypass -File local-tools\update.ps1          # 업데이트 + 빌드 + 한글 테스트
#   powershell -ExecutionPolicy Bypass -File local-tools\update.ps1 -Push    # 끝나면 내 GitHub 포크에도 올림
# 충돌이 나면 아무것도 바꾸지 않고 멈춘다. 그때는 LOCAL_PATCHES.md 를 보고 수동으로 다시 적용한다.
param([switch]$Push)

$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
$repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $repo

function Fail($msg) { Write-Host "`n[중단] $msg" -ForegroundColor Red; exit 1 }

if ((git rev-parse --abbrev-ref HEAD) -ne "ko-local") { Fail "ko-local 브랜치에서 실행하세요 (git checkout ko-local)." }
if (git status --porcelain --untracked-files=no) { Fail "커밋하지 않은 수정이 있습니다. 먼저 커밋하거나 되돌리세요." }

Write-Host "원본 업데이트 받는 중..."
git fetch upstream
if ($LASTEXITCODE -ne 0) { Fail "git fetch 실패 (인터넷 연결 확인)." }
$before = git rev-parse HEAD
$new = git rev-list --count HEAD..upstream/main
if ($new -eq "0") { Write-Host "새 업데이트가 없습니다." } else { Write-Host "새 커밋 $new 개" }

git rebase upstream/main
if ($LASTEXITCODE -ne 0) {
    git rebase --abort
    Fail "내 수정과 원본 업데이트가 충돌합니다. 원래 상태로 되돌렸습니다.`n       local-tools\LOCAL_PATCHES.md 의 '다시 적용하는 법'을 따르세요."
}

Write-Host "빌드 중... (몇 분 걸립니다)"
Get-Process filmcraft -ErrorAction SilentlyContinue | ForEach-Object { Fail "FilmCraft 가 실행 중입니다. 닫고 다시 실행하세요." }
cargo build --release -p filmcraft -p filmcraft-cli
if ($LASTEXITCODE -ne 0) { git reset --hard $before; Fail "빌드 실패. 업데이트 전 상태로 되돌렸습니다." }

Write-Host "한글 입력 테스트 중..."
cargo test -p filmcraft-ui-egui --test graphics_handles_ui -- input_method korean
if ($LASTEXITCODE -ne 0) { Fail "한글 입력 테스트 실패. 원본이 바뀌어 수정이 더 이상 맞지 않을 수 있습니다 (LOCAL_PATCHES.md 참고)." }

# 원본 main 을 내 포크의 main 에도 그대로 반영 (내 수정은 ko-local 에만 있다)
git branch -f main upstream/main
if ($Push) {
    git push origin main
    git push --force-with-lease origin ko-local
}
Write-Host "`n완료. local-tools\run-filmcraft.bat 으로 실행하세요." -ForegroundColor Green
