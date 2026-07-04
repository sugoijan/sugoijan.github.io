#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from html import escape
from pathlib import Path
from urllib.parse import urljoin, urlsplit

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - fallback for older Python installs
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "links.toml"
OUTPUTS = {
    "index.html": ROOT / "index.html",
    "robots.txt": ROOT / "robots.txt",
    "sitemap.xml": ROOT / "sitemap.xml",
    "sitemap-pages.xml": ROOT / "sitemap-pages.xml",
}


def require_string(value: object, *, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} must be a non-empty string")
    return value.strip()


def optional_string(value: object, *, context: str) -> str:
    if value in (None, ""):
        return ""
    return require_string(value, context=context)


def string_list(value: object, *, context: str, default: list[str] | None = None) -> list[str]:
    if value in (None, ""):
        return list(default or [])

    if isinstance(value, str):
        return [require_string(value, context=context)]

    if not isinstance(value, list):
        raise ValueError(f"{context} must be a string or an array of strings")

    return [
        require_string(item, context=f"{context}[{index}]")
        for index, item in enumerate(value, start=1)
    ]


def absolute_url(value: object, *, context: str, normalize_directory: bool = False) -> str:
    url = require_string(value, context=context)
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{context} must be an absolute http(s) URL")

    if normalize_directory:
        path = parsed.path.rstrip("/")
        normalized = parsed._replace(path=path, query="", fragment="").geturl()
        return normalized + "/"

    return parsed._replace(fragment="").geturl()


def unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def load_config() -> dict[str, object]:
    try:
        raw = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Missing config file: {CONFIG_PATH.name}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"{CONFIG_PATH.name} is not valid TOML: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError(f"{CONFIG_PATH.name} must contain a top-level table")

    title = require_string(raw.get("title"), context="title")
    site_url = absolute_url(raw.get("site_url"), context="site_url", normalize_directory=True)
    intro = optional_string(raw.get("intro", ""), context="intro")
    extra_sitemaps = [
        absolute_url(value, context=f"extra_sitemaps[{index}]")
        for index, value in enumerate(string_list(raw.get("extra_sitemaps"), context="extra_sitemaps"), start=1)
    ]

    robots_value = raw.get("robots", {})
    if not isinstance(robots_value, dict):
        raise ValueError("robots must be a table")
    robots = {
        "user_agent": require_string(robots_value.get("user_agent", "*"), context="robots.user_agent"),
        "allow": string_list(robots_value.get("allow"), context="robots.allow", default=["/"]),
        "disallow": string_list(robots_value.get("disallow"), context="robots.disallow", default=[]),
    }

    sections_value = raw.get("sections", [])
    if not isinstance(sections_value, list):
        raise ValueError("sections must be an array of tables")

    sections: list[dict[str, object]] = []
    collected_sitemaps: list[str] = []
    collected_pages: list[str] = []
    for section_index, section_value in enumerate(sections_value, start=1):
        if not isinstance(section_value, dict):
            raise ValueError(f"section #{section_index} must be a table")

        section_title = require_string(
            section_value.get("title"),
            context=f"section #{section_index}.title",
        )
        entries_value = section_value.get("entries", [])
        if not isinstance(entries_value, list):
            raise ValueError(f"section #{section_index}.entries must be an array of tables")

        entries: list[dict[str, str]] = []
        for entry_index, entry_value in enumerate(entries_value, start=1):
            if not isinstance(entry_value, dict):
                raise ValueError(
                    f"section #{section_index} entry #{entry_index} must be a table"
                )

            label = require_string(
                entry_value.get("label"),
                context=f"section #{section_index} entry #{entry_index}.label",
            )
            href = require_string(
                entry_value.get("href"),
                context=f"section #{section_index} entry #{entry_index}.href",
            )
            note = optional_string(
                entry_value.get("note", ""),
                context=f"section #{section_index} entry #{entry_index}.note",
            )
            sitemap = optional_string(
                entry_value.get("sitemap", ""),
                context=f"section #{section_index} entry #{entry_index}.sitemap",
            )
            if sitemap:
                sitemap = absolute_url(
                    sitemap,
                    context=f"section #{section_index} entry #{entry_index}.sitemap",
                )
                collected_sitemaps.append(sitemap)
            else:
                # Entries without their own sitemap are listed in
                # sitemap-pages.xml, but only same-origin URLs are allowed
                # to appear in a sitemap served from site_url.
                resolved = urlsplit(urljoin(site_url, href))
                origin = urlsplit(site_url)
                if (resolved.scheme, resolved.netloc) == (origin.scheme, origin.netloc):
                    collected_pages.append(resolved._replace(fragment="").geturl())

            entries.append({"label": label, "href": href, "note": note, "sitemap": sitemap})

        sections.append({"title": section_title, "entries": entries})

    return {
        "title": title,
        "intro": intro,
        "site_url": site_url,
        "robots": robots,
        "sections": sections,
        "sitemaps": unique([urljoin(site_url, "sitemap-pages.xml"), *extra_sitemaps, *collected_sitemaps]),
        "pages": unique([site_url, *collected_pages]),
    }


def render_entry(entry: dict[str, str]) -> str:
    note_html = ""
    if entry["note"]:
        note_html = f'\n            <span class="note">{escape(entry["note"])}</span>'

    return (
        "        <li>\n"
        f'          <a href="{escape(entry["href"], quote=True)}">\n'
        f'            <span class="label">{escape(entry["label"])}</span>{note_html}\n'
        "          </a>\n"
        "        </li>"
    )


def render_section(section: dict[str, object]) -> str:
    entries = section["entries"]
    if not isinstance(entries, list) or not entries:
        return ""

    rendered_entries = "\n".join(render_entry(entry) for entry in entries)
    return (
        "      <section>\n"
        f"        <h2>{escape(str(section['title']))}</h2>\n"
        "        <ul>\n"
        f"{rendered_entries}\n"
        "        </ul>\n"
        "      </section>"
    )


def render_html(config: dict[str, object]) -> str:
    title = escape(str(config["title"]))
    intro_value = str(config["intro"])
    sections = [render_section(section) for section in config["sections"] if isinstance(section, dict)]
    sections_html = "\n".join(section for section in sections if section)
    if not sections_html:
        sections_html = (
            '      <p class="empty">No links configured yet. Edit <code>links.toml</code> '
            "and run <code>python3 scripts/build.py</code>.</p>"
        )

    header_lines = ["      <header>", f"        <h1>{title}</h1>"]
    if intro_value:
        header_lines.append(f"        <p>{escape(intro_value)}</p>")
    header_lines.append("      </header>")
    header_html = "\n".join(header_lines)

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    <style>
      :root {{
        color-scheme: light;
        --background: #fafafa;
        --foreground: #111111;
        --muted: #666666;
        --line: #d8d8d8;
      }}

      * {{
        box-sizing: border-box;
      }}

      body {{
        margin: 0;
        min-height: 100vh;
        padding: 4rem 1.25rem;
        background: var(--background);
        color: var(--foreground);
        font-family: ui-monospace, "SFMono-Regular", "SF Mono", Menlo, Consolas, monospace;
      }}

      main {{
        width: min(100%, 40rem);
        margin: 0 auto;
      }}

      h1,
      h2,
      p {{
        margin: 0;
      }}

      h1 {{
        font-size: 1rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }}

      header p {{
        margin-top: 0.8rem;
        max-width: 32rem;
        color: var(--muted);
        line-height: 1.6;
      }}

      section {{
        margin-top: 2rem;
      }}

      h2 {{
        margin-bottom: 0.75rem;
        color: var(--muted);
        font-size: 0.85rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }}

      ul {{
        list-style: none;
        padding: 0;
        margin: 0;
      }}

      li {{
        border-top: 1px solid var(--line);
      }}

      li:last-child {{
        border-bottom: 1px solid var(--line);
      }}

      a {{
        display: block;
        padding: 0.85rem 0;
        color: inherit;
        text-decoration: none;
      }}

      a:hover .label,
      a:focus-visible .label {{
        text-decoration: underline;
      }}

      .note {{
        display: block;
        margin-top: 0.2rem;
        color: var(--muted);
        font-size: 0.9rem;
      }}

      .empty {{
        margin-top: 2rem;
        padding-top: 1rem;
        border-top: 1px solid var(--line);
        color: var(--muted);
        line-height: 1.6;
      }}

      code {{
        font-family: inherit;
      }}
    </style>
  </head>
  <body>
    <main>
{header_html}
{sections_html}
    </main>
  </body>
</html>
"""


def render_robots(config: dict[str, object]) -> str:
    robots = config["robots"]
    if not isinstance(robots, dict):
        raise ValueError("robots config is invalid")

    lines = [
        "# Generated from links.toml by scripts/build.py",
        f"User-agent: {robots['user_agent']}",
    ]
    lines.extend(f"Allow: {value}" for value in robots["allow"])
    lines.extend(f"Disallow: {value}" for value in robots["disallow"])
    lines.extend(["", f"Sitemap: {urljoin(str(config['site_url']), 'sitemap.xml')}"])
    return "\n".join(lines) + "\n"


def render_sitemap_index(config: dict[str, object]) -> str:
    sitemaps = config["sitemaps"]
    if not isinstance(sitemaps, list):
        raise ValueError("sitemaps config is invalid")

    sitemap_items = "\n".join(
        "  <sitemap>\n"
        f"    <loc>{escape(url)}</loc>\n"
        "  </sitemap>"
        for url in sitemaps
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{sitemap_items}
</sitemapindex>
"""


def render_page_sitemap(config: dict[str, object]) -> str:
    pages = config["pages"]
    if not isinstance(pages, list):
        raise ValueError("pages config is invalid")

    url_items = "\n".join(
        "  <url>\n"
        f"    <loc>{escape(url)}</loc>\n"
        "  </url>"
        for url in pages
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{url_items}
</urlset>
"""


def build_outputs(config: dict[str, object]) -> dict[str, str]:
    return {
        "index.html": render_html(config),
        "robots.txt": render_robots(config),
        "sitemap.xml": render_sitemap_index(config),
        "sitemap-pages.xml": render_page_sitemap(config),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate the GitHub Pages entrypoint and metadata files from links.toml."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if any generated file is out of date.",
    )
    args = parser.parse_args()

    try:
        outputs = build_outputs(load_config())
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.check:
        stale = []
        for name, expected in outputs.items():
            path = OUTPUTS[name]
            current = path.read_text(encoding="utf-8") if path.exists() else ""
            if current != expected:
                stale.append(name)

        if stale:
            print(f"generated files are out of date: {', '.join(stale)}", file=sys.stderr)
            return 1

        print("generated files are up to date")
        return 0

    for name, content in outputs.items():
        OUTPUTS[name].write_text(content, encoding="utf-8")

    print(f"wrote {', '.join(outputs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
