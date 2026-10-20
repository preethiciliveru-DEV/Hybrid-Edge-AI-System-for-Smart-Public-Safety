"""
Roboflow importer: search Wikimedia Commons for images per-class and upload by URL to Roboflow project.

Usage: python roboflow_importer.py

Caveats:
- Uses Roboflow API key stored in the script variables (private). Keep file private.
- Throttles requests and backs off on errors to reduce Wikimedia rate-limit failures.
- This script aims to reach target counts for each class and negatives, but may take hours depending on rate limits.
"""

import requests, time, sys, random, os
from urllib.parse import urlencode

# -------- CONFIG --------
ROBOFLOW_API_KEY = '2K30DIUQqoc7L2gPW4HR'  # your private key (do not share)
WORKSPACE = 'preethies'
PROJECT = 'hybridsafety-weapons'
UPLOAD_ENDPOINT = f'https://api.roboflow.com/{WORKSPACE}/{PROJECT}/upload'

USER_AGENT = 'HybridSafetyImporter/1.0 (contact: preethies)'

TARGETS = {
    'kitchen_knife': {'queries': ['kitchen knife','chef knife','kitchen knives','kitchen cutlery knife'], 'target': 220},
    'scissors': {'queries': ['scissors','hair scissors','fabric scissors','kitchen scissors'], 'target': 220},
    'pistol': {'queries': ['pistol','handgun','revolver','semi-automatic pistol'], 'target': 220},
    'rifle': {'queries': ['rifle','assault rifle','sniper rifle','hunting rifle'], 'target': 220}
}
NEGATIVE_QUERIES = ['spoon','fork','butter knife','screwdriver','pliers','wrench','phone','remote control','flashlight','pen','ruler','toothbrush','toy gun','kitchen clutter','desk clutter','bag','clothes','boxes','outdoor clutter']
NEGATIVES_TARGET = 800

WIKI_API = 'https://commons.wikimedia.org/w/api.php'

# Time settings
SLEEP_BETWEEN_REQUESTS = 3.0
SLEEP_ON_429 = 60.0
MAX_RETRIES = 5

# Keep track of uploaded URLs to avoid duplicates in this run
uploaded = set()

# helper: search wikimedia for image URLs
def search_wikimedia(query, limit=50):
    params = {
        'action': 'query',
        'generator': 'search',
        'gsrsearch': query,
        'gsrlimit': limit,
        'prop': 'imageinfo',
        'iiprop': 'url|mime|size',
        'format': 'json'
    }
    headers = {'User-Agent': USER_AGENT}
    retries = 0
    while retries < MAX_RETRIES:
        try:
            r = requests.get(WIKI_API, params=params, headers=headers, timeout=30)
            if r.status_code == 429:
                print('Wikimedia rate limited (429). Backing off for', SLEEP_ON_429, 's')
                time.sleep(SLEEP_ON_429)
                retries += 1
                continue
            r.raise_for_status()
            data = r.json()
            urls = []
            pages = data.get('query', {}).get('pages', {})
            for p in pages.values():
                for ii in p.get('imageinfo', []) if isinstance(p.get('imageinfo', []), list) else []:
                    mime = ii.get('mime', '')
                    size = ii.get('size', 0)
                    url = ii.get('url')
                    if url and mime.startswith('image') and size > 8000:
                        urls.append(url)
            return list(dict.fromkeys(urls))
        except Exception as e:
            print('Wikimedia search error:', e)
            time.sleep(SLEEP_ON_429)
            retries += 1
    return []

# helper: upload URL to roboflow
def upload_to_roboflow(image_url, split='train'):
    params = {'api_key': ROBOFLOW_API_KEY}
    data = {'image': image_url, 'split': split}
    headers = {'User-Agent': USER_AGENT}
    try:
        resp = requests.post(UPLOAD_ENDPOINT, params=params, data=data, headers=headers, timeout=30)
        if resp.status_code in (200,201):
            return True, resp.text
        else:
            return False, f'{resp.status_code}: {resp.text}'
    except Exception as e:
        return False, str(e)

# Filtering helpers
def is_toy_or_replica(url):
    l = url.lower()
    return any(tok in l for tok in ('toy','replica','airsoft','bb_', 'paintball'))

def is_butter_or_plastic(url):
    l = url.lower()
    return any(tok in l for tok in ('butter','plastic','spoon','fork'))

# Main import loop
if __name__ == '__main__':
    total_uploaded = 0
    # Ensure log
    os.makedirs('import_logs', exist_ok=True)
    logf = open('import_logs/import_log.txt', 'a', encoding='utf-8')

    # Upload positives
    for cls, cfg in TARGETS.items():
        need = cfg['target']
        uploaded_count = 0
        print(f'=== Collecting for class {cls} target {need} ===')
        queries = cfg['queries']
        q_index = 0
        attempts = 0
        while uploaded_count < need and attempts < need * 10:
            q = queries[q_index % len(queries)]
            q_index += 1
            attempts += 1
            print(f'Searching for "{q}" (attempt {attempts})')
            urls = search_wikimedia(q, limit=60)
            if not urls:
                print('No urls returned; sleeping then continuing')
                time.sleep(SLEEP_ON_429)
                continue
            for u in urls:
                if uploaded_count >= need:
                    break
                if u in uploaded:
                    continue
                # class-specific filters
                if cls in ('pistol','rifle') and is_toy_or_replica(u):
                    continue
                if cls == 'kitchen_knife' and is_butter_or_plastic(u):
                    continue
                success, info = upload_to_roboflow(u, split='train')
                if success:
                    uploaded.add(u)
                    uploaded_count += 1
                    total_uploaded += 1
                    print(f'Uploaded {uploaded_count}/{need} for {cls}')
                    logf.write(f'POS,{cls},{u}\n')
                    logf.flush()
                else:
                    print('Upload failed:', info)
                time.sleep(SLEEP_BETWEEN_REQUESTS + random.random())
            # small pause to not hammer
            time.sleep(2.0 + random.random()*2.0)
        print(f'Finished {cls}: {uploaded_count} uploaded')

    # Upload negatives
    neg_uploaded = 0
    print('=== Collecting negatives ===')
    q_index = 0
    q_attempts = 0
    neg_queries_cycle = NEGATIVE_QUERIES.copy()
    while neg_uploaded < NEGATIVES_TARGET and q_attempts < NEGATIVES_TARGET * 20:
        q = neg_queries_cycle[q_index % len(neg_queries_cycle)]
        q_index += 1
        q_attempts += 1
        print(f'Searching negatives for "{q}" (attempt {q_attempts})')
        urls = search_wikimedia(q, limit=80)
        if not urls:
            print('No urls; sleeping')
            time.sleep(SLEEP_ON_429)
            continue
        for u in urls:
            if neg_uploaded >= NEGATIVES_TARGET:
                break
            if u in uploaded:
                continue
            l = u.lower()
            if any(tok in l for tok in ('pistol','rifle','gun','handgun')):
                continue
            success, info = upload_to_roboflow(u, split='train')
            if success:
                uploaded.add(u)
                neg_uploaded += 1
                total_uploaded += 1
                print(f'Negatives uploaded: {neg_uploaded}/{NEGATIVES_TARGET}')
                logf.write(f'NEG,{u}\n')
                logf.flush()
            else:
                print('Upload failed:', info)
            time.sleep(SLEEP_BETWEEN_REQUESTS + random.random())
        time.sleep(2.0 + random.random()*2.0)

    print('Import complete. Total uploaded:', total_uploaded)
    logf.write(f'COMPLETE,{total_uploaded}\n')
    logf.close()

    # After upload, create a version via API (simple request)
    print('Creating a new version in Roboflow...')
    version_url = f'https://api.roboflow.com/{WORKSPACE}/{PROJECT}/versions?api_key={ROBOFLOW_API_KEY}'
    # minimal payload: name
    try:
        r = requests.post(version_url, json={'version': {'name': 'auto-import-1'}}, timeout=30)
        print('Version create response:', r.status_code, r.text)
    except Exception as e:
        print('Version create failed:', e)

    print('All done. You can check your Roboflow project now.')
