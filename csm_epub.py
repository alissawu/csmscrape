import os
import re
from ebooklib import epub

# Reuse constants + image ordering from your PDF script
from csm_all import (
    collect_images_for_volume,
    FIRST_VOL,
    LAST_VOL,
    OUTPUT_ROOT,
)

EPUB_OUTPUT = os.path.join(OUTPUT_ROOT, "epubs")
os.makedirs(EPUB_OUTPUT, exist_ok=True)


def guess_mime(path: str) -> str:
    """Simple image mime guess based on extension."""
    lower = path.lower()
    if lower.endswith(".png"):
        return "image/png"
    # default jpeg for jpg / jpeg / other
    return "image/jpeg"


def extract_chapter_label(rel_path: str) -> str:
    """
    From a rel_path like:
      Chainsaw Man .../Chapter 8 - Chainsaw Vs. Bat/02.jpg
    return:
      'Chapter 8 - Chainsaw Vs. Bat'
    """
    m = re.search(r"(Chapter\s+\d+[^/]*)", rel_path)
    if m:
        return m.group(1)
    # fallback
    return "Pages"


def build_epub_for_volume(vol: str):
    image_entries = collect_images_for_volume(vol)
    if not image_entries:
        print(f"[!] No images for volume {vol}, skipping EPUB.")
        return

    print(f"[+] Building EPUB for volume {vol} with {len(image_entries)} pages...")

    # Group pages by chapter in order of appearance
    chapters = {}  # chapter_label -> list[(rel_path, full_path)]
    for rel_path, full_path in image_entries:
        chap_label = extract_chapter_label(rel_path)
        if chap_label not in chapters:
            chapters[chap_label] = []
        chapters[chap_label].append((rel_path, full_path))

    book = epub.EpubBook()
    book.set_identifier(f"chainsaw-man-colored-v{vol}")
    book.set_title(f"Chainsaw Man (Digitally Colored) v{vol}")
    book.set_language("en")

    # Basic metadata
    book.add_author("Tatsuki Fujimoto")
    book.add_metadata(
        "DC", "description",
        f"Chainsaw Man, Digitally Colored, Volume {vol}"
    )

    spine_items = []
    toc_links = []

    chapter_index = 0

    for chap_label, pages in chapters.items():
        chapter_index += 1

        first_page_item = None

        for page_index, (rel_path, full_path) in enumerate(pages, start=1):
            # Add image resource
            img_id = f"img_v{vol}_{chapter_index}_{page_index}"
            img_file_name = f"images/v{vol}/{img_id}{os.path.splitext(full_path)[1]}"
            with open(full_path, "rb") as f:
                img_item = epub.EpubItem(
                    uid=img_id,
                    file_name=img_file_name,
                    media_type=guess_mime(full_path),
                    content=f.read(),
                )
            book.add_item(img_item)

            # Simple XHTML page that shows the image
            page_uid = f"page_v{vol}_{chapter_index}_{page_index}"
            page_file_name = f"text/v{vol}_{chapter_index}_{page_index}.xhtml"

            page_html = epub.EpubHtml(
                uid=page_uid,
                file_name=page_file_name,
                title=f"{chap_label} - {page_index}",
                lang="en",
            )
            # Very minimal markup, image centered
            page_html.content = f"""
            <html xmlns="http://www.w3.org/1999/xhtml">
              <head>
                <title>{chap_label} - {page_index}</title>
                <meta charset="utf-8" />
                <style>
                  body {{ margin: 0; padding: 0; text-align: center; background: #000; }}
                  img  {{ max-width: 100%; height: auto; }}
                </style>
              </head>
              <body>
                <img src="../{img_file_name}" alt="{chap_label} page {page_index}" />
              </body>
            </html>
            """.strip()

            book.add_item(page_html)
            spine_items.append(page_html)

            if first_page_item is None:
                first_page_item = page_html

        # For TOC: link the chapter name to the *first* page of that chapter
        if first_page_item is not None:
            toc_links.append(
                epub.Link(
                    first_page_item.file_name,
                    chap_label,
                    f"toc_v{vol}_chap_{chapter_index}",
                )
            )

    # Table of contents (dropdown in readers like Apple Books).
    # This does NOT create a visible "TOC page" at the front.
    book.toc = toc_links

    # Required navigation files (NCX + Nav), but we do NOT
    # include 'nav' in the spine, so it's not shown as first page.
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Reading order: just the pages, in order
    book.spine = spine_items

    epub_name = f"Chainsaw_Man_Digitally_Colored_v{vol}.epub"
    epub_path = os.path.join(EPUB_OUTPUT, epub_name)

    epub.write_epub(epub_path, book)
    print(f"[✓] Saved EPUB -> {epub_path}")


def main():
    # Try all volumes 1..LAST_VOL; build epubs only where we have images
    vols = [f"{i:02d}" for i in range(FIRST_VOL, LAST_VOL + 1)]
    for vol in vols:
        build_epub_for_volume(vol)

    print("[✓] All EPUBs done.")


if __name__ == "__main__":
    main()
