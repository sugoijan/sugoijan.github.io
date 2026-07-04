# sugoijan.github.io

This repo stays intentionally simple: GitHub Pages serves generated static files, and the source of truth is `links.toml`.

Generated files (not committed; built locally or in CI):

- `index.html`
- `robots.txt`
- `sitemap.xml`
- `sitemap-pages.xml`

## Update the menu

Edit `links.toml`. A link entry looks like this:

```toml
[[sections.entries]]
label = "My Project"
href = "https://example.com"
note = "Optional short description"
sitemap = "https://example.com/sitemap.xml" # Optional
```

The `sitemap` field is optional. If present, it is added to the generated `sitemap.xml` sitemap index (it must live on the same host as `site_url`, per the sitemaps protocol). If absent, the entry's `href` is listed directly in `sitemap-pages.xml` instead — unless it points to another host, which a sitemap served from this site is not allowed to include.

You can also add top-level `extra_sitemaps = ["https://example.com/sitemap.xml"]` entries if something should be indexed without appearing in the menu.

Then rebuild the site:

```sh
python3 scripts/build.py
```

## Preview locally

```sh
./scripts/preview.sh
```

This rebuilds the generated files and serves the repo on `http://127.0.0.1:8000`.

## Check generated output

```sh
python3 scripts/build.py --check
```

That is useful locally to confirm the generated files on disk match `links.toml`.

## Deploy

Pushing to `main` triggers `.github/workflows/deploy.yml`, which runs `scripts/build.py` and deploys only the generated files to GitHub Pages (source must be set to "GitHub Actions" in the repo settings). Pull requests run the build as a validation check without deploying.
