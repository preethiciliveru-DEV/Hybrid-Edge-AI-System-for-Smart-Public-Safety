"""
Simple Wikimedia Commons image fetcher for public-domain/CC images by search term.

Usage:
  python wikimedia_fetcher.py --query "kitchen knife" --out_dir downloaded/kitchen_knife --max 300

Notes:
- This fetcher uses the MediaWiki API and filters by file type and size.
- It does not guarantee annotations. Downloaded images must be manually labeled or added as negatives.
"""
import requests
import os
import argparse
from urllib.parse import quote_plus

WIKI_API = "https://commons.wikimedia.org/w/api.php"


def search_images(query, max_results=100):
    params = {
        'action': 'query',
        'generator': 'search',
        'gsrsearch': query,
        'gsrlimit': max_results,
        'prop': 'imageinfo',
        'iiprop': 'url|size|mime',
        'format': 'json'
    }
    r = requests.get(WIKI_API, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    images = []
    if 'query' not in data:
        return images
    pages = data['query'].get('pages', {})
    for pid, page in pages.items():
        if 'imageinfo' in page:
            for info in page['imageinfo']:
                url = info.get('url')
                mime = info.get('mime')
                size = info.get('size', 0)
                if url and mime and mime.startswith('image') and size > 10000:
                    images.append(url)
    return images


def download_images(urls, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for i, url in enumerate(urls):
        try:
            r = requests.get(url, stream=True, timeout=10)
            r.raise_for_status()
            ext = os.path.splitext(url.split('?')[0])[1]
            fname = f"img_{i:05d}{ext}"
            outp = os.path.join(out_dir, fname)
            with open(outp, 'wb') as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)
        except Exception as e:
            print('Failed', url, e)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--query', required=True)
    parser.add_argument('--out_dir', required=True)
    parser.add_argument('--max', type=int, default=200)
    args = parser.parse_args()
    urls = search_images(args.query, max_results=args.max)
    print('Found', len(urls), 'images for', args.query)
    download_images(urls, args.out_dir)

if __name__ == '__main__':
    main()
