#!/usr/bin/python3
import argparse
import requests
import sys,os
import subprocess
from colorama import Fore, Style, init
from concurrent.futures import ThreadPoolExecutor, as_completed
import shutil

# Initialize colorama
init(autoreset=True)
term_width = shutil.get_terminal_size((80, 20)).columns

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

def test_url(url, output_file, found_urls, excluded_codes, proxies=None, isvalid=False):
    try:
        response = requests.get(url, timeout=3, proxies=proxies)
        status_code = response.status_code
        if status_code in excluded_codes:
            return None
        if status_code == 200 and url not in found_urls:
            isvalid = True
            found_urls.add(url)
            result = f" (Status Code: {status_code})"
            if output_file:
                with open(output_file, "a") as f:
                    f.write(f"{url} (Status Code: {status_code})\n")
            return result
        elif status_code != 404 and url not in found_urls:
            isvalid = True
            found_urls.add(url)
            return f" (Status Code: {status_code})"
    except requests.RequestException:
        pass
    return None

def construct_url(subdomain, domain, directory=None, extension=None):
    # Construct the full URL based on provided directory and extension
    if directory and extension:
        return f"{domain}/{directory}.{extension}"
    elif directory:
        return f"{domain}/{directory}"
    return domain

def fuzz_recursive(base_url, directories, extensions, subdomains, output_file, found_urls, excluded_codes, current_depth, max_depth, proxies=None, max_workers=10):
    if current_depth > max_depth:
        print(f"Reached maximum recursive depth: {max_depth}")
        return

    urls_to_fuzz = []

    if directories:
        for directory in directories:
            if extensions:
                for extension in extensions:
                    url = f"{base_url}/{directory}.{extension}"
                    urls_to_fuzz.append(url)
            else:
                url = f"{base_url}/{directory}"
                urls_to_fuzz.append(url)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        home_page_content = subprocess.run(f"curl -s {base_url}").stdout
        futures = {executor.submit(test_url, url, output_file, found_urls, excluded_codes, proxies): url for url in urls_to_fuzz}
        for future in as_completed(futures):
            url = futures[future]
            curled = subprocess.run(f"curl -s {url}").stdout
            if curled.strip() == home_page_content.strip() and url != futures:
                print(f"Skipping URL {url} as it redirects to the home page.")
                continue
            if result:
               print(f"{result}")

def print_status_line(text):
    clear_line = " " * term_width
    sys.stdout.write(f"\r{clear_line}\r")
    sys.stdout.write(text)
    sys.stdout.flush()

def fuzz_urls(subdomains, directories, extensions, domains, output_file, found_urls, excluded_codes, base_url, max_depth, proxies=None, max_workers=10):
    urls_to_fuzz = []
    if base_url.strip("https://") or base_url.strip("http://") and base_url.find("/") == None:
        base_url.endswith("/")
    if directories:
        for domain in domains:
            for subdomain in subdomains:
                for directory in directories:
                    if extensions:
                        for extension in extensions:
                            url = construct_url(subdomain, domain, directory, extension)
                            urls_to_fuzz.append(url)
                            if subdomain == "www":
                                url = construct_url(None, domain, directory, extension)
                                urls_to_fuzz.append(url)
                            url = construct_url(subdomain, domain, directory)
                            urls_to_fuzz.append(url)
                    else:
                        url = construct_url(subdomain, domain, directory)
                        urls_to_fuzz.append(url)
                        if subdomain == "www":
                            url = construct_url(None, domain, directory)
                            urls_to_fuzz.append(url)
                        url = construct_url(subdomain, domain)
                        urls_to_fuzz.append(url)
    elif subdomains:
        for domain in domains:
            for subdomain in subdomains:
                if extensions:
                    for extension in extensions:
                        url = construct_url(subdomain, domain, None, extension)
                        urls_to_fuzz.append(url)
                        if subdomain == "www":
                            url = construct_url(None, domain, None, extension)
                            urls_to_fuzz.append(url)
                        url = construct_url(subdomain, domain)
                        urls_to_fuzz.append(url)
                else:
                    url = construct_url(subdomain, domain)
                    urls_to_fuzz.append(url)
                    if subdomain == "www":
                        url = construct_url(None, domain)
                        urls_to_fuzz.append(url)
    elif extensions:
        for domain in domains:
            for extension in extensions:
                url = construct_url(None, domain, None, extension)
                urls_to_fuzz.append(url)
                if domain == "www":
                    url = construct_url(None, extension)
                    urls_to_fuzz.append(url)
    else:
        for domain in domains:
            url = construct_url(None, domain)
            urls_to_fuzz.append(url)

    home_url = base_url.rstrip("/")
    found_directories = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(test_url, url, output_file, found_urls, excluded_codes, proxies): url for url in urls_to_fuzz}
        for future in as_completed(futures):
            url = futures[future]
            print_status_line(f"\r{url}")
            sys.stdout.flush()
            result = future.result()
            if result:
                print(f"{result}")
    for directory in found_directories:
        fuzz_recursive(directory, directories, extensions, subdomains, output_file, found_urls, excluded_codes, 1, max_depth, proxies, max_workers)

def main():
    parser = argparse.ArgumentParser(
        description="Fuzzer for enumeration and fuzzing with extensions and subdomains.",
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-u", "--url", required=True, help="Base URL for fuzzing. Must start with http:// or https://.")
    parser.add_argument("-s", "--subdomains", help="Path to the subdomains wordlist.")
    parser.add_argument("-d", "--directories", help="Path to the directories wordlist.")
    parser.add_argument("-e", "--extensions", help="Path to the extensions wordlist.")
    parser.add_argument("-w", "--domains", help="Path to the domains wordlist.")
    parser.add_argument("-o", "--output", help="File to save the valid URLs.")
    parser.add_argument("-r", "--recursive", type=int, default=1, help="Depth of recursive search (default: 1).")
    parser.add_argument("-p", "--proxy", help="Proxy URL (format: http://proxy_ip:proxy_port or socks5://proxy_ip:proxy_port).")
    parser.add_argument("-t", "--threads", type=int, default=10, help="Number of concurrent threads (default: 10).")
    parser.add_argument("-x", "--exclude", nargs="*", default=[], help="Status codes to exclude from results (e.g., 404 500).")
    args = parser.parse_args()

    if not args.url.startswith(("https://", "https://")):
        parser.error("Must start with http:// or https://")
        exit()
    subdomains = read_wordlist(args.subdomains) if args.subdomains else ["www"]
    directories = read_wordlist(args.directories) if args.directories else None
    extensions = read_wordlist(args.extensions) if args.extensions else None
    domains = read_wordlist(args.domains) if args.domains else [args.url]
    output_file = args.output
    base_url = args.url.rstrip("/")
    max_depth = args.recursive
    proxy = args.proxy
    threads = args.threads
    excluded_codes = set(map(int, args.exclude)) if args.exclude else set()
    proxies = {"http": proxy, "https": proxy, "socks5": proxy} if proxy else None
    if output_file and os.path.exists(output_file):
        os.remove(output_file)

    found_urls = set()

    fuzz_urls(subdomains, directories, extensions, domains, output_file, found_urls, excluded_codes, base_url, max_depth, proxies, threads)
    if output_file and os.path.exists(output_file):
        os.remove(output_file)

if __name__ == "__main__":
    main()
