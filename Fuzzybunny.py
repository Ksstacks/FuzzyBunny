#!/usr/bin/python3
import argparse
import requests
import sys
import os
from colorama import init
from concurrent.futures import ThreadPoolExecutor, as_completed
import shutil

init(autoreset=True)
term_width = shutil.get_terminal_size((100, 50)).columns

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

def print_status_line(text):
    clear_line = " " * term_width
    sys.stdout.write(f"\r{clear_line}\r")
    sys.stdout.write(text)
    sys.stdout.flush()

def read_wordlist(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='replace') as file:
        return [line.strip() for line in file if line.strip()]

def test_url(session, url, output_file, found_urls, excluded_codes, proxies=None, home_page_content=None):
    try:
        response = session.get(url, timeout=3, proxies=proxies)
        status_code = response.status_code
        if status_code in excluded_codes:
            return None
        if home_page_content is not None and response.text.strip() == home_page_content:
            return None
        if url not in found_urls:
            found_urls.add(url)
            if output_file:
                with open(output_file, "a") as f:
                    f.write(f"{url} (Status Code: {status_code})\n")
            return f"{url} (Status Code: {status_code})"
    except requests.RequestException:
        pass
    return None

def fuzz_recursive(base_url, directories, extensions, subdomains, output_file, found_urls, excluded_codes, current_depth, max_depth, proxies=None, max_workers=10):
    if current_depth > max_depth:
        return

    urls_to_fuzz = []
    if directories:
        for directory in directories:
            if extensions:
                for extension in extensions:
                    urls_to_fuzz.append(f"{base_url.rstrip('/')}/{directory}.{extension}")
            else:
                urls_to_fuzz.append(f"{base_url.rstrip('/')}/{directory}")

    session = requests.Session()

    try:
        home_page_response = session.get(base_url, timeout=3, proxies=proxies)
        home_page_content = home_page_response.text.strip()
    except Exception:
        return

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(test_url, session, url, output_file, found_urls, excluded_codes, proxies, home_page_content): url for url in urls_to_fuzz}
        for future in as_completed(futures):
            url = futures[future]
            print_status_line(f"Currently fuzzing: {url}")
            try:
                result = future.result()
                if result:
                    print_status_line("")  # Clear status line before printing found URL
                    print(f"[+] {result}")
                    fuzz_recursive(url, directories, extensions, subdomains, output_file, found_urls, excluded_codes, current_depth + 1, max_depth, proxies, max_workers)
            except Exception:
                continue
    print_status_line("Recursive fuzzing complete.")

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

    session = requests.Session()

    try:
        home_page_response = session.get(base_url, timeout=3, proxies=proxies)
        home_page_content = home_page_response.text.strip()
    except Exception:
        home_page_content = None

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(test_url, session, url, output_file, found_urls, excluded_codes, proxies, home_page_content): url for url in urls_to_fuzz}
        for future in as_completed(futures):
            url = futures[future]
            print_status_line(f"Currently fuzzing: {url}")
            result = future.result()
            if result:
                print_status_line("")  # Clear status line before printing found URL
                print(f"[+] {result}")
                fuzz_recursive(result.split()[0], directories, extensions, subdomains, output_file, found_urls, excluded_codes, 1, max_depth, proxies, max_workers)
    print_status_line("Fuzzing complete.")

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

    subdomains = read_wordlist(args.subdomains) if args.subdomains else ["www"]
    directories = read_wordlist(args.directories) if args.directories else None
    extensions = read_wordlist(args.extensions) if args.extensions else None
    domains = read_wordlist(args.domains) if args.domains else [args.url.replace("http://", "").replace("https://", "").rstrip("/")]
    output_file = args.output
    base_url = args.url
    max_depth = args.recursive
    proxy = args.proxy
    threads = args.threads
    excluded_codes = set(map(int, args.exclude)) if args.exclude else set()
    proxies = {"http": proxy, "https": proxy} if proxy else None

    if output_file and os.path.exists(output_file):
        os.remove(output_file)

    found_urls = set()
    fuzz_urls(subdomains, directories, extensions, domains, output_file, found_urls, excluded_codes, base_url, max_depth, proxies, threads)

if __name__ == "__main__":
    main()
