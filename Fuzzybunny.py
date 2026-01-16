#!/usr/bin/python3
import argparse
from urllib.parse import urlparse
import requests
import sys
import os
import shutil
import threading
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)
term_width = shutil.get_terminal_size((100, 50)).columns
print_lock = threading.Lock()
session = requests.Session()

# Disable retries
adapter = HTTPAdapter(max_retries=0)
session.mount("http://", adapter)
session.mount("https://", adapter)

# Browser-like headers
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "close"
})

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


def strip_scheme(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc or parsed.path

def fatal(msg, code=1):
    print(f"[!] Error: {msg}", file=sys.stderr)
    sys.exit(code)

def extract_host(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc

def normalize_domain(value: str) -> str:
    value = value.strip()
    parsed = urlparse(value)
    return parsed.netloc or parsed.path

def print_status_line(text):
    with print_lock:
        sys.stdout.write(f"\r{' ' * term_width}\r")
        sys.stdout.write(text)
        sys.stdout.flush()

def validate_url(url):
    parsed = urlparse(url)

    if not parsed.scheme or not parsed.netloc:
        print(f"[!] Invalid URL format: {url}")
        return False
    try:
        response = requests.get(url, timeout=5)
        if response.status_code >= 400:
            tocontinue = input(f"[!] URL responded with error code {response.status_code}. Continue anyway? (y/n): ").lower()
            if tocontinue == 'n':
                exit()
        return True
    except requests.exceptions.RequestException as e:
        print(f"[!] Could not connect to {url} — {e}")
        return False

def read_wordlist(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='replace') as file:
        return [line.strip() for line in file]

def test_url(session, url, output_file, found_urls, excluded_codes, proxies=None, home_page_content=None, home_page_response=None, print_status=True, output_nocode=None):
    try:
        print_status_line(f"Currently fuzzing: {url}")
        #print(url)
        response = requests.get(url, timeout=3, proxies=proxies)
        status_code = response.status_code
        if status_code in excluded_codes:
            return None
        if url not in found_urls and status_code != 404:
            found_urls.add(url)
            # Console output (ALWAYS include status code)
            console_line = f"{url} (Status Code: {status_code})"
            # File output (conditional)
            file_line = url if output_nocode else console_line
            if output_file:
                with open(output_file, "a") as f:
                    f.write(file_line + "\n")
            return url, status_code
    except requests.RequestException:
        pass
    return None


def fuzz_recursive(base_url, directories, extensions, subdomains, output_file, found_urls, excluded_codes, current_depth, max_depth, proxies=None, max_workers=10, origin_base=None, output_nocode=None):
    
    if current_depth > max_depth:
        return

    if origin_base is None:
        origin_base = base_url

    urls_to_fuzz = set()
    if directories:
        for directory in directories:
            if extensions:
                for extension in extensions:
                    urls_to_fuzz.add(f"{base_url.rstrip('/')}/{directory}.{extension}")
            else:
                urls_to_fuzz.add(f"{base_url.rstrip('/')}/{directory}")

    if current_depth == 1 and subdomains:
        host = extract_host(base_url)
        for subdomain in subdomains:
            urls_to_fuzz.add(f"http://{subdomain}.{host}")

    if subdomains and current_depth > 1:
        for subdomain in subdomains:
                urls_to_fuzz.add(f"{subdomain}.{base_url}")

    try:
        home_page_response = session.get(base_url, timeout=3, proxies=proxies)
        home_page_content = home_page_response.text.strip()
    except Exception:
        return

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(test_url, session, url, output_file, found_urls, excluded_codes, proxies, home_page_content, home_page_response, output_nocode=output_nocode): url for url in urls_to_fuzz}
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
                    print(f"[+] {url}")
                    fuzz_recursive(result, directories, extensions, subdomains, output_file, found_urls, excluded_codes, current_depth + 1, max_depth, proxies, max_workers, origin_base)
            except Exception as e:
                print(f"[!] Error processing {url}: {e}")
                continue
    print_status_line("")
    print("Recursive fuzzing complete for this directory.")

    if current_depth == max_depth and base_url != origin_base:
        fuzz_recursive(url, directories, extensions, subdomains, output_file, found_urls, excluded_codes, 1, max_depth, proxies, max_workers, origin_base)

def fuzz_urls(subdomains, directories, extensions, domains, output_file, found_urls, excluded_codes, base_url, max_depth, proxies=None, max_workers=10, output_nocode=None):

    if subdomains != "www" and directories:
        fatal("Cannot fuzz both subdomains and directories.")

    for domain in domains:
        print_status_line("")
        print(f"\n[*] Fuzzing domain: {domain}")

        urls_to_fuzz = set()
        base_domain_url = f"http://{domain}"

        if subdomains != "www":
            for subdomain in subdomains:
                urls_to_fuzz.add(f"http://{subdomain}.{domain}")
        else:
            urls_to_fuzz.add(base_domain_url)

        if directories:
            for directory in directories:
                dir_url = f"{base_domain_url}/{directory}"
                urls_to_fuzz.add(dir_url)

                if extensions:
                    for extension in extensions:
                        urls_to_fuzz.add(f"{dir_url}.{extension}")
        try:
            home_page_response = session.get(base_domain_url, timeout=3, proxies=proxies)
            home_page_content = home_page_response.text.strip()
        except Exception:
            continue

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(test_url, session, url, output_file, found_urls, excluded_codes, proxies, output_nocode=output_nocode): url for url in urls_to_fuzz}
            for future in as_completed(futures):
                result = future.result()
                if not result:
                    continue
                url, status = result
                print_status_line("")
                print(f"[+] {url} (Status Code: {status})")
                fuzz_recursive(url, directories, extensions, subdomains, output_file, found_urls, excluded_codes, 1, max_depth, proxies, max_workers)

    print_status_line("")
    print("Fuzzing complete.")

def main():
    parser = argparse.ArgumentParser(description="Fuzzer for enumeration and fuzzing with extensions and subdomains.")
    parser.add_argument("-u", "--url", help="Base URL for fuzzing. Must start with http:// or https://.")
    parser.add_argument("-s", "--subdomains", help="Path to the subdomains wordlist.")
    parser.add_argument("-d", "--directories", help="Path to the directories wordlist.")
    parser.add_argument("-e", "--extensions", help="Path to the extensions wordlist.")
    parser.add_argument("-w", "--domains", help="Path to the domains wordlist.")
    parser.add_argument("-o", "--output", help="File to save the valid URLs.")
    parser.add_argument("-r", "--recursive", type=int, default=1, help="Depth of recursive search (default: 1).")
    parser.add_argument("-p", "--proxy", help="Proxy URL (http://ip:port or socks5://ip:port).")
    parser.add_argument("-t", "--threads", type=int, default=10, help="Number of concurrent threads.")
    parser.add_argument("-x", "--exclude", nargs="*", default=[], help="Status codes to exclude (e.g., 404 500).")
    parser.add_argument("--output-nocode", action="store_true", help="Output URLs without status codes")
    args = parser.parse_args()

    subdomains = read_wordlist(args.subdomains) if args.subdomains else "www"
    directories = read_wordlist(args.directories) if args.directories else None
    extensions = read_wordlist(args.extensions) if args.extensions else None
    domains = ([normalize_domain(d) for d in read_wordlist(args.domains)] if args.domains else [normalize_domain(args.url)])
    output_file = args.output
    base_url = args.url

    if args.url:
        base_url = args.url.rstrip("/")
        validate_url(base_url)
        base_urls = [base_url]

    elif args.domains:
        base_urls = [f"http://{d}" for d in domains]
        validate_url(base_urls[0])
        base_url = base_urls[0]

    else:
        fatal("You must provide either --url or --domains", 2)

    max_depth = args.recursive
    proxy = args.proxy
    threads = args.threads
    excluded_codes = set(map(int, args.exclude))
    proxies = {"http": proxy, "https": proxy, "socks5": proxy} if proxy else None
    output_nocode = args.output_nocode

    if output_file and os.path.exists(output_file):
        os.remove(output_file)

    found_urls = set()
    fuzz_urls(subdomains, directories, extensions, domains, output_file, found_urls, excluded_codes, base_url, max_depth, proxies, threads, output_nocode=output_nocode)



if __name__ == "__main__":
    main()