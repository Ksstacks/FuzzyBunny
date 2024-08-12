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

def test_url(url, output_file, found_urls, excluded_codes, proxies=None):
    try:
        response = requests.get(url, timeout=3, proxies=proxies)
        status_code = response.status_code
        if status_code in excluded_codes:
            return None

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

def redirects_to_home_page(url, home_url, proxies=None):
    try:
        response = requests.get(url, timeout=3, proxies=proxies, allow_redirects=False)
        if response.is_redirect:
            redirect_url = response.headers.get('Location', '')
            # Normalize URLs for comparison
            if redirect_url.startswith('/'):
                redirect_url = home_url.rstrip('/') + redirect_url
            if redirect_url == home_url:
                return True
    except requests.RequestException:
        pass
    return False

def construct_url(subdomain, domain, directory=None, extension=None):
    # Construct the full URL based on provided directory and extension
    if directory and extension:
        return f"{domain}/{directory}.{extension}"
    elif directory:
        return f"{domain}/{directory}"
    return domain

def fuzz_urls(subdomains, directories, extensions, domains, output_file, found_urls, excluded_codes, base_url=None, depth=1, max_depth=1, proxies=None, max_workers=10):
    urls_to_fuzz = []

    if directories:
        for domain in domains:
            for subdomain in subdomains:
                for directory in directories:
                    if extensions:
                        for extension in extensions:
                            url = construct_url(subdomain, domain, directory, extension)
                            urls_to_fuzz.append(url)
                            if subdomain == 'www':
                                url = construct_url(None, domain, directory, extension)
                                urls_to_fuzz.append(url)
                            url = construct_url(subdomain, domain, directory)
                            urls_to_fuzz.append(url)
                    else:
                        url = construct_url(subdomain, domain, directory)
                        urls_to_fuzz.append(url)
                        if subdomain == 'www':
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
                        if subdomain == 'www':
                            url = construct_url(None, domain, None, extension)
                            urls_to_fuzz.append(url)
                        url = construct_url(subdomain, domain)
                        urls_to_fuzz.append(url)
                else:
                    url = construct_url(subdomain, domain)
                    urls_to_fuzz.append(url)
                    if subdomain == 'www':
                        url = construct_url(None, domain)
                        urls_to_fuzz.append(url)
    elif extensions:
        for domain in domains:
            for extension in extensions:
                url = construct_url(None, domain, None, extension)
                urls_to_fuzz.append(url)
                if domain == 'www':
                    url = construct_url(None, extension)
                    urls_to_fuzz.append(url)
    else:
        for domain in domains:
            url = construct_url(None, domain)
            urls_to_fuzz.append(url)

    home_url = base_url.rstrip('/')

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(test_url, url, output_file, found_urls, excluded_codes, proxies): url for url in urls_to_fuzz}
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

            # If a valid directory is found
            if result:
                # Check if it redirects to the home page
                if redirects_to_home_page(url, home_url, proxies):
                    print(f"{Fore.YELLOW}Skipping URL {url} because it redirects to the home page.{Style.RESET_ALL}")
                elif depth < max_depth:
                    # Continue recursive fuzzing with the new base URL
                    new_base_url = url.rstrip('/')
                    fuzz_urls(subdomains, directories, extensions, [new_base_url], output_file, found_urls, excluded_codes, new_base_url, depth + 1, max_depth, proxies, max_workers)

def main():
    parser = argparse.ArgumentParser(
        description="Fuzzer for enumeration and fuzzing with extensions and subdomains.\n\n"
                    "Examples:\n"
                    "  python fuzzer.py -u https://example.com -d directories.txt",
        formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('-u', '--url', required=True, help='Base URL for fuzzing. Must start with http:// or https://.')
    parser.add_argument('-s', '--subdomains', help='Path to the subdomains wordlist.')
    parser.add_argument('-d', '--directories', help='Path to the directories wordlist.')
    parser.add_argument('-e', '--extensions', help='Path to the extensions wordlist.')
    parser.add_argument('-w', '--domains', help='Path to the domains wordlist.')
    parser.add_argument('-o', '--output', help='File to save the valid URLs.')
    parser.add_argument('-r', '--recursive', type=int, default=1, help='Depth of recursive search (default: 1).')
    parser.add_argument('-p', '--proxy', help='Proxy URL (format: http://proxy_ip:proxy_port or socks5://proxy_ip:proxy_port).')
    parser.add_argument('-t', '--threads', type=int, default=10, help='Number of concurrent threads (default: 10).')
    parser.add_argument('-x', '--exclude', nargs='+', type=int, help='HTTP status codes to exclude (e.g., 403 500).')

    args = parser.parse_args()

    # Check if URL starts with http:// or https://
    if not (args.url.startswith('http://') or args.url.startswith('https://')):
        parser.error("The URL must start with http:// or https://")

    if not args.subdomains and not args.directories and not args.extensions:
        parser.error("At least one of --subdomains, --directories, or --extensions must be specified.")

    subdomains = read_wordlist(args.subdomains) if args.subdomains else ['www']
    directories = read_wordlist(args.directories) if args.directories else None
    extensions = read_wordlist(args.extensions) if args.extensions else None
    domains = read_wordlist(args.domains) if args.domains else [args.url]
    output_file = args.output
    base_url = args.url
    recursive_depth = args.recursive
    proxy = args.proxy
    threads = args.threads
    excluded_codes = set(args.exclude) if args.exclude else set()

    proxies = {'http': proxy, 'https': proxy} if proxy else None

    if output_file and os.path.exists(output_file):
        os.remove(output_file)

    found_urls = set()

    fuzz_urls(subdomains, directories, extensions, domains, output_file, found_urls, excluded_codes, base_url, max_depth=recursive_depth, proxies=proxies, max_workers=threads)

if __name__ == "__main__":
    main()
