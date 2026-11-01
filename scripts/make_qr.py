"""이 PC의 접속 주소를 찾아 QR 코드 이미지(qr.png)로 저장한다.

실행: python scripts/make_qr.py [포트 | URL]
포트만 주면 핫스팟에 연결한 뒤에 실행해야 핫스팟 쪽 주소가 잡힌다.
URL(https://...)을 주면 그 주소로 QR을 만든다. 터널 모드에서 쓴다.
"""
import socket
import sys
from pathlib import Path

import qrcode


def lan_ip() -> str:
    """외부로 나가는 경로의 IP를 얻는다. 실제로 패킷을 보내지는 않는다."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else "8501"
    url = arg if arg.startswith("http") else f"http://{lan_ip()}:{arg}"
    out = Path(__file__).resolve().parent.parent / "qr.png"
    qrcode.make(url, box_size=12, border=3).save(out)
    print(f"접속 주소: {url}")
    print(f"QR 코드: {out}")


if __name__ == "__main__":
    main()
