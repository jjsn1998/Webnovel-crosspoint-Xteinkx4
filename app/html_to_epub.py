import argparse
import html
import re
import uuid
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString
from ebooklib import epub


BLOCK_TAGS = {
    "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "blockquote", "ul", "ol", "hr", "pre"
}


def clean_filename(name: str) -> str:
    name = re.sub(r"[^\w\s.-]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:100] or "book"


def extract_main_content(soup: BeautifulSoup):
    for tag in soup(["script", "style", "noscript", "iframe", "svg", "form", "button", "input"]):
        tag.decompose()

    candidates = [
        "article",
        "main",
        ".entry-content",
        ".post-content",
        ".page-content",
        ".content",
    ]

    for selector in candidates:
        found = soup.select_one(selector)
        if found and len(found.get_text(strip=True)) > 500:
            return found

    return soup.find("body") or soup


def clean_content(content, remove_images=True):
    bad_words = [
        "comment", "comments", "respond", "reply",
        "sidebar", "footer", "header", "nav", "menu",
        "share", "social", "related", "advert", "ad-",
        "cookie", "subscribe", "newsletter"
    ]

    for tag in list(content.find_all(True)):
        tag_id = (tag.get("id") or "").lower()
        tag_class = " ".join(tag.get("class") or []).lower()
        combined = f"{tag_id} {tag_class}"

        if any(word in combined for word in bad_words):
            tag.decompose()

    if remove_images:
        for tag in list(content.find_all(["img", "picture", "source", "figure"])):
            tag.decompose()

    for tag in content.find_all(True):
        if tag.name == "a" and tag.get("href"):
            tag.attrs = {"href": tag.get("href")}
        else:
            tag.attrs = {}

    for tag in list(content.find_all(["p", "div", "span"])):
        if not tag.get_text(strip=True) and not tag.find(["img", "hr"]):
            tag.decompose()

    return content


def collect_blocks(node):
    blocks = []

    for child in node.children:
        if isinstance(child, NavigableString):
            text = str(child).strip()
            if text:
                blocks.append(f"<p>{html.escape(text)}</p>")
            continue

        if not getattr(child, "name", None):
            continue

        if child.name.lower() in BLOCK_TAGS:
            text = child.get_text(" ", strip=True)
            if child.name.lower() == "hr":
                blocks.append("<hr/>")
            elif text:
                blocks.append(str(child))
            continue

        blocks.extend(collect_blocks(child))

    return blocks


def split_blocks(blocks, max_chars):
    chunks = []
    current = []
    current_chars = 0

    for block in blocks:
        plain = BeautifulSoup(block, "lxml").get_text(" ", strip=True)
        block_chars = len(plain)

        if current and current_chars + block_chars > max_chars:
            chunks.append(current)
            current = []
            current_chars = 0

        current.append(block)
        current_chars += block_chars

    if current:
        chunks.append(current)

    return chunks


def build_epub(html_file: Path, output_dir: Path, author: str, chunk_size: int):
    raw_html = html_file.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(raw_html, "lxml")

    title = html_file.stem
    safe_title = html.escape(title)

    content = extract_main_content(soup)
    content = clean_content(content, remove_images=True)

    blocks = collect_blocks(content)

    if blocks:
        first_text = BeautifulSoup(blocks[0], "lxml").get_text(" ", strip=True).lower()
        if first_text == title.lower():
            blocks = blocks[1:]

    if not blocks:
        blocks = [f"<p>{html.escape(content.get_text(' ', strip=True))}</p>"]

    chunks = split_blocks(blocks, chunk_size)

    book = epub.EpubBook()
    book.set_identifier(str(uuid.uuid4()))
    book.set_title(title)
    book.set_language("en")
    book.add_author(author)

    css = """
    body {
        font-family: serif;
        line-height: 1.45;
        margin: 0;
        padding: 0;
    }
    h1, h2 {
        text-align: center;
        margin-bottom: 1em;
    }
    p {
        margin-top: 0;
        margin-bottom: 1em;
        text-indent: 0;
    }
    blockquote {
        margin-left: 1em;
        margin-right: 1em;
    }
    hr {
        margin: 1.5em 0;
    }
    """

    style = epub.EpubItem(
        uid="style",
        file_name="style/main.css",
        media_type="text/css",
        content=css,
    )
    book.add_item(style)

    epub_chapters = []

    for index, chunk in enumerate(chunks, start=1):
        part_title = title if len(chunks) == 1 else f"{title} - Part {index}"
        safe_part_title = html.escape(part_title)
        file_name = f"part-{index:03}.xhtml"

        chapter = epub.EpubHtml(
            title=part_title,
            file_name=file_name,
            lang="en",
        )

        heading = safe_title if index == 1 else f"{safe_title} — Part {index}"

        chapter.content = f"""
        <html>
          <head>
            <title>{safe_part_title}</title>
            <link rel="stylesheet" type="text/css" href="style/main.css"/>
          </head>
          <body>
            <h1>{heading}</h1>
            {''.join(chunk)}
          </body>
        </html>
        """

        chapter.add_item(style)
        book.add_item(chapter)
        epub_chapters.append(chapter)

    book.toc = tuple(epub_chapters)
    book.spine = ["nav"] + epub_chapters

    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    output_dir.mkdir(parents=True, exist_ok=True)

    output_name = clean_filename(title) + ".epub"
    output_path = output_dir / output_name

    epub.write_epub(str(output_path), book)
    return output_path, len(chunks)


def main():
    parser = argparse.ArgumentParser(description="Convert saved HTML web novel chapter to split EPUB.")
    parser.add_argument("html_file", help="Path to saved HTML file")
    parser.add_argument("--output", default="/output", help="Output directory")
    parser.add_argument("--author", default="Unknown", help="Author name")
    parser.add_argument("--chunk-size", type=int, default=3500, help="Characters per internal EPUB section")

    args = parser.parse_args()

    html_file = Path(args.html_file)
    output_dir = Path(args.output)

    if not html_file.exists():
        raise FileNotFoundError(f"HTML file not found: {html_file}")

    output_path, chunks = build_epub(
        html_file=html_file,
        output_dir=output_dir,
        author=args.author,
        chunk_size=args.chunk_size,
    )

    print(f"Created EPUB: {output_path}")
    print(f"Internal sections created: {chunks}")


if __name__ == "__main__":
    main()
