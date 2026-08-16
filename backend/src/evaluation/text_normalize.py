
from __future__ import annotations

import re

import mistune
from bs4 import BeautifulSoup


def remove_markdown(md: str) -> str:
    html = mistune.html(md or "")
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(True):
        tag.unwrap()
    text = re.sub(r"[ \t]+", " ", str(soup))
    text = re.sub(r"\n+", "\n", text)
    return text.strip()
