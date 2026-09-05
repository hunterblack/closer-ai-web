#!/usr/bin/env python3
"""
Link checker for the Closer AI static site.

Two independent passes:

  internal  Resolves every site-relative href against the filesystem using the
            same rules Vercel serves with (cleanUrls, trailingSlash:false) plus
            the redirects declared in vercel.json. Also verifies that every
            "#fragment" actually exists as an id in the page it points at.
            No network, fully deterministic — safe to block a merge on.

  external  Requests every off-site URL and reports anything that does not
            answer. Depends on other people's servers, so it is scheduled and
            advisory rather than a merge gate.

The point of this file is the CTA that shipped pointing at an App Store listing
that returned 404 (PR #8). Internal checks catch a renamed id or a moved page;
external checks catch a URL that dies after we ship it.

Usage:
    python3 scripts/check-links.py --internal
    python3 scripts/check-links.py --external
    python3 scripts/check-links.py --internal --external
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Directories that are not part of the served site.
SKIP_DIRS = {".git", "node_modules", ".vercel", "design_handoff_website_redesign", "scripts"}

# Schemes we acknowledge but cannot verify by fetching.
UNCHECKABLE_SCHEMES = ("mailto:", "tel:", "sms:", "data:", "javascript:")

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
TIMEOUT = 25


class LinkExtractor(HTMLParser):
    """Collects link-ish attributes and every id on the page.

    HTMLParser drops comment contents, which is deliberate and load-bearing:
    the five legal/support pages intentionally keep the not-yet-live App Store
    URL commented out for launch day, and CI must not fail on it.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []  # (attr_value, tag, rel)
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        # <a name="..."> is a legacy fragment target.
        if tag == "a" and a.get("name"):
            self.ids.add(a["name"])
        rel = (a.get("rel") or "").lower()
        for attr in ("href", "src", "action"):
            val = a.get(attr)
            if val:
                self.links.append((val.strip(), tag, rel))

    # Void elements never hit handle_startendtag separately in all cases.
    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


def html_files():
    out = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            if fn.endswith(".html"):
                out.append(os.path.join(dirpath, fn))
    return sorted(out)


def load_redirects():
    """Read vercel.json redirects so internal checks match what is served."""
    path = os.path.join(ROOT, "vercel.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        cfg = json.load(f)
    return [(r["source"], r["destination"]) for r in cfg.get("redirects", []) if "source" in r]


def parse(path):
    with open(path, encoding="utf-8") as f:
        p = LinkExtractor()
        p.feed(f.read())
        return p


def resolve_internal(target, source_file, redirects):
    """Map a site path to a file on disk, mirroring Vercel's cleanUrls.

    Returns the resolved filesystem path, or None if nothing would be served.
    """
    for src, dest in redirects:
        if target == src:
            target = dest
            break

    if target.startswith("/"):
        base = ROOT
        rel = target.lstrip("/")
    else:
        base = os.path.dirname(source_file)
        rel = target

    candidate = os.path.normpath(os.path.join(base, rel))

    # Never let a link escape the repo.
    if not candidate.startswith(ROOT):
        return None

    if os.path.isfile(candidate):
        return candidate
    # cleanUrls: /privacy is served from privacy.html
    if os.path.isfile(candidate + ".html"):
        return candidate + ".html"
    if os.path.isdir(candidate) and os.path.isfile(os.path.join(candidate, "index.html")):
        return os.path.join(candidate, "index.html")
    return None


def check_internal():
    redirects = load_redirects()
    files = html_files()
    # id sets are needed for cross-page fragment checks.
    parsed = {f: parse(f) for f in files}
    failures = []
    checked = 0

    for path in files:
        rel_source = os.path.relpath(path, ROOT)
        for raw, tag, rel in parsed[path].links:
            if raw.startswith(("http://", "https://", "//")) or raw.startswith(UNCHECKABLE_SCHEMES):
                continue

            target, _, fragment = raw.partition("#")
            target = target.split("?")[0]  # strip cache-busting query
            checked += 1

            if not target:
                # Pure "#fragment" — same page.
                resolved = path
            else:
                resolved = resolve_internal(target, path, redirects)
                if resolved is None:
                    failures.append(f"{rel_source}: {raw} -> no such file")
                    continue

            if fragment:
                target_parsed = parsed.get(resolved)
                if target_parsed is None and resolved.endswith(".html"):
                    target_parsed = parse(resolved)
                if target_parsed is not None and fragment not in target_parsed.ids:
                    failures.append(
                        f'{rel_source}: {raw} -> "{os.path.relpath(resolved, ROOT)}" has no id="{fragment}"'
                    )

    return checked, failures


def fetch_status(url, method="GET"):
    req = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, None
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:  # network/DNS/TLS
        return None, str(e)


def check_external():
    files = html_files()
    # url -> set of "file (context)" so one report line covers every occurrence.
    targets = {}
    for path in files:
        rel_source = os.path.relpath(path, ROOT)
        for raw, tag, rel in parse(path).links:
            if not raw.startswith(("http://", "https://")):
                continue
            # preconnect/dns-prefetch name an origin to warm up, not a document
            # to fetch. fonts.gstatic.com answers 404 at "/" by design.
            if "preconnect" in rel or "dns-prefetch" in rel:
                continue
            targets.setdefault(raw, {"sources": set(), "is_form": False})
            targets[raw]["sources"].add(rel_source)
            if tag == "form":
                targets[raw]["is_form"] = True

    failures = []
    for url in sorted(targets):
        info = targets[url]
        status, err = fetch_status(url)
        where = ", ".join(sorted(info["sources"]))

        if err is not None:
            failures.append(f"{url} -> unreachable ({err})  [{where}]")
            continue

        ok = 200 <= status < 400
        # A form action is a POST endpoint; 405 to our GET means it is alive.
        if info["is_form"] and status == 405:
            ok = True

        print(f"  {status}  {url}")
        if not ok:
            failures.append(f"{url} -> HTTP {status}  [{where}]")

    return len(targets), failures


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--internal", action="store_true", help="check on-site links and fragments (no network)")
    ap.add_argument("--external", action="store_true", help="check off-site URLs (network)")
    args = ap.parse_args()

    if not args.internal and not args.external:
        args.internal = args.external = True

    failed = False

    if args.internal:
        print("Internal links and fragments")
        count, failures = check_internal()
        if failures:
            failed = True
            for f in failures:
                print(f"  FAIL  {f}")
        print(f"  {count} checked, {len(failures)} broken\n")

    if args.external:
        print("External URLs")
        count, failures = check_external()
        if failures:
            failed = True
            print()
            for f in failures:
                print(f"  FAIL  {f}")
        print(f"  {count} checked, {len(failures)} failing\n")

    if failed:
        print("Link check FAILED")
        return 1
    print("Link check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
