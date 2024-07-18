import argparse
import requests
import os
from colorama import Fore, Back, Style
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    return False

def fuzz_url(url, output_file, found_urls, proxies=None, depth=0, max_depth=1):
    if test_url(url, output_file, found_urls, proxies) and depth < max_depth:
        return url
    return None

def fuzz_urls(subdomains, directories, extensions, domains, output_file, found_urls, base_url=None, depth=1, proxies=None, max_workers=10):
    urls_to_fuzz = []
    for domain in domains:
        for subdomain in subdomains:
            for directory in directories:
                for extension in extensions:
                    # Construct URLs
                    if base_url:
                        url = f"http://{subdomain}.{base_url}/{directory}/index.{extension}"
                    else:
                        url = f"http://{subdomain}.{domain}/{directory}/index.{extension}"
                    urls_to_fuzz.append((url, depth))

                    # Additional test without www
                    if subdomain == 'www':
                        if base_url:
                            url = f"http://{base_url}/{directory}/index.{extension}"
                        else:
                            url = f"http://{domain}/{directory}/index.{extension}"
                        urls_to_fuzz.append((url, depth))

                    # Additional test for just subdomain
                    if base_url:
                        url = f"http://{subdomain}.{base_url}/{directory}"
                    else:
                        url = f"http://{subdomain}.{domain}/{directory}"
                    urls_to_fuzz.append((url, depth))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fuzz_url, url, output_file, found_urls, proxies, d, depth): url for url, d in urls_to_fuzz}
        for future in as_completed(futures):
            result = future.result()
            if result:
                subdomains.append(result.split('/')[2].split('.')[0])
                fuzz_urls(subdomains, directories, extensions, [result.split('/')[2]], output_file, found_urls, base_url, depth - 1, proxies, max_workers)

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
    fuzz_urls(subdomains, directories, extensions, domains, output_file, found_urls, base_url, recursive_depth, proxies, threads)

if __name__ == "__main__":
    main()
