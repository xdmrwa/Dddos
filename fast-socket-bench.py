#!/usr/bin/env python3 """ fast-socket-bench.py A small, single-file educational tool to measure and demonstrate socket/TCP/HTTPS connection performance and simple socket-level tweaks (TCP_NODELAY, socket buffer sizes). Intended for learning and safe benchmarks against servers you own or have permission to test.

Features:

Accepts a domain name and port from the user.

Performs DNS lookup timing, TCP connect timing, TLS handshake timing (if TLS), time-to-first-byte, total download time.

Option to run multiple sequential or parallel fetches to see differences.

Shows throughput and basic timing breakdown.

Sets a few socket options (TCP_NODELAY and adjustable send/recv buffer sizes) to demonstrate their effect.


Usage examples: python3 fast-socket-bench.py example.com 443 --requests 3 --concurrency 2 python3 fast-socket-bench.py example.com 80 --requests 1

Safety & ethics:

Don't use this to attack or stress websites you don't own or have permission to test.

Keep concurrency and requests low (default requests=1, concurrency=1).


Works well on Termux (install Python 3 with pkg install python) and uploadable to GitHub as a single script.

"""

import argparse import asyncio import ssl import socket import time from typing import Optional

async def timed_fetch(domain: str, port: int, use_ssl: bool, path: str, sndbuf: Optional[int], rcvbuf: Optional[int]): # Measure DNS resolution time t0 = time.perf_counter() loop = asyncio.get_running_loop() infos = await loop.getaddrinfo(domain, port, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM) t_dns = time.perf_counter() - t0

# pick first address
family, socktype, proto, cname, addr = infos[0]

t_connect_start = time.perf_counter()
reader = None
writer = None
try:
    ssl_context = None
    if use_ssl:
        ssl_context = ssl.create_default_context()

    # open_connection will perform TCP connect and optionally TLS handshake
    # but we want to be able to tweak socket options before TLS wraps it; so create socket, set options, then connect
    raw_sock = socket.socket(family=family, type=socktype, proto=proto)

    # set non-blocking for asyncio
    raw_sock.setblocking(False)

    # Set socket options to demonstrate their effect
    try:
        # TCP_NODELAY removes Nagle's algorithm (can reduce latency for small writes)
        raw_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except Exception:
        pass
    if sndbuf:
        try:
            raw_sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, sndbuf)
        except Exception:
            pass
    if rcvbuf:
        try:
            raw_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, rcvbuf)
        except Exception:
            pass

    # Use loop.create_connection with the pre-created socket
    transport, protocol = await loop.create_connection(lambda: asyncio.StreamReaderProtocol(asyncio.StreamReader()),
                                                      host=None, port=None, sock=raw_sock, ssl=ssl_context, server_hostname=(domain if use_ssl else None))
    # retrieve reader/writer
    # protocol._stream_reader is an internal detail but works across CPython versions
    reader = protocol._stream_reader
    writer = asyncio.StreamWriter(transport, protocol, reader, loop)

    t_connect = time.perf_counter() - t_connect_start

    # Send a minimal HTTP GET
    req = f"GET {path} HTTP/1.1\r\nHost: {domain}\r\nUser-Agent: fast-socket-bench/1.0\r\nConnection: close\r\nAccept: */*\r\n\r\n"
    t_write_start = time.perf_counter()
    writer.write(req.encode())
    await writer.drain()
    t_write = time.perf_counter() - t_write_start

    # Time to first byte
    t_ttfb_start = time.perf_counter()
    first_chunk = await reader.read(1)
    t_ttfb = time.perf_counter() - t_ttfb_start

    # Read rest
    t_read_start = time.perf_counter()
    body = first_chunk + await reader.read(-1)
    t_read = time.perf_counter() - t_read_start

    total = time.perf_counter() - t0

    # compute sizes and throughput
    size_bytes = len(body)
    throughput_bps = size_bytes / (t_read if t_read > 0 else 1e-9)

    # close
    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass

    return {
        'dns': t_dns,
        'connect': t_connect,
        'write': t_write,
        'ttfb': t_ttfb,
        'read': t_read,
        'total': total,
        'size_bytes': size_bytes,
        'throughput_bps': throughput_bps,
    }

except Exception as e:
    if writer:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
    return {'error': str(e), 'dns': t_dns}

async def run_benchmark(domain: str, port: int, requests: int, concurrency: int, path: str, sndbuf: Optional[int], rcvbuf: Optional[int]): use_ssl = (port == 443)

sem = asyncio.Semaphore(concurrency)

async def worker(i):
    async with sem:
        res = await timed_fetch(domain, port, use_ssl, path, sndbuf, rcvbuf)
        return i, res

tasks = [asyncio.create_task(worker(i)) for i in range(requests)]
results = []
for t in tasks:
    out = await t
    results.append(out)
return results

def human_time(secs: float) -> str: return f"{secs*1000:.2f} ms" if secs < 1 else f"{secs:.3f} s"

def main(): parser = argparse.ArgumentParser(description="Fast socket benchmark (educational).") parser.add_argument('domain', help='Domain name to test (e.g. example.com)') parser.add_argument('port', type=int, help='Port number (e.g. 443 for HTTPS or 80 for HTTP)') parser.add_argument('--path', default='/', help='Path to request (default: /)') parser.add_argument('--requests', type=int, default=1, help='Total number of requests (default 1)') parser.add_argument('--concurrency', type=int, default=1, help='Parallel concurrency (default 1)') parser.add_argument('--sndbuf', type=int, default=None, help='SO_SNDBUF size (bytes)') parser.add_argument('--rcvbuf', type=int, default=None, help='SO_RCVBUF size (bytes)') parser.add_argument('--no-ssl-verify', action='store_true', help='Disable TLS certificate verification (NOT recommended)')

args = parser.parse_args()

if args.requests < 1 or args.concurrency < 1:
    print('requests and concurrency must be >= 1')
    return
if args.concurrency > args.requests:
    args.concurrency = args.requests

if args.no_ssl_verify and args.port == 443:
    # create unverified context globally via environment? simpler: inform user
    print('Warning: --no-ssl-verify requested but this script uses system default verification. Use only for lab testing.')

print(f"Testing {args.domain}:{args.port} path={args.path} requests={args.requests} concurrency={args.concurrency}")
if args.sndbuf:
    print(f"Using SO_SNDBUF={args.sndbuf}")
if args.rcvbuf:
    print(f"Using SO_RCVBUF={args.rcvbuf}")

results = asyncio.run(run_benchmark(args.domain, args.port, args.requests, args.concurrency, args.path, args.sndbuf, args.rcvbuf))

success_count = 0
for i, res in results:
    print('\n--- Request', i, '---')
    if 'error' in res:
        print('Error:', res['error'])
        continue
    success_count += 1
    print(f"DNS: {human_time(res['dns'])}")
    print(f"Connect+TLS: {human_time(res['connect'])}")
    print(f"Write time: {human_time(res['write'])}")
    print(f"TTFB: {human_time(res['ttfb'])}")
    print(f"Read time: {human_time(res['read'])}")
    print(f"Total elapsed: {human_time(res['total'])}")
    print(f"Downloaded bytes: {res['size_bytes']}")
    print(f"Throughput: {res['throughput_bps'] / 1024:.2f} KB/s")

print(f"\nCompleted: {success_count}/{len(results)} successful")
print('Done.')

if name == 'main': main()

