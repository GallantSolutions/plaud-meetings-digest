#!/usr/bin/env python3
"""
notion-page-write.py — Create a child page under a Notion parent page with
a markdown body. Used by the weekly-rollup skill to write the Monday-morning
synthesis page.

Markdown → Notion blocks conversion is intentionally minimal: headings (#, ##,
###), paragraphs, bulleted lists, numbered lists, blockquotes, inline bold,
and inline code. No tables, no images, no embeds — keep the dependency surface
tiny.

Usage:
    python3 notion-page-write.py \\
        --parent-page <PARENT_PAGE_ID_32CHAR> \\
        --title "Week of 2026-05-13 — Action Items Rollup" \\
        --body /tmp/rollup-body.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:
    print("ERROR: 'requests' not installed. Run: python3 -m pip install requests", file=sys.stderr)
    sys.exit(1)

CONFIG_PATH = Path.home() / ".claude" / "skills" / "meetings-digest" / "config.json"
NOTION_VERSION = "2022-06-28"
NOTION_API = "https://api.notion.com/v1"
MAX_TEXT_LEN = 2000  # Notion's per-rich-text-fragment cap
RATE_LIMIT_RETRIES = 5


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        print(f"ERROR: config not found at {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)
    return json.loads(CONFIG_PATH.read_text())


def headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Markdown → Notion blocks
# ---------------------------------------------------------------------------

INLINE_BOLD = re.compile(r"\*\*(.+?)\*\*")
INLINE_CODE = re.compile(r"`([^`]+?)`")


def rich_text_from_inline(text: str) -> list[dict[str, Any]]:
    """
    Parse a single-line markdown fragment into Notion rich_text spans.
    Supports **bold** and `code` inline; everything else is plain.
    Splits long text into <=MAX_TEXT_LEN segments.
    """
    spans: list[dict[str, Any]] = []
    pos = 0

    pattern = re.compile(r"(\*\*[^*]+?\*\*|`[^`]+?`)")
    for m in pattern.finditer(text):
        if m.start() > pos:
            plain = text[pos:m.start()]
            for chunk in _chunk(plain, MAX_TEXT_LEN):
                spans.append({"type": "text", "text": {"content": chunk}})
        token = m.group(0)
        if token.startswith("**"):
            inner = token[2:-2]
            for chunk in _chunk(inner, MAX_TEXT_LEN):
                spans.append({
                    "type": "text",
                    "text": {"content": chunk},
                    "annotations": {"bold": True},
                })
        elif token.startswith("`"):
            inner = token[1:-1]
            for chunk in _chunk(inner, MAX_TEXT_LEN):
                spans.append({
                    "type": "text",
                    "text": {"content": chunk},
                    "annotations": {"code": True},
                })
        pos = m.end()

    if pos < len(text):
        rest = text[pos:]
        for chunk in _chunk(rest, MAX_TEXT_LEN):
            spans.append({"type": "text", "text": {"content": chunk}})

    if not spans:
        spans.append({"type": "text", "text": {"content": ""}})
    return spans


def _chunk(s: str, n: int) -> list[str]:
    if not s:
        return [""]
    return [s[i:i + n] for i in range(0, len(s), n)]


def md_to_blocks(md: str) -> list[dict[str, Any]]:
    """
    Minimal markdown → Notion blocks. Handles:
      - # ## ### headings
      - paragraphs
      - bulleted lists (`- ` or `* `)
      - numbered lists (`1. `)
      - blockquotes (`> `)
      - blank lines (separator between blocks)
    """
    blocks: list[dict[str, Any]] = []
    lines = md.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i].rstrip()

        if not line:
            i += 1
            continue

        if line.startswith("### "):
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {"rich_text": rich_text_from_inline(line[4:])},
            })
            i += 1
            continue

        if line.startswith("## "):
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": rich_text_from_inline(line[3:])},
            })
            i += 1
            continue

        if line.startswith("# "):
            blocks.append({
                "object": "block",
                "type": "heading_1",
                "heading_1": {"rich_text": rich_text_from_inline(line[2:])},
            })
            i += 1
            continue

        if line.startswith("> "):
            quote_lines = [line[2:]]
            i += 1
            while i < len(lines) and lines[i].startswith("> "):
                quote_lines.append(lines[i][2:])
                i += 1
            joined = "\n".join(quote_lines)
            blocks.append({
                "object": "block",
                "type": "quote",
                "quote": {"rich_text": rich_text_from_inline(joined)},
            })
            continue

        bullet_match = re.match(r"^[-*]\s+(.*)", line)
        if bullet_match:
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": rich_text_from_inline(bullet_match.group(1)),
                },
            })
            i += 1
            continue

        number_match = re.match(r"^\d+\.\s+(.*)", line)
        if number_match:
            blocks.append({
                "object": "block",
                "type": "numbered_list_item",
                "numbered_list_item": {
                    "rich_text": rich_text_from_inline(number_match.group(1)),
                },
            })
            i += 1
            continue

        # Paragraph (collect contiguous non-empty, non-block lines)
        para_lines = [line]
        i += 1
        while i < len(lines):
            nxt = lines[i].rstrip()
            if not nxt:
                break
            if (
                nxt.startswith("#") or nxt.startswith("> ")
                or re.match(r"^[-*]\s+", nxt) or re.match(r"^\d+\.\s+", nxt)
            ):
                break
            para_lines.append(nxt)
            i += 1

        text = " ".join(para_lines)
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": rich_text_from_inline(text)},
        })

    return blocks


# ---------------------------------------------------------------------------
# Notion API calls
# ---------------------------------------------------------------------------

def post_with_retry(url: str, token: str, body: dict[str, Any]) -> requests.Response:
    retries = 0
    while True:
        resp = requests.post(url, headers=headers(token), json=body, timeout=20)
        if resp.status_code == 429:
            if retries >= RATE_LIMIT_RETRIES:
                return resp
            time.sleep(float(resp.headers.get("Retry-After", "1")))
            retries += 1
            continue
        return resp


def patch_with_retry(url: str, token: str, body: dict[str, Any]) -> requests.Response:
    retries = 0
    while True:
        resp = requests.patch(url, headers=headers(token), json=body, timeout=20)
        if resp.status_code == 429:
            if retries >= RATE_LIMIT_RETRIES:
                return resp
            time.sleep(float(resp.headers.get("Retry-After", "1")))
            retries += 1
            continue
        return resp


def create_page(token: str, parent_page_id: str, title: str, blocks: list[dict[str, Any]]) -> tuple[bool, str]:
    """
    Create a page under parent_page_id with the given title and blocks.
    Notion caps children-per-request at 100; chunk if needed by creating the
    page with the first 100 blocks, then PATCHing additional batches.
    """
    first_batch = blocks[:100]
    rest = blocks[100:]

    payload = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "properties": {
            "title": {
                "title": [{"type": "text", "text": {"content": title}}]
            }
        },
        "children": first_batch,
    }

    resp = post_with_retry(f"{NOTION_API}/pages", token, payload)
    if resp.status_code != 200:
        try:
            body = resp.json()
            return False, f"{resp.status_code} {body.get('code', '')}: {body.get('message', resp.text[:300])}"
        except Exception:
            return False, f"{resp.status_code}: {resp.text[:300]}"

    page = resp.json()
    page_id = page.get("id", "")

    # Append remaining blocks (if any) in 100-block chunks
    for i in range(0, len(rest), 100):
        chunk = rest[i:i + 100]
        resp = patch_with_retry(
            f"{NOTION_API}/blocks/{page_id}/children",
            token,
            {"children": chunk},
        )
        if resp.status_code != 200:
            return False, f"Appending children failed at chunk {i//100 + 2}: {resp.status_code} {resp.text[:300]}"

    return True, page.get("url", "")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-page", help="Parent page ID. If omitted, reads from config.")
    parser.add_argument("--title", required=True, help="Page title")
    parser.add_argument("--body", required=True, help="Path to markdown body file")
    args = parser.parse_args()

    config = load_config()
    dest = config.get("destination", {})

    if dest.get("type") != "notion":
        print(f"ERROR: destination type is '{dest.get('type')}', not 'notion'", file=sys.stderr)
        return 1

    token = dest.get("notion_api_key")
    if not token:
        print("ERROR: notion_api_key missing in config", file=sys.stderr)
        return 1

    parent = args.parent_page or dest.get("notion_parent_page_id")
    if not parent:
        print("ERROR: parent page ID not provided and not in config", file=sys.stderr)
        return 1
    parent = parent.replace("-", "").strip()

    body_path = Path(args.body)
    if not body_path.exists():
        print(f"ERROR: body file not found: {body_path}", file=sys.stderr)
        return 1
    md = body_path.read_text()

    blocks = md_to_blocks(md)
    print(f"Parsed {len(blocks)} blocks from body. Creating page '{args.title[:80]}'...", file=sys.stderr)

    ok, info = create_page(token, parent, args.title, blocks)
    if not ok:
        print(f"ERROR: {info}", file=sys.stderr)
        return 2

    print(f"✓ Page created: {info}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
