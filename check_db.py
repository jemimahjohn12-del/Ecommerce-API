import socket
import time

from sqlalchemy.engine import make_url

from app.core.config import settings

url = make_url(settings.database_url)
host = url.host
port = url.port or 5432

print("host:", host)
print("port:", port)
print("options:", dict(url.query))

try:
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
except Exception as e:
    print("DNS lookup FAILED:", e)
    raise SystemExit

for info in addresses:
    family = "IPv6" if info[0] == socket.AF_INET6 else "IPv4"
    ip = info[4][0]
    start = time.time()
    try:
        s = socket.create_connection(info[4][:2], timeout=8)
        s.close()
        print(family, ip, "-> OK in", round(time.time() - start, 2), "seconds")
    except Exception as e:
        print(family, ip, "-> FAILED:", e)