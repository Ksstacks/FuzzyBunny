import argparse
import requests
import os
import threading
from colorama import Fore, Style
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

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

def read_wordlist(file_path):
    with open(file_path, 'r') as file:
        return [line.strip() for line in file.readlines()]

def test_url(url, output_file, found_urls, proxies=None, semaphore=None):
    try:
        response = requests.get(url, timeout=3, proxies=proxies)
        status_code = response.status_code
        if status_code == 200 and url not in found_urls:
            print(f"Valid URL found: {url} (Status Code: " + Fore.GREEN + f"{status_code}" + Fore.WHITE + ")")
            found_urls.add(url)
            if output_file:
                with open(output_file, 'a') as f:
                    f.write(f"{url} (Status Code: {status_code})\n")
            return True
        elif status_code != 404 and url not in found_urls:
            print(f"URL: {url} (Status Code: " + Fore.BLUE + f"{status_code}" + Fore.WHITE + ")")
            found_urls.add(url)
    except requests.RequestException:
        pass
    finally:
        if semaphore:
            semaphore.release()
    return False

def fuzz_urls(subdomains, directories, extensions, domains, output_file, found_urls, base_url=None, depth=1, max_depth=1, proxies=None, max_workers=10):
    semaphore = threading.Semaphore(max_workers)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for domain in domains:
            for subdomain in subdomains:
                for directory in directories:
                    for extension in extensions:
                        # Construct URLs
                        if base_url:
                            url = urljoin(f"http://{subdomain}.{base_url}/", f"{directory}/index.{extension}")
                        else:
                            url = urljoin(f"http://{subdomain}.{domain}/", f"{directory}/index.{extension}")

                        semaphore.acquire()
                        futures.append(executor.submit(test_url, url, output_file, found_urls, proxies, semaphore))

                        # Additional test without www
                        if subdomain == 'www':
                            if base_url:
                                url = urljoin(f"http://{base_url}/", f"{directory}/index.{extension}")
                            else:
                                url = urljoin(f"http://{domain}/", f"{directory}/index.{extension}")
                            semaphore.acquire()
                            futures.append(executor.submit(test_url, url, output_file, found_urls, proxies, semaphore))

                        # Additional test for just subdomain
                        if base_url:
                            url = urljoin(f"http://{subdomain}.{base_url}/", f"{directory}")
                        else:
                            url = urljoin(f"http://{subdomain}.{domain}/", f"{directory}")
                        semaphore.acquire()
                        futures.append(executor.submit(test_url, url, output_file, found_urls, proxies, semaphore))

        for future in as_completed(futures):
            result = future.result()
            if result and depth < max_depth:
                new_base_url = result.rstrip('/')
                fuzz_urls(subdomains, directories, extensions, [new_base_url], output_file, found_urls, new_base_url, depth + 1, max_depth, proxies, max_workers)

def main():
    parser = argparse.ArgumentParser(
        description="Fuzzer for enumeration and fuzzing with extensions and subdomains.\n\n"
                    "Examples:\n"
                    "  python fuzzer.py -u example.com -s subdomains.txt\n"
                    "  python fuzzer.py --url example.com --directories directories.txt",
        formatter_class=argparse.RawTextHelpFormatter
    )

    # Add arguments
    parser.add_argument('-u', '--url', required=True, help='Base URL to fuzz.')
    parser.add_argument('-s', '--subdomains', help='Path to the subdomains wordlist.')
    parser.add_argument('-d', '--directories', help='Path to the directories wordlist.')
    parser.add_argument('-e', '--extensions', help='Path to the extensions wordlist.')
    parser.add_argument('-w', '--domains', help='Path to the domains wordlist.')
    parser.add_argument('-o', '--output', help='File to save the valid URLs.')
    parser.add_argument('-r', '--recursive', type=int, default=1, help='Depth of recursive search (default: 1).')
    parser.add_argument('-p', '--proxy', help='Proxy URL (format: http://proxy_ip:proxy_port or socks5://proxy_ip:proxy_port).')
    parser.add_argument('-t', '--threads', type=int, default=10, help='Number of concurrent threads (default: 10).')

    args = parser.parse_args()

    if not args.subdomains and not args.directories:
        parser.error("Either --subdomains or --directories must be specified.")

    subdomains = read_wordlist(args.subdomains) if args.subdomains else ['www']
    directories = read_wordlist(args.directories) if args.directories else ['']
    extensions = read_wordlist(args.extensions) if args.extensions else ['']
    domains = read_wordlist(args.domains) if args.domains else [args.url]
    output_file = args.output
    base_url = args.url
    recursive_depth = args.recursive
    proxy = args.proxy
    threads = args.threads

    proxies = {'http': proxy, 'https': proxy} if proxy else None

    if output_file and os.path.exists(output_file):
        os.remove(output_file)

    found_urls = set()
    fuzz_urls(subdomains, directories, extensions, domains, output_file, found_urls, base_url, 1, recursive_depth, proxies, threads)

if __name__ == "__main__":
    main()
