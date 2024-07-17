import argparse
import requests
import os
from colorama import Fore,Back,Style

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

def test_url(url, output_file, found_urls):
    try:
        response = requests.get(url, timeout=3)
        status_code = response.status_code
        if status_code == 200 and url not in found_urls:
            print(f"Valid URL found: {url} (Status Code: " + Fore.GREEN + f"{status_code}" + Fore.WHITE + ")")
            found_urls.add(url)
            if output_file:
                with open(output_file, 'a') as f:
                    f.write(f"{url} (Status Code: {status_code})\n")
            return True
        elif status_code != 404 and url not in found_urls:
            print(f"URL: {url} (Status Code: " + Fore.Blue + f"{status_code}" + Fore.WHITE + ")")
            found_urls.add(url)
    except requests.RequestException:
        pass
    return False

def fuzz_urls(subdomains, directories, extensions, domains, output_file, found_urls, base_url=None, depth=1):
    for domain in domains:
        for subdomain in subdomains:
            for directory in directories:
                for extension in extensions:
                    # Construct URLs
                    if base_url:
                        url = f"http://{subdomain}.{base_url}/{directory}/index.{extension}"
                    else:
                        url = f"http://{subdomain}.{domain}/{directory}/index.{extension}"

                    if test_url(url, output_file, found_urls) and depth > 0:
                        fuzz_urls(subdomains, directories, extensions, [f"{subdomain}.{domain}"], output_file, found_urls, base_url, depth-1)

                    # Additional test without www
                    if subdomain == 'www':
                        if base_url:
                            url = f"http://{base_url}/{directory}/index.{extension}"
                        else:
                            url = f"http://{domain}/{directory}/index.{extension}"
                        if test_url(url, output_file, found_urls) and depth > 0:
                            fuzz_urls(subdomains, directories, extensions, [domain], output_file, found_urls, base_url, depth-1)

                    # Additional test for just subdomain
                    if base_url:
                        url = f"http://{subdomain}.{base_url}/{directory}"
                    else:
                        url = f"http://{subdomain}.{domain}/{directory}"
                    if test_url(url, output_file, found_urls) and depth > 0:
                        fuzz_urls(subdomains, directories, extensions, [f"{subdomain}.{domain}"], output_file, found_urls, base_url, depth-1)

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

    if output_file and os.path.exists(output_file):
        os.remove(output_file)

    found_urls = set()
    fuzz_urls(subdomains, directories, extensions, domains, output_file, found_urls, base_url, recursive_depth)

if __name__ == "__main__":
    main()
