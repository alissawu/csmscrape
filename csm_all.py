import os
import re
import time
import requests
from urllib.parse import unquote
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed

ARCHIVE_PAGE_URL = (
    "https://ia800203.us.archive.org/view_archive.php?"
    "archive=/27/items/chainsaw-man-digitally-colored/"
    "Chainsaw%20Man%20%28Digitally%20Colored%29.rar"
)

# Volumes v01 ... v11
FIRST_VOL = 1
LAST_VOL = 11
TARGET_VOLUMES = {f"{i:02d}" for i in range(FIRST_VOL, LAST_VOL + 1)}

# Root output and subfolders
OUTPUT_ROOT = "chainsaw_man_colored"
PDF_OUTPUT = os.path.join(OUTPUT_ROOT, "pdfs")
os.makedirs(OUTPUT_ROOT, exist_ok=True)
os.makedirs(PDF_OUTPUT, exist_ok=True)


# ------------------------------------
#   FETCH HTML
# ------------------------------------
def fetch_html(url: str) -> str:
    print(f"[+] Fetching HTML from {url} ...")
    resp = requests.get(url)
    resp.raise_for_status()
    print(f"[+] Got {len(resp.text)} bytes of HTML")
    return resp.text


# ------------------------------------
#   PARSE IMAGE LINKS
# ------------------------------------
def parse_image_links(html: str):
    """
    Return a list of dicts:
      { 'vol': '01', 'inner_path': 'Chainsaw Man (Digitally Colored)/...', 'url': 'https://...' }
    """
    href_pattern = r'href="([^"]+\.(?:jpg|jpeg|png))"'
    raw_hrefs = re.findall(href_pattern, html, flags=re.IGNORECASE)
    print(f"[+] Found {len(raw_hrefs)} hrefs ending in jpg/png")

    links_info = []

    for href in raw_hrefs:
        if href.startswith("//"):
            full_url = "https:" + href
        elif href.startswith("http://") or href.startswith("https://"):
            full_url = href
        else:
            continue

        decoded = unquote(href)

        # volume number from "Digital Colored Comics v02"
        vol_match = re.search(r"Digital Colored Comics v(\d{2})", decoded)
        if not vol_match:
            continue

        vol = vol_match.group(1)
        if vol not in TARGET_VOLUMES:
            continue

        # inner path inside archive
        inner_idx = decoded.find("Chainsaw Man (Digitally Colored)/")
        if inner_idx == -1:
            inner_path = decoded.split("/")[-1]
        else:
            inner_path = decoded[inner_idx:]

        links_info.append(
            {"vol": vol, "inner_path": inner_path, "url": full_url}
        )

    print(f"[+] Kept {len(links_info)} images for vols {sorted(TARGET_VOLUMES)}")
    for sample in links_info[:5]:
        print("    sample:", sample["inner_path"])

    return links_info


# ------------------------------------
#   PARALLEL DOWNLOADS WITH RETRIES
# ------------------------------------
def make_session():
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (csm-fast-downloader)"})
    return s


def _download_one(item, session, retries: int = 3, backoff_base: float = 1.0):
    vol = item["vol"]
    inner_path = item["inner_path"]
    url = item["url"]

    local_path = os.path.join(OUTPUT_ROOT, inner_path)
    os.makedirs(os.path.dirname(local_path), exist_ok=True)

    if os.path.exists(local_path):
        return f"[=] Skipped (exists): {local_path}"

    last_err = None
    for attempt in range(1, retries + 1):
        try:
            with session.get(url, stream=True, timeout=20) as r:
                r.raise_for_status()
                with open(local_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=16384):
                        if chunk:
                            f.write(chunk)
            return f"[↓] Downloaded v{vol}: {inner_path}"
        except Exception as e:
            last_err = e
            if attempt < retries:
                sleep_for = backoff_base * attempt
                print(
                    f"[!] Retry {attempt}/{retries} for {url} in {sleep_for:.1f}s "
                    f"({e})"
                )
                time.sleep(sleep_for)
            else:
                break

    return f"[!] FAILED {url} — {last_err}"


def download_images(links_info, max_workers=8):
    if not links_info:
        print("[!] No images to download.")
        return

    session = make_session()
    print(f"[+] Starting parallel downloads ({max_workers} threads)...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_download_one, item, session)
            for item in links_info
        ]
        for fut in as_completed(futures):
            print(fut.result())


# ------------------------------------
#   IMAGE COLLECTION / ORDERING
# ------------------------------------
def _sort_key_for_relpath(rel_path: str):
    """
    Sort by chapter number then page number.

    rel_path looks like:
      'Chainsaw Man .../Chapter 10 - Kon/03.jpg'
    """
    # chapter number
    chap_match = re.search(r"Chapter\s+(\d+)", rel_path)
    chap_num = int(chap_match.group(1)) if chap_match else 9999

    # page number from filename
    base = os.path.basename(rel_path)
    page_match = re.search(r"(\d+)(?=\.[^.]+$)", base)
    page_num = int(page_match.group(1)) if page_match else 9999

    return (chap_num, page_num, rel_path)


def collect_images_for_volume(vol: str):
    """
    Walk OUTPUT_ROOT and gather all images for a given volume.
    Returns list of (rel_path, full_path) sorted by chapter/page.
    """
    tag = f"Digital Colored Comics v{vol}"
    image_entries = []

    for root, _, files in os.walk(OUTPUT_ROOT):
        if tag not in root:
            continue

        for name in files:
            if not name.lower().endswith((".jpg", ".jpeg", ".png")):
                continue

            full_path = os.path.join(root, name)
            rel_path = os.path.relpath(full_path, OUTPUT_ROOT)
            image_entries.append((rel_path, full_path))

    image_entries.sort(key=lambda t: _sort_key_for_relpath(t[0]))
    return image_entries


# ------------------------------------
#   PDF BUILDING
# ------------------------------------
def build_pdf_for_volume(vol: str):
    images_entries = collect_images_for_volume(vol)
    if not images_entries:
        print(f"[!] No images for volume {vol}")
        return

    pdf_name = f"Chainsaw_Man_Digitally_Colored_v{vol}.pdf"
    pdf_path = os.path.join(PDF_OUTPUT, pdf_name)

    if os.path.exists(pdf_path):
        print(f"[=] PDF already exists for v{vol}, skipping.")
        return

    print(f"[+] Building PDF v{vol} ({len(images_entries)} pages)...")

    images = []
    for _, full_path in images_entries:
        try:
            img = Image.open(full_path)
            if img.mode != "RGB":
                img = img.convert("RGB")
            images.append(img)
        except Exception as e:
            print(f"[!] Failed reading {full_path}: {e}")

    if images:
        images[0].save(pdf_path, save_all=True, append_images=images[1:])
        print(f"[✓] Saved {pdf_path}")
    else:
        print(f"[!] No valid images for v{vol}")


# ------------------------------------
#   MAIN
# ------------------------------------
def main():
    html = fetch_html(ARCHIVE_PAGE_URL)
    links_info = parse_image_links(html)
    links_info.sort(key=lambda x: (x["vol"], x["inner_path"]))

    download_images(links_info, max_workers=3)

    vols_present = sorted({item["vol"] for item in links_info})
    print(f"[+] Found volumes: {vols_present}")

    for vol in vols_present:
        build_pdf_for_volume(vol)

    print("[✓] ALL DONE.")


if __name__ == "__main__":
    main()
