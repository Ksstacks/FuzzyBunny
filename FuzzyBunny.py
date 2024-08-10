import argparse
import requests
import os
from colorama import Fore, Style, init
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys

# Initialize colorama
init(autoreset=True)

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

def test_url(url, output_file, found_urls, proxies=None):
    try:
        response = requests.get(url, timeout=3, proxies=proxies, allow_redirects=True)
        final_url = response.url
        status_code = response.status_code
        if status_code == 200 and url not in found_urls:
            found_urls.add(url)
            result = f"Valid URL found: {url} (Status Code: {Fore.GREEN}{status_code}{Fore.WHITE}){Style.RESET_ALL}"
            if output_file:
                with open(output_file, 'a') as f:
                    f.write(f"{url} (Status Code: {status_code})\n")
            return result
        elif status_code != 404 and url not in found_urls:
            found_urls.add(url)
            return f"URL: {url} (Status Code: {Fore.RED}{status_code}{Fore.WHITE}){Style.RESET_ALL}"
    except requests.RequestException:
        pass
    return None

def fuzz_urls(subdomains, directories, extensions, domains, output_file, found_urls, base_url=None, depth=1, max_depth=1, proxies=None, max_workers=10):
    urls_to_fuzz = []

    def construct_url(subdomain, domain, directory=None, extension=None):
        # Determine the base URL, checking if it's already a full URL or needs "http://" prepended
        if "http://" in domain or "https://" in domain:
            base = domain
        else:
            base = f"http://{subdomain}.{domain}" if subdomain else f"http://{domain}"

        if directory and extension:
            return f"{base}/{directory}.{extension}"
        elif directory:
            return f"{base}/{directory}"
        return base

    if directories:
        for domain in domains:
            for subdomain in subdomains:
                for directory in directories:
                    if extensions:
                        for extension in extensions:
                            urls_to_fuzz.append(construct_url(subdomain, base_url if base_url else domain, directory, extension))
                            if subdomain == 'www':
                                urls_to_fuzz.append(construct_url(None, base_url if base_url else domain, directory, extension))
                            urls_to_fuzz.append(construct_url(subdomain, base_url if base_url else domain, directory))
                    else:
                        urls_to_fuzz.append(construct_url(subdomain, base_url if base_url else domain, directory))
                        if subdomain == 'www':
                            urls_to_fuzz.append(construct_url(None, base_url if base_url else domain, directory))
                        urls_to_fuzz.append(construct_url(subdomain, base_url if base_url else domain))
    elif subdomains:
        for domain in domains:
            for subdomain in subdomains:
                if extensions:
                    for extension in extensions:
                        urls_to_fuzz.append(construct_url(subdomain, base_url if base_url else domain, None, extension))
                        if subdomain == 'www':
                            urls_to_fuzz.append(construct_url(None, base_url if base_url else domain, None, extension))
                        urls_to_fuzz.append(construct_url(subdomain, base_url if base_url else domain))
                else:
                    urls_to_fuzz.append(construct_url(subdomain, base_url if base_url else domain))
                    if subdomain == 'www':
                        urls_to_fuzz.append(construct_url(None, base_url if base_url else domain))
    elif extensions:
        for domain in domains:
            for extension in extensions:
                urls_to_fuzz.append(construct_url(None, domain, None, extension))
                if domain == 'www':
                    urls_to_fuzz.append(construct_url(None, extension))
    else:
        for domain in domains:
            urls_to_fuzz.append(construct_url(None, domain))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(test_url, url, output_file, found_urls, proxies): url for url in urls_to_fuzz}
        for future in as_completed(futures):
            url = futures[future]
            result = future.result()
            # Clear the previous fuzzing URL line
            sys.stdout.write("\r" + " " * 100 + "\r")
            sys.stdout.flush()
            if result:
                print(result)
            # Display current fuzzing URL
            sys.stdout.write(f"\r{Fore.YELLOW}Fuzzing URL: {url} {Style.RESET_ALL}")
            sys.stdout.flush()
            # If a valid directory is found, continue fuzzing inside this directory
            if depth < max_depth and result:
                new_base_url = url.rstrip('/')
                # Ensure there's only one "http://" or "https://" in the URL
                if new_base_url.startswith('http://http://') or new_base_url.startswith('https://https://'):
                    new_base_url = new_base_url.replace('http://http://', 'http://').replace('https://https://', 'https://')
                
                # Check if the URL redirects to itself, skip if it does
                try:
                    response = requests.get(new_base_url, timeout=3, proxies=proxies, allow_redirects=True)
                    if response.url == new_base_url:
                        print(f"\n{Fore.BLUE}Skipping recursive fuzzing for {new_base_url} as it redirects to itself.{Style.RESET_ALL}")
                        continue
                except requests.RequestException:
                    continue
                
                fuzz_urls(subdomains, directories, extensions, [new_base_url], output_file, found_urls, new_base_url, depth + 1, max_depth, proxies, max_workers)

def fuzz_subdomains(base_url, wordlist, output_file, found_urls, proxies=None, max_workers=10):
    subdomains = read_wordlist(wordlist)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(test_url, f"http://{subdomain}.{base_url}", output_file, found_urls, proxies): subdomain for subdomain in subdomains}
        for future in as_completed(futures):
            subdomain = futures[future]
            result = future.result()
            # Clear the previous fuzzing URL line
            sys.stdout.write("\r" + " " * 100 + "\r")
            sys.stdout.flush()
            if result:
                print(result)
            # Display current fuzzing URL
            sys.stdout.write(f"\r{Fore.YELLOW}Fuzzing Subdomain: {subdomain}.{base_url} {Style.RESET_ALL}")
            sys.stdout.flush()

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

    if not args.subdomains and not args.directories and not args.extensions:
        parser.error("At least one of --subdomains, --directories, or --extensions must be specified.")

    subdomains = read_wordlist(args.subdomains) if args.subdomains else ['www']
    directories = read_wordlist(args.directories) if args.directories else None
    extensions = read_wordlist(args.extensions) if args.extensions else None
    domains = read_wordlist(args.domains) if args.domains else [args.url]
    output_file = args.output
    proxies = {'http': args.proxy, 'https': args.proxy} if args.proxy else None

    found_urls = set()

    fuzz_urls(subdomains, directories, extensions, domains, output_file, found_urls, base_url=args.url, max_depth=args.recursive, proxies=proxies, max_workers=args.threads)

if __name__ == "__main__":
    main()
