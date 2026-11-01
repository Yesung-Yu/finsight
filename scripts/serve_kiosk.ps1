# 전시용 실행. 새로고침 버튼은 숨긴다.
#   .\scripts\serve_kiosk.ps1           같은 핫스팟의 휴대폰만 접속 (PC를 핫스팟에 먼저 연결)
#   .\scripts\serve_kiosk.ps1 -Tunnel   Cloudflare 터널로 공개 주소를 만들어 어디서든 접속
#                                       (PC만 인터넷에 연결되면 됨. 주소는 실행할 때마다 바뀜)
param([switch]$Tunnel)

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$env:FINSIGHT_KIOSK = "1"

if (-not $Tunnel) {
    & .\.venv\Scripts\python.exe scripts\make_qr.py
    & .\.venv\Scripts\streamlit.exe run app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true
    return
}

# 설치 직후에는 열려 있던 터미널의 PATH에 없을 수 있어 기본 설치 위치도 확인한다.
$cloudflared = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $cloudflared) {
    $cloudflared = "C:\Program Files (x86)\cloudflared\cloudflared.exe", "C:\Program Files\cloudflared\cloudflared.exe" |
        Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $cloudflared) {
    Write-Error "cloudflared가 없습니다. winget install --id Cloudflare.cloudflared 로 설치한 뒤 새 터미널에서 다시 실행하세요."
    return
}

$log = Join-Path $env:TEMP "finsight-tunnel.log"
Remove-Item $log -ErrorAction SilentlyContinue
$cfProc = $null
try {
    # 터널은 이 PC에서만 접속하는 localhost로 연결하므로 서버는 외부에 열지 않는다.
    $cfProc = Start-Process $cloudflared -ArgumentList "tunnel", "--url", "http://localhost:8501" `
        -RedirectStandardError $log -WindowStyle Hidden -PassThru

    $url = $null
    for ($i = 0; $i -lt 30 -and -not $url; $i++) {
        Start-Sleep 1
        if (Test-Path $log) {
            $m = Select-String -Path $log -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" | Select-Object -First 1
            if ($m) { $url = $m.Matches[0].Value }
        }
    }
    if (-not $url) { Write-Error "터널 주소를 얻지 못했습니다. 인터넷 연결을 확인하세요. 로그: $log"; return }

    & .\.venv\Scripts\python.exe scripts\make_qr.py $url
    & .\.venv\Scripts\streamlit.exe run app.py --server.address localhost --server.port 8501 --server.headless true
}
finally {
    if ($cfProc -and -not $cfProc.HasExited) { Stop-Process -Id $cfProc.Id -Force }
}
