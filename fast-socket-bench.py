#!/data/data/com.termux/files/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Educational Packet Transfer Tool
For learning socket programming and network communication
"""

import socket
import sys
import time
import ssl
from urllib.parse import urlparse

def create_socket_connection(domain, port, use_https=False):
    """
    Create a socket connection to the specified domain and port
    """
    try:
        # Resolve domain to IP
        print(f"[+] Resolving {domain}...")
        ip = socket.gethostbyname(domain)
        print(f"[+] IP Address: {ip}")
        
        # Create socket
        if use_https or port == 443:
            # Create SSL context for HTTPS
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            # Create regular socket first
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            
            # Wrap with SSL
            s = context.wrap_socket(sock, server_hostname=domain)
        else:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
        
        # Connect to server
        print(f"[+] Connecting to {domain}:{port}...")
        start_time = time.time()
        s.connect((ip, port))
        connect_time = time.time() - start_time
        print(f"[+] Connected! Connection time: {connect_time:.3f}s")
        
        return s, connect_time
        
    except socket.gaierror:
        print(f"[-] Error: Could not resolve domain {domain}")
        return None, 0
    except socket.timeout:
        print(f"[-] Error: Connection timeout to {domain}:{port}")
        return None, 0
    except Exception as e:
        print(f"[-] Error: {str(e)}")
        return None, 0

def send_http_request(sock, domain, path="/"):
    """
    Send a simple HTTP GET request
    """
    try:
        request = f"GET {path} HTTP/1.1\r\n"
        request += f"Host: {domain}\r\n"
        request += "User-Agent: Educational-Packet-Tool\r\n"
        request += "Connection: close\r\n\r\n"
        
        print("[+] Sending HTTP request...")
        sock.send(request.encode())
        return True
    except Exception as e:
        print(f"[-] Error sending request: {str(e)}")
        return False

def receive_response(sock):
    """
    Receive and display server response
    """
    try:
        print("[+] Receiving response...")
        response = b""
        start_time = time.time()
        
        while True:
            try:
                data = sock.recv(4096)
                if not data:
                    break
                response += data
            except socket.timeout:
                break
        
        total_time = time.time() - start_time
        response_size = len(response)
        
        print(f"[+] Response received!")
        print(f"[+] Time taken: {total_time:.3f}s")
        print(f"[+] Data size: {response_size} bytes")
        
        # Show first 500 characters of response
        response_text = response.decode('utf-8', errors='ignore')
        print("\n[+] Response preview:")
        print(response_text[:500] + ("..." if len(response_text) > 500 else ""))
        
        return response, total_time
    except Exception as e:
        print(f"[-] Error receiving response: {str(e)}")
        return None, 0

def main():
    print("=== Educational Packet Transfer Tool ===")
    print("For learning socket programming concepts\n")
    
    # Get user input
    domain = input("Enter domain (e.g., google.com): ").strip()
    if not domain:
        print("[-] Domain cannot be empty!")
        return
    
    # Default to HTTPS if no port specified for common sites
    default_port = 443 if not domain.startswith("http") else None
    port_input = input(f"Enter port (default {default_port or 80}): ").strip()
    
    try:
        port = int(port_input) if port_input else (default_port or 80)
    except ValueError:
        print("[-] Invalid port number!")
        return
    
    # Determine if HTTPS should be used
    use_https = port == 443 or input("Use HTTPS? (y/n): ").lower().startswith('y')
    
    # Create connection
    sock, connect_time = create_socket_connection(domain, port, use_https)
    if not sock:
        return
    
    try:
        # Send HTTP request if it's a web server
        if port in [80, 443, 8080]:
            path = input("Enter path (default /): ").strip() or "/"
            if send_http_request(sock, domain, path):
                response, response_time = receive_response(sock)
                if response:
                    print(f"\n[+] Total time: {connect_time + response_time:.3f}s")
        else:
            # For non-HTTP ports, just test connection
            print("[+] Connection successful!")
            print(f"[+] Time taken: {connect_time:.3f}s")
            
    finally:
        sock.close()
        print("\n[+] Connection closed")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[+] Program interrupted by user")
    except Exception as e:
        print(f"\n[-] Unexpected error: {str(e)}")
