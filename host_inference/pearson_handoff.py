"""Honest external-reader handoff; URL construction is not page verification."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from flask import render_template_string

PEARSON_HOSTS = {"ebooks.elibrary.in.pearson.com", "elibrary.in.pearson.com"}
PEARSON_PORTAL = "https://elibrary.in.pearson.com/"


def book_url(url: str) -> str:
    """Accept only Pearson HTTPS destinations and remove unsupported page suffixes."""
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in PEARSON_HOSTS or parsed.username:
        raise ValueError("Invalid Pearson reader destination.")
    return re.sub(r"/page/\d+", "", url)


def handoff(title: str, url: str, page: int) -> str:
    """Ask readers to open the book and navigate manually, without login claims."""
    return render_template_string(
        """<!doctype html><html lang="en"><meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{{ title }} — Pearson reader</title>
        <style>body{background:#090514;color:#eee;font:16px system-ui;margin:0;padding:7vh 6vw}
        main{max-width:640px;margin:auto}a{display:inline-block;background:#7045c1;color:white;
        padding:14px 22px;border-radius:12px;text-decoration:none}p{line-height:1.6}</style>
        <main><h1>{{ title }}</h1>
        <p>Open the book in Pearson, then go to <strong>page {{ page }}</strong>
        using the reader&#39;s page control.</p>
        <p>Sign in through the Pearson portal first. Then open the book and use its page
        control to select page {{ page }}. Pearson may restore your last-read page;
        reflowable books may use different numbering.</p>
        <p><a href="{{ portal }}" target="_blank" rel="noopener noreferrer">Sign in to Pearson eLibrary</a></p>
        <p><a href="{{ url }}" target="_blank" rel="noopener noreferrer">Open book in Pearson</a></p>
        <p>If the book link opens a blank page, return to the Pearson portal and search for
        <strong>{{ title }}</strong>. This reader does not provide a verified page link.</p>
        <p>Requested source page: {{ page }}. Check the book title and page before using the citation.</p>
        </main></html>""",
        title=title, url=book_url(url), portal=PEARSON_PORTAL, page=page,
    )
