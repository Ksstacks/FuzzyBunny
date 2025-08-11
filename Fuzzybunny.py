#!/usr/bin/python3
import argparse
from urllib.parse import urlparse
import requests
import sys
import os
import subprocess
from colorama import Fore, Style, init
from concurrent.futures import ThreadPoolExecutor, as_completed
import shutil
import threading

# Initialize colorama
init(autoreset=True)
term_width = shutil.get_terminal_size((100, 50)).columns
print_lock = threading.Lock()
session = requests.Session()

def print_status_line(text):
    with print_lock:
        sys.stdout.write(f"\r{' ' * term_width}\r")
        sys.stdout.write(text)
        sys.stdout.flush()

def validate_url(url):
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        sys.exit(f"[!] Invalid URL format: {url}")

    try:
        response = requests.get(url, timeout=5)
        if response.status_code >= 400:
            sys.exit(f"[!] URL responded with error code {response.status_code}")
    except requests.exceptions.RequestException as e:
        sys.exit(f"[!] Could not connect to {url} — {e}")

banner = """
  ░        ░░  ░░░░  ░░        ░░        ░░  ░░░░  ░░       ░░░  ░░░░  ░░   ░░░  ░░   ░░░  ░░  ░░░░  ░
  ▒  ▒▒▒▒▒▒▒▒  ▒▒▒▒  ▒▒▒▒▒▒▒  ▒▒▒▒▒▒▒▒  ▒▒▒▒  ▒▒  ▒▒▒  ▒▒▒▒  ▒▒  ▒▒▒▒  ▒▒    ▒▒  ▒▒    ▒▒  ▒▒▒  ▒▒  ▒▒
  ▓      ▓▓▓▓  ▓▓▓▓  ▓▓▓▓▓  ▓▓▓▓▓▓▓▓  ▓▓▓▓▓▓▓    ▓▓▓▓       ▓▓▓  ▓▓▓▓  ▓▓  ▓  ▓  ▓▓  ▓  ▓  ▓▓▓▓    ▓▓▓
  █  ████████  ████  ███  ████████  ██████████  █████  ████  ██  ████  ██  ██    ██  ██    █████  ████
  █  █████████      ███        ██        █████  █████       ████      ███  ███   ██  ███   █████  ████

  + by kstacks
  + telegram @ksstacks
"""
print(banner)

def read_wordlist(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='replace') as file:
        return [line.strip() for line in file]

def test_url(session, url, output_file, found_urls, excluded_codes, proxies=None, home_page_content=None, home_page_response=None):
    try:
        print_status_line(f"Currently fuzzing: {url}")
        response = requests.get(url, timeout=3, proxies=proxies)
        status_code = response.status_code
        if status_code in excluded_codes:
            return None
        if status_code == 200 and url not in found_urls:
            found_urls.add(url)
            if output_file:
                with open(output_file, "a") as f:
                    f.write(f"{url} (Status Code: {status_code})\n")
            return f"{url} (Status Code: {status_code})"
        elif status_code != 404 and url not in found_urls:
            found_urls.add(url)
            return f"{url} (Status Code: {status_code})"
    except requests.RequestException:
        pass
    return None

def fuzz_recursive(base_url, directories, extensions, subdomains, output_file, found_urls, excluded_codes, current_depth, max_depth, proxies=None, max_workers=10, origin_base=None):
    if current_depth > max_depth:
        return

    if origin_base is None:
        origin_base = base_url

    urls_to_fuzz = []
    if directories:
        for directory in directories:
            if extensions:
                for extension in extensions:
                    urls_to_fuzz.append(f"{base_url.rstrip('/')}/{directory}.{extension}")
            else:
                urls_to_fuzz.append(f"{base_url.rstrip('/')}/{directory}")

    try:
        home_page_response = session.get(base_url, timeout=3, proxies=proxies)
        home_page_content = home_page_response.text.strip()
    except Exception:
        return

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(test_url, session, url, output_file, found_urls, excluded_codes, proxies, home_page_content, home_page_response): url for url in urls_to_fuzz}
        for future in as_completed(futures):
            url = futures[future]
            try:
                if home_page_response == home_page_content:
                    print_status_line("")
                    print(f"[!] Skipping {url} — redirects to home page")
                    continue
                result = future.result()
                if result:
                    print_status_line("")
                    print(f"[+] {result}")
                    fuzz_recursive(url, directories, extensions, subdomains, output_file, found_urls, excluded_codes, current_depth + 1, max_depth, proxies, max_workers, origin_base)
            except Exception as e:
                print(f"[!] Error processing {url}: {e}")
                continue
    print_status_line("")
    print("Recursive fuzzing complete for this directory.")

    if current_depth == max_depth and base_url != origin_base:
        fuzz_recursive(origin_base, directories, extensions, subdomains, output_file, found_urls, excluded_codes, 1, max_depth, proxies, max_workers, origin_base)

def fuzz_urls(subdomains, directories, extensions, domains, output_file, found_urls, excluded_codes, base_url, max_depth, proxies=None, max_workers=10):
    urls_to_fuzz = set()

    for domain in domains:
        for subdomain in subdomains:
            base = f"{subdomain}.{domain}" if subdomain != "www" else domain
            if directories:
                for directory in directories:
                    if extensions:
                        for extension in extensions:
                            urls_to_fuzz.add(f"http://{base}/{directory}.{extension}")
                    urls_to_fuzz.add(f"http://{base}/{directory}")
            urls_to_fuzz.add(f"http://{base}")

    try:
        home_page_response = session.get(base_url, timeout=3, proxies=proxies)
        home_page_content = home_page_response.text.strip()
    except Exception:
        return

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(test_url, session, url, output_file, found_urls, excluded_codes, proxies): url for url in urls_to_fuzz}
        for future in as_completed(futures):
            result = future.result()
            if home_page_response == home_page_content:
                print_status_line("")
                print(f"[!] Skipping {url} — redirects to home page")
                continue            
            elif result:
                print_status_line("")
                print(f"[+] {result}")
                fuzz_recursive(result.split()[0], directories, extensions, subdomains, output_file, found_urls, excluded_codes, 1, max_depth, proxies, max_workers)
    print_status_line("")
    print("Fuzzing complete.")

def main():
    parser = argparse.ArgumentParser(description="Fuzzer for enumeration and fuzzing with extensions and subdomains.")
    parser.add_argument("-u", "--url", required=True, help="Base URL for fuzzing. Must start with http:// or https://.")
    parser.add_argument("-s", "--subdomains", help="Path to the subdomains wordlist.")
    parser.add_argument("-d", "--directories", help="Path to the directories wordlist.")
    parser.add_argument("-e", "--extensions", help="Path to the extensions wordlist.")
    parser.add_argument("-w", "--domains", help="Path to the domains wordlist.")
    parser.add_argument("-o", "--output", help="File to save the valid URLs.")
    parser.add_argument("-r", "--recursive", type=int, default=1, help="Depth of recursive search (default: 1).")
    parser.add_argument("-p", "--proxy", help="Proxy URL (http://ip:port or socks5://ip:port).")
    parser.add_argument("-t", "--threads", type=int, default=10, help="Number of concurrent threads.")
    parser.add_argument("-x", "--exclude", nargs="*", default=[], help="Status codes to exclude (e.g., 404 500).")
    args = parser.parse_args()

    if not args.url.startswith(("http://", "https://")):
        parser.error("URL must start with http:// or https://")
    if args.recursive and int(args.recursive) > 1 and args.subdomains is not None:
        sys.exit("[!] Recursive searching with subdomains is not supported.")

    validate_url(args.url)

    subdomains = read_wordlist(args.subdomains) if args.subdomains else ["www"]
    directories = read_wordlist(args.directories) if args.directories else None
    extensions = read_wordlist(args.extensions) if args.extensions else None
    domains = read_wordlist(args.domains) if args.domains else [args.url.replace("http://", "").replace("https://", "").rstrip("/")]
    output_file = args.output
    base_url = args.url
    max_depth = args.recursive
    proxy = args.proxy
    threads = args.threads
    excluded_codes = set(map(int, args.exclude))
    proxies = {"http": proxy, "https": proxy, "socks5": proxy} if proxy else None

    if output_file and os.path.exists(output_file):
        os.remove(output_file)

    found_urls = set()
    fuzz_urls(subdomains, directories, extensions, domains, output_file, found_urls, excluded_codes, base_url, max_depth, proxies, threads)

if __name__ == "__main__":
    main()
