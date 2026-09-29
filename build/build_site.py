#!/usr/bin/env python3
"""Rebuild the old FrontPage/Word malcolmandnuran.com site as a clean modern static site.

Reads from ../Web_site (left untouched) plus new tales in build/tales, and writes ../new_site.
Re-runnable: the output folder is wiped and regenerated each time.
"""
import hashlib
import html
import os
import re
import shutil
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from PIL import Image, ImageOps

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
SRC = PROJECT / "Web_site" / "NuransRe" / "web page" / "mals web page"
MK = SRC / "malcolmk"
OLD = SRC / "old web files"
OUT = PROJECT / "new_site"
ASSETS = HERE / "assets"
NEW_TALES = HERE / "tales"
DRIVE_VIDEOS = HERE / "drive_videos.txt"
DOMAIN = "www.malcolmandnuran.com"

FULL_PX = 1600
MED_PX = 900

report = []


def warn(msg):
    report.append(msg)


# --------------------------------------------------------------------------- utils

def read(path):
    data = Path(path).read_bytes()
    for enc in ("utf-8", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    return data.decode("cp1252", errors="replace")


def slugify(text):
    text = html.unescape(text).lower().replace("&", " and ").replace("'", "").replace("’", "")
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "page"


def esc(text):
    return html.escape(text, quote=True)


def clean_text(text):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", text)).replace("\xa0", " ").split())


def page_title(src):
    m = re.search(r"<title>(.*?)</title>", src, re.S | re.I)
    return clean_text(m.group(1)) if m else ""


def resolve(base_dir, href):
    """Resolve a (possibly URL-encoded) relative link to a real file, tolerating case mismatches."""
    if not href or re.match(r"^[a-z]+:", href, re.I) or href.startswith("#"):
        return None
    path = unquote(urlsplit(href).path)
    if not path:
        return None
    p = (Path(base_dir) / path).resolve()
    if p.is_file():
        return p
    # case-insensitive walk
    cur = Path(base_dir).resolve()
    for part in Path(path).parts:
        if part == "..":
            cur = cur.parent
            continue
        if part in (".", ""):
            continue
        if not cur.is_dir():
            return None
        match = [c for c in cur.iterdir() if c.name.lower() == part.lower()]
        if not match:  # e.g. "Nuran's Scones.htm" saved to disk as "Nuran_s Scones.htm"
            match = [c for c in cur.iterdir() if norm(c.name) == norm(part)]
        if not match:
            return None
        cur = match[0]
    return cur if cur.is_file() else None


_IMG_INDEX = None


# Images the old pages use under a name the file no longer has.
IMAGE_RENAMES = {"dogs.jpg": "the dogs.jpg"}

# Images the old pages use that aren't anywhere in Web_site/ (lost before the download); left out quietly.
LOST_IMAGES = {"mal & christ on trikes.jpg", "malcolmjulianshrink.jpg", "billcakecutting.jpg", "jimjules.jpg",
               "mal_ bike_web.jpg", "maljulianyasmine.jpg", "grandpa&grandma.jpg"}


def image_name(src):
    return unquote(urlsplit(src).path).replace("\\", "/").rsplit("/", 1)[-1].lower()


def find_image(src):
    """Fallback for pages whose image paths broke when folders were moved: match by file name."""
    global _IMG_INDEX
    if _IMG_INDEX is None:
        _IMG_INDEX = {}
        for p in sorted(SRC.rglob("*")):
            if p.suffix.lower() in IMG_EXT and "_vti" not in str(p):
                _IMG_INDEX.setdefault(p.name.lower(), p)
    name = image_name(src)
    name = IMAGE_RENAMES.get(name, name)
    return _IMG_INDEX.get(name) if name else None


DATE_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})")
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def split_date(text):
    m = DATE_RE.search(text)
    if not m:
        return text.strip(), ""
    d, mo, y = (int(x) for x in m.groups())
    if y < 100:
        y += 2000
    rest = (text[: m.start()] + text[m.end():]).strip(" -–")
    return rest, f"{d} {MONTHS[mo - 1]} {y}" if 1 <= mo <= 12 else m.group(0)


# --------------------------------------------------------------------------- media

class Media:
    """Copies/optimises images, videos and documents into new_site/media, deduplicated by content."""

    def __init__(self):
        self.done = {}  # source path -> result
        self.by_hash = {}

    def _hash(self, path):
        return hashlib.sha1(Path(path).read_bytes()).hexdigest()[:12]

    def image(self, path):
        """Return dict(full=..., med=..., w=, h=) paths relative to site root, or None."""
        path = Path(path)
        if path in self.done:
            return self.done[path]
        h = self._hash(path)
        if h in self.by_hash:
            self.done[path] = self.by_hash[h]
            return self.by_hash[h]
        stem = slugify(path.stem)[:40]
        try:
            im = Image.open(path)
            im = ImageOps.exif_transpose(im)
        except Exception as e:  # noqa: BLE001
            warn(f"unreadable image {path}: {e}")
            self.done[path] = None
            return None
        if path.suffix.lower() == ".gif":
            name = f"media/img/{stem}-{h[:6]}.gif"
            shutil.copy2(path, OUT / name)
            res = dict(full=name, med=name, w=im.width, h=im.height)
        else:
            im = im.convert("RGB")
            full = im.copy()
            full.thumbnail((FULL_PX, FULL_PX), Image.LANCZOS)
            name = f"media/img/{stem}-{h[:6]}.jpg"
            full.save(OUT / name, "JPEG", quality=82, optimize=True, progressive=True)
            med = im.copy()
            med.thumbnail((MED_PX, MED_PX), Image.LANCZOS)
            mname = f"media/img/m/{stem}-{h[:6]}.jpg"
            med.save(OUT / mname, "JPEG", quality=78, optimize=True, progressive=True)
            res = dict(full=name, med=mname, w=med.width, h=med.height)
        self.done[path] = self.by_hash[h] = res
        return res

    def file(self, path, sub, name=None):
        path = Path(path)
        if path in self.done:
            return self.done[path]
        name = name or (slugify(path.stem) + path.suffix.lower())
        rel = f"media/{sub}/{name}"
        shutil.copy2(path, OUT / rel)
        self.done[path] = rel
        return rel


MEDIA = Media()
IMG_EXT = {".jpg", ".jpeg", ".png", ".gif"}
DOC_EXT = {".pdf"}
VID_EXT = {".mp4", ".wmv"}


# --------------------------------------------------------------------------- HTML cleaning

SKIP_CONTENT = {"head", "style", "script", "xml", "title", "select", "noscript", "object", "embed",
                "applet", "iframe", "map", "textarea", "button"}
BLOCK = {"p": "p", "h1": "h2", "h2": "h2", "h3": "h3", "h4": "h3", "h5": "h3", "h6": "h3",
         "ul": "ul", "ol": "ol", "li": "li", "blockquote": "blockquote",
         "div": "div", "td": "div", "th": "div", "center": "div", "dl": "div", "dd": "div", "dt": "div"}
INLINE = {"b": "strong", "strong": "strong", "i": "em", "em": "em", "sup": "sup", "sub": "sub"}
VOID_SKIP = {"input", "meta", "link", "area", "param", "hr"}


class Cleaner(HTMLParser):
    def __init__(self, base_dir, link_map, drop_image=None):
        super().__init__(convert_charrefs=True)
        self.base_dir = Path(base_dir)
        self.link_map = link_map  # resolved Path -> site-relative url (without root prefix)
        self.drop_image = drop_image or (lambda p: False)
        self.out = []
        self.stack = []  # open output tags (or None for dropped)
        self.skip = 0
        self.images = []

    # --- helpers
    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        a = {k.lower(): (v or "") for k, v in attrs}
        if self.skip:
            if tag in SKIP_CONTENT:
                self.skip += 1
            return
        if tag in SKIP_CONTENT:
            self.skip = 1
            return
        if tag == "br":
            self.out.append("<br>")
            return
        if tag in VOID_SKIP:
            return
        if tag in ("img", "v:imagedata"):
            self.out.append(self.img(a))
            return
        if tag == "a":
            href = self.link(a.get("href", ""))
            if href:
                ext = " target=\"_blank\" rel=\"noopener\"" if href.startswith("http") else ""
                self.out.append(f'<a href="{esc(href)}"{ext}>')
                self.stack.append("a")
            elif a.get("href"):
                # link to an old navigation page or dead domain: drop it, text included if short
                self.stack.append(("drop", len(self.out)))
            else:
                self.stack.append(None)
            return
        if tag in BLOCK:
            t = BLOCK[tag]
            self.out.append(f"<{t}>")
            self.stack.append(t)
            return
        if tag in INLINE:
            t = INLINE[tag]
            self.out.append(f"<{t}>")
            self.stack.append(t)
            return
        if tag in ("tr", "table", "tbody", "thead", "form", "body", "html", "span", "font",
                   "u", "o:p", "st1:city", "st1:place", "st1:country-region", "st1:state",
                   "st1:street", "st1:address", "st1:personname", "nobr", "small", "big"):
            self.stack.append(None)
            return
        # anything else (vml shapes, etc.): transparent
        self.stack.append(None)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self.skip:
            if tag in SKIP_CONTENT:
                self.skip -= 1
            return
        if tag in ("br", "img", "v:imagedata") or tag in VOID_SKIP:
            return
        # pop to matching entry (tolerant of broken nesting)
        want = BLOCK.get(tag) or INLINE.get(tag) or ("a" if tag == "a" else None)
        for i in range(len(self.stack) - 1, -1, -1):
            if want is None or self.stack[i] == want:
                closing = self.stack[i:]
                del self.stack[i:]
                for t in reversed(closing):
                    if isinstance(t, tuple):
                        text = clean_text("".join(self.out[t[1]:]))
                        if len(text) <= 40 and "<img" not in "".join(self.out[t[1]:]):
                            del self.out[t[1]:]
                    elif t:
                        self.out.append(f"</{t}>")
                return

    def handle_data(self, data):
        if not self.skip:
            self.out.append(html.escape(data.replace("\r", ""), quote=False))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag.lower() not in ("br", "img", "v:imagedata") and tag.lower() not in VOID_SKIP:
            self.handle_endtag(tag)

    def link(self, href):
        href = href.strip()
        if not href or href.startswith("#") or href.lower().startswith(("mailto:", "javascript:")):
            return None
        if re.match(r"^https?://", href, re.I):
            host = urlsplit(href).netloc.lower()
            if "malcolmandnuran" in host or "nuransrecipe" in host:
                return None  # dead links to the old domains
            return href
        target = resolve(self.base_dir, href)
        if target is None:
            return None
        if target in self.link_map:
            return "@ROOT@" + self.link_map[target]
        ext = target.suffix.lower()
        if ext in IMG_EXT:
            r = MEDIA.image(target)
            return "@ROOT@" + r["full"] if r else None
        if ext in DOC_EXT:
            return "@ROOT@" + MEDIA.file(target, "docs")
        if ext in VID_EXT:
            return "@ROOT@" + MEDIA.file(target, "video")
        return None  # old navigation page

    def img(self, a):
        src = a.get("src", "")
        target = resolve(self.base_dir, src) or find_image(src)
        if target is None:
            if src and not src.startswith("http") and image_name(src) not in LOST_IMAGES:
                warn(f"missing image '{unquote(src)}' in {self.base_dir.relative_to(SRC)}")
            return ""
        if target.suffix.lower() not in IMG_EXT or self.drop_image(target):
            return ""
        try:
            with Image.open(target) as im:
                w, h = im.size
        except Exception:  # noqa: BLE001
            w = h = 0
        if w and w < 90 and h < 90:
            return ""  # buttons, spacers, bullets
        r = MEDIA.image(target)
        if not r:
            return ""
        self.images.append(r)
        alt = a.get("alt") or a.get("longdesc") or ""
        if not alt or alt.lower().endswith((".jpg", ".gif")):
            alt = ""
        align = a.get("align", "").lower()
        try:
            shown = int(re.sub(r"\D", "", a.get("width", "")) or 0)
        except ValueError:
            shown = 0
        cls = "photo"
        if align in ("left", "right") or (shown and shown <= 320):
            cls += " fl" if align == "left" else " fr"
        return (f'<a class="{cls}" href="@ROOT@{r["full"]}"'
                f'{f" data-caption=\"{esc(alt)}\"" if alt else ""}>'
                f'<img src="@ROOT@{r["med"]}" width="{r["w"]}" height="{r["h"]}" '
                f'alt="{esc(alt)}" loading="lazy" decoding="async"></a>')


def clean_html(src, base_dir, link_map, title=None, drop_image=None):
    body = re.search(r"<body\b[^>]*>(.*)</body>", src, re.S | re.I)
    body = body.group(1) if body else src
    # Word conditional/VML blocks live inside comments and are dropped by the parser.
    body = re.sub(r"<!\[if [^\]]*\]>|<!\[endif\]>", "", body, flags=re.I)
    c = Cleaner(base_dir, link_map, drop_image)
    c.feed(body)
    c.close()
    out = "".join(c.out)
    for t in reversed([t for t in c.stack if isinstance(t, str)]):
        out += f"</{t}>"
    return tidy(out, title), c.images


EMPTY_INLINE = re.compile(r"<(strong|em|sup|sub)>(\s|&nbsp;|\xa0)*</\1>")


def tidy(s, title=None):
    s = s.replace("\xa0", " ")
    s = re.sub(r"[ \t]*\n[ \t]*", " ", s)
    s = re.sub(r" {2,}", " ", s)
    for _ in range(3):
        s = EMPTY_INLINE.sub(" ", s)
        s = re.sub(r"<a [^>]*>\s*</a>", "", s)
        s = re.sub(r"<(p|div|li|h2|h3|blockquote)>(\s|<br>)*</\1>", "", s)
        s = re.sub(r"<(ul|ol)>\s*</\1>", "", s)
    # unwrap divs that only hold other blocks; turn text-bearing divs into paragraphs
    s = re.sub(r"<div>\s*(<(?:p|h2|h3|ul|ol|blockquote)>)", r"\1", s)
    s = re.sub(r"(</(?:p|h2|h3|ul|ol|blockquote)>)\s*</div>", r"\1", s)
    s = s.replace("<div>", "<p>").replace("</div>", "</p>")
    # nested <p> produced by the conversion
    for _ in range(3):
        s = re.sub(r"<p>(\s*<p>)", r"\1", s)
        s = re.sub(r"(</p>\s*)</p>", r"\1", s)
        s = re.sub(r"<p>(\s*<(?:h2|h3|ul|ol|blockquote)>)", r"\1", s)
        s = re.sub(r"(</(?:h2|h3|ul|ol|blockquote)>\s*)</p>", r"\1", s)
    s = re.sub(r"(<br>\s*){3,}", "<br><br>", s)
    s = re.sub(r"<p>(\s|<br>)+", "<p>", s)
    s = re.sub(r"(\s|<br>)+</p>", "</p>", s)
    s = re.sub(r"<(p|h2|h3)>\s*</\1>", "", s)
    # drop leading blocks that just repeat the title or old site banners
    if title:
        key = norm(title)
        for _ in range(4):
            m = re.match(r"\s*<(p|h2|h3)>(.*?)</\1>", s, re.S)
            if not m:
                break
            txt = norm(clean_text(m.group(2)))
            if "<img" in m.group(2) or txt not in (key, "tarpeena tales", norm(title.split(":")[0])) and not (
                    txt and key.startswith(txt)):
                break
            s = s[m.end():]
    s = re.sub(r"\s*(<(?:p|h2|h3|ul|ol|li|blockquote)>)", r"\n\1", s)
    return s.strip()


def norm(t):
    return re.sub(r"[^a-z0-9]", "", t.lower())


# --------------------------------------------------------------------------- templating

NAV = [("index.html", "Home"), ("tales/index.html", "Tarpeena Tales"),
       ("discoveries.html", "Great Discoveries"), ("recipes/index.html", "Recipes"),
       ("greyhounds.html", "Greyhounds"), ("photos/index.html", "Photos")]


def render(rel_path, title, content, section=None, description="", body_class="", root=None):
    depth = rel_path.count("/")
    root = "../" * depth if root is None else root
    nav = "".join(
        f'<li><a href="{root}{href}"{" aria-current=\"page\"" if section == href else ""}>{label}</a></li>'
        for href, label in NAV)
    full_title = f"{title} · Malcolm & Nuran" if title != "Malcolm & Nuran" else title
    content = content.replace("@ROOT@", root)
    page = f"""<!doctype html>
<html lang="en-AU">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(description or 'Malcolm and Nuran Keenan – Tarpeena Tales, recipes, greyhounds and family photos.')}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,600;0,700;1,400&display=swap">
<link rel="stylesheet" href="{root}assets/css/site.css">
<link rel="icon" href="{root}assets/favicon.svg" type="image/svg+xml">
<script src="{root}assets/js/site.js" defer></script>
</head>
<body class="{body_class}">
<a class="skip" href="#main">Skip to content</a>
<header class="site-header">
  <div class="wrap bar">
    <a class="brand" href="{root}index.html"><span class="brand-mark" aria-hidden="true">M&amp;N</span> Malcolm &amp; Nuran</a>
    <button class="nav-toggle" aria-expanded="false" aria-controls="site-nav">Menu</button>
    <nav id="site-nav" class="site-nav" aria-label="Main"><ul>{nav}</ul></nav>
  </div>
</header>
<main id="main">
{content}
</main>
<footer class="site-footer">
  <div class="wrap">
    <p>Malcolm &amp; Nuran Keenan · Tarpeena, South Australia</p>
    <p class="muted">Stories, recipes and photos shared with family and friends.</p>
  </div>
</footer>
</body>
</html>
"""
    dest = OUT / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(page, encoding="utf-8")


def card(href, title, text="", img=None, meta=""):
    pic = (f'<img src="@ROOT@{img["med"]}" alt="" loading="lazy" width="{img["w"]}" height="{img["h"]}">'
           if img else '<span class="card-ph" aria-hidden="true"></span>')
    return (f'<a class="card" href="{href}"><div class="card-img">{pic}</div><div class="card-body">'
            f'{f"<p class=\"meta\">{esc(meta)}</p>" if meta else ""}<h3>{esc(title)}</h3>'
            f'{f"<p>{esc(text)}</p>" if text else ""}</div></a>')


def excerpt(content, n=150):
    t = clean_text(content)
    return (t[:n].rsplit(" ", 1)[0] + "…") if len(t) > n else t


# --------------------------------------------------------------------------- index parsing

def index_links(path):
    """Return [(resolved_path, link_text)] for <a> tags in an index page, in order, deduped."""
    src = read(path)
    seen = {}
    order = []
    for m in re.finditer(r"<a\b[^>]*href=\"([^\"]*)\"[^>]*>(.*?)</a>", src, re.S | re.I):
        target = resolve(Path(path).parent, m.group(1))
        text = clean_text(m.group(2))
        if target is None:
            continue
        if target in seen:
            seen[target] = (seen[target] + " " + text).strip()
        else:
            seen[target] = text
            order.append(target)
    return [(p, seen[p]) for p in order]


# --------------------------------------------------------------------------- sections

def build_tales(link_map):
    vols = []
    # Volume 1: numbered tales
    v1 = []
    for p, text in index_links(MK / "Tarpeena Tales" / "Tarpeena_Tales_Archive.htm"):
        name, date = split_date(text)
        m = re.search(r"(\d+)\s*$", name)
        v1.append(dict(src=p, title=name, date=date, num=int(m.group(1)) if m else 999))
    v1.sort(key=lambda t: t["num"])
    vols.append(dict(n=1, title="Volume 1", years="2005 – 2007", tales=v1))

    extra2 = []
    v2 = []
    for p, text in index_links(MK / "vol2index.htm"):
        name, date = split_date(text)
        v2.append(dict(src=p, title=name or page_title(read(p)), date=date))
    for p, text in index_links(MK / "Tales2.htm"):
        if p.suffix.lower() == ".wmv":
            extra2.append((MEDIA.file(p, "video"), "Mal's 180 (video, .wmv download)"))
    vols.append(dict(n=2, title="Volume 2", years="2009 – 2010", tales=v2, extra=extra2))

    v3 = []
    for p, text in index_links(MK / "Volume3Index.htm"):
        name, date = split_date(text)
        v3.append(dict(src=p, title=name or page_title(read(p)), date=date))
    vols.append(dict(n=3, title="Volume 3", years="2011 – 2012", tales=v3))

    v4 = []
    for p, text in index_links(MK / "volume4index.htm"):
        name, date = split_date(text or p.stem)
        v4.append(dict(src=p, title=page_title(read(p)) or name, date=date))
    v4 += new_tales()
    vols.append(dict(n=4, title="Volume 4", years="2021 –", tales=v4))

    # assign URLs first so cross-links between tales resolve
    for v in vols:
        used = set()
        for t in v["tales"]:
            slug = slugify(t["title"])
            while slug in used:
                slug += "-2"
            used.add(slug)
            t["url"] = f"tales/vol{v['n']}/{slug}.html"
            link_map[t["src"]] = t["url"]
    return vols


def new_tales():
    """Tales written since the move to GitHub: build/tales/*.txt, oldest first by date.

    Each file starts with 'title:' and 'date:' (YYYY-MM-DD) lines, then a blank line, then the story.
    Paragraphs are separated by blank lines; *italic* and **bold** work; a line like
    'photo: tiger.jpg | A caption' shows a photo kept next to the .txt file.
    """
    tales = []
    for p in sorted(NEW_TALES.glob("*.txt")):
        head, _, body = p.read_text(encoding="utf-8").partition("\n\n")
        meta = dict(line.split(":", 1) for line in head.splitlines() if ":" in line)
        meta = {k.strip().lower(): v.strip() for k, v in meta.items()}
        if not meta.get("title") or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", meta.get("date", "")):
            sys.exit(f"{p.name}: needs 'title:' and 'date: YYYY-MM-DD' lines at the top")
        y, mo, d = (int(x) for x in meta["date"].split("-"))
        tales.append(dict(src=p, title=meta["title"], date=f"{d} {MONTHS[mo - 1]} {y}",
                          sort=meta["date"], text=body))
    return sorted(tales, key=lambda t: t["sort"])


def inline(text):
    text = esc(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    return re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)


def text_to_html(text, base_dir):
    out, imgs = [], []
    for block in re.split(r"\n\s*\n", text.strip()):
        m = re.fullmatch(r"photo:\s*([^|]+?)\s*(?:\|\s*(.*))?", block.strip(), re.S)
        if m:
            path = base_dir / m.group(1)
            if not path.is_file():
                sys.exit(f"photo not found: {path}")
            r = MEDIA.image(path)
            imgs.append(r)
            cap = " ".join((m.group(2) or "").split())
            out.append(f'<p><a class="photo" href="@ROOT@{r["full"]}"{f" data-caption=\"{esc(cap)}\"" if cap else ""}>'
                       f'<img src="@ROOT@{r["med"]}" width="{r["w"]}" height="{r["h"]}" alt="{esc(cap)}" '
                       f'loading="lazy" decoding="async"></a></p>')
        else:
            out.append("<p>" + "<br>".join(inline(line) for line in block.strip().splitlines()) + "</p>")
    return "\n".join(out), imgs


def render_tales(vols, link_map):
    flat = [(v, t) for v in vols for t in v["tales"]]
    for i, (v, t) in enumerate(flat):
        if "text" in t:
            content, imgs = text_to_html(t["text"], t["src"].parent)
        else:
            content, imgs = clean_html(read(t["src"]), t["src"].parent, link_map, title=t["title"])
        t["img"] = imgs[0] if imgs else None
        if not t["date"]:  # many tales end with a date line like "20.11.05"
            m = re.findall(r"<p>(?:<strong>)?\s*(\d{1,2}\.\d{1,2}\.\d{2,4})\s*(?:</strong>)?</p>", content)
            if m:
                t["date"] = split_date(m[-1])[1]
        t["excerpt"] = excerpt(content)
        prev_ = flat[i - 1][1] if i > 0 else None
        next_ = flat[i + 1][1] if i + 1 < len(flat) else None
        pn = '<nav class="prevnext" aria-label="More tales">'
        pn += (f'<a class="prev" href="@ROOT@{prev_["url"]}"><span>← Previous</span>{esc(prev_["title"])}</a>'
               if prev_ else "<span></span>")
        pn += (f'<a class="next" href="@ROOT@{next_["url"]}"><span>Next →</span>{esc(next_["title"])}</a>'
               if next_ else "<span></span>")
        pn += "</nav>"
        meta = f'<a href="@ROOT@tales/index.html#vol{v["n"]}">Tarpeena Tales · {v["title"]}</a>'
        if t["date"]:
            meta += f' · <time>{esc(t["date"])}</time>'
        page = (f'<article class="wrap narrow prose">'
                f'<header class="page-head"><p class="kicker">{meta}</p><h1>{esc(t["title"])}</h1></header>'
                f'{content}</article><div class="wrap narrow">{pn}</div>')
        render(t["url"], t["title"], page, section="tales/index.html",
               description=t["excerpt"])

    parts = ['<section class="hero small"><div class="wrap"><p class="kicker">From Tarpeena, South Australia</p>'
             '<h1>Tarpeena Tales</h1><p class="lede">Malcolm\'s occasional dispatches from country life – '
             'cycling the pines, home brew, darts, dogs, family visits and the odd adventure further afield.</p>'
             '</div></section><div class="wrap">']
    parts.append('<nav class="vol-jump" aria-label="Volumes">' + "".join(
        f'<a href="#vol{v["n"]}">{v["title"]}</a>' for v in vols) + "</nav>")
    for v in reversed(vols):
        parts.append(f'<section class="volume" id="vol{v["n"]}"><h2>{v["title"]} <span class="muted">{v["years"]}</span></h2>'
                     '<div class="grid cards">')
        for t in v["tales"]:
            parts.append(card(f'@ROOT@{t["url"]}', t["title"], t["excerpt"], t["img"], t["date"]))
        parts.append("</div>")
        for href, label in v.get("extra", []):
            parts.append(f'<p class="note"><a href="@ROOT@{href}">{esc(label)}</a></p>')
        parts.append("</section>")
    parts.append("</div>")
    render("tales/index.html", "Tarpeena Tales", "".join(parts), section="tales/index.html",
           description="Malcolm's Tarpeena Tales – stories of country life in Tarpeena, South Australia.")


def build_discoveries(link_map):
    p = MK / "Great Discoveries.htm"
    content, imgs = clean_html(read(p), p.parent, link_map, title="Great Discoveries")
    page = (f'<article class="wrap narrow prose"><header class="page-head"><p class="kicker">A memoir</p>'
            f'<h1>Great Discoveries</h1></header>{content}</article>')
    render("discoveries.html", "Great Discoveries", page, section="discoveries.html",
           description=excerpt(content))
    return imgs[0] if imgs else None, excerpt(content, 160)


def build_recipes(link_map):
    idx = MK / "nuransrecipes" / "index.html"
    src = read(idx)
    cats = []
    for m in re.finditer(r"<option[^>]*value=\"([^\"]*)\"[^>]*>(.*?)(?=<option|</select)", src, re.S | re.I):
        val, text = m.group(1), clean_text(m.group(2))
        if val == "none":
            name = text.strip(" -")
            if name and "select" not in name.lower():
                cats.append(dict(name=name.title().replace("'S", "'s").replace("&Amp;", "&"), items=[]))
            continue
        p = resolve(idx.parent, val)
        if p is None:
            warn(f"recipe link missing: {val}")
            continue
        cats[-1]["items"].append(dict(src=p, title=text))
    used = set()
    for c in cats:
        for r in c["items"]:
            slug = slugify(r["title"])
            while slug in used:
                slug += "-2"
            used.add(slug)
            r["url"] = f"recipes/{slug}.html"
            link_map[r["src"]] = r["url"]

    # extra PDF recipe not in the dropdown
    pdf = idx.parent / "recipes" / "lemon pie filling.pdf"
    pdf_url = MEDIA.file(pdf, "docs") if pdf.exists() else None

    for c in cats:
        for i, r in enumerate(c["items"]):
            content, imgs = clean_html(read(r["src"]), r["src"].parent, link_map, title=r["title"])
            r["img"] = imgs[0] if imgs else None
            page = (f'<article class="wrap narrow prose recipe"><header class="page-head">'
                    f'<p class="kicker"><a href="@ROOT@recipes/index.html#{slugify(c["name"])}">Nuran\'s Recipes · {esc(c["name"])}</a></p>'
                    f'<h1>{esc(r["title"])}</h1></header>{content}'
                    f'<p class="back"><a href="@ROOT@recipes/index.html">← All recipes</a></p></article>')
            render(r["url"], r["title"], page, section="recipes/index.html",
                   description=f"Nuran's recipe for {r['title']}. " + excerpt(content, 120))

    # intro text: everything in the page before the recipe list
    intro_src = re.split(r"Select a recipe", src, maxsplit=1, flags=re.I)[0] + "</body>"
    intro, _ = clean_html(intro_src, idx.parent, link_map, title="Nuran's recipes")
    intro = re.sub(r'<a class="photo[^>]*>.*?</a>', "", intro)
    intro = re.sub(r"<(p|h2|h3)>[^<]*(Nurans Recipes web site|MUM'S RECIPES|Just choose a recipe)[^<]*</\1>", "",
                   intro, flags=re.I)
    kitchen = MEDIA.image(MK / "images" / "nurankitchen.JPG")
    parts = [f'<section class="hero small"><div class="wrap split"><div><p class="kicker">From Nuran\'s kitchen</p>'
             f'<h1>Nuran\'s Recipes</h1><div class="lede prose">{intro}</div></div>'
             f'<img class="hero-side" src="@ROOT@{kitchen["med"]}" alt="Nuran in her kitchen" width="{kitchen["w"]}" height="{kitchen["h"]}"></div></section>'
             '<div class="wrap"><nav class="vol-jump" aria-label="Categories">']
    parts += [f'<a href="#{slugify(c["name"])}">{esc(c["name"])}</a>' for c in cats]
    parts.append("</nav>")
    for c in cats:
        parts.append(f'<section class="volume" id="{slugify(c["name"])}"><h2>{esc(c["name"])}</h2><ul class="recipe-list">')
        parts += [f'<li><a href="@ROOT@{r["url"]}">{esc(r["title"])}</a></li>' for r in c["items"]]
        if pdf_url and c["name"].lower() == "sweets":
            parts.append(f'<li><a href="@ROOT@{pdf_url}">Lemon Pie Filling <span class="muted">(PDF)</span></a></li>')
        parts.append("</ul></section>")
    parts.append("</div>")
    render("recipes/index.html", "Nuran's Recipes", "".join(parts), section="recipes/index.html",
           description="Nuran's family recipes – curries, mains, sauces, pies, salads and sweets.")
    return kitchen, sum(len(c["items"]) for c in cats)


GREY_ORDER = ["first win", "second win", "third win", "fourth win", "johnnys fifth win", "johnny sixth win",
              "johnnys seventh win", "eighth win", "ninth win formula 400", "tenth win", "eleventh win",
              "13th win", "murray bridge win"]


def drive_links():
    """build/drive_videos.txt: lines of 'file-name.mp4  <Google Drive share link>' -> {file name: Drive file id}."""
    links = {}
    if DRIVE_VIDEOS.exists():
        for line in DRIVE_VIDEOS.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) < 2 or line.lstrip().startswith("#"):
                continue
            m = re.search(r"/d/([\w-]+)|[?&]id=([\w-]+)", parts[1])
            if not m:
                sys.exit(f"drive_videos.txt: can't find a file id in {parts[1]}")
            links[parts[0]] = m.group(1) or m.group(2)
    return links


def build_greyhounds(link_map):
    base = MK / "nuransrecipes"
    idx = base / "Greyhound index.htm"
    photo = MEDIA.image(base / "near record and training trifecta.jpg")

    drive = drive_links()

    def vid(p, title):
        name = slugify(title) + ".mp4"
        if name in drive:
            player = (f'<iframe src="https://drive.google.com/file/d/{drive[name]}/preview" title="{esc(title)}" '
                      'allow="autoplay; fullscreen" allowfullscreen loading="lazy"></iframe>')
        else:
            warn(f"no Google Drive link for {name} in build/drive_videos.txt (file copied into the site instead)")
            player = f'<video controls preload="none" src="@ROOT@{MEDIA.file(p, "video", name)}"></video>'
        return f'<figure class="video">{player}<figcaption>{esc(title)}</figcaption></figure>'

    keen = sorted((p for p in (base / "win replays").glob("*.mp4")),
                  key=lambda p: GREY_ORDER.index(" ".join(p.stem.lower().split()))
                  if " ".join(p.stem.lower().split()) in GREY_ORDER else 99)
    zeenat = sorted((base / "Zeenat wins").glob("*.mp4"))
    ztitles = ["Zeenat – Race 11, Mount Gambier (26 Dec 2019)", "Zeenat – win replay (30 Dec 2019)"]

    parts = [f'<section class="hero small"><div class="wrap split"><div><p class="kicker">J.K. The Great Syndicate</p>'
             '<h1>The Greyhounds</h1><p class="lede">The syndicate\'s dogs – Zeenat, Keen One and Keen Too – '
             'and replays of their winning runs.</p></div>'
             f'<a class="photo hero-side" href="@ROOT@{photo["full"]}" data-caption="Near record and a training trifecta">'
             f'<img src="@ROOT@{photo["med"]}" alt="Near record and training trifecta" width="{photo["w"]}" height="{photo["h"]}"></a>'
             '</div></section><div class="wrap">']
    parts.append('<section class="volume"><h2>Keen One – winning runs</h2><div class="grid videos">')
    for p in keen:
        t = " ".join(p.stem.split()).replace("johnnys", "Johnny's").replace("Johnny ", "Johnny's ")
        parts.append(vid(p, "Keen One – " + t[0].upper() + t[1:]))
    parts.append('</div></section><section class="volume"><h2>Zeenat – winning runs</h2><div class="grid videos">')
    for p, t in zip(zeenat, ztitles):
        parts.append(vid(p, t))
    parts.append("</div></section></div>")
    if not idx.exists():
        warn("Greyhound index missing")
    render("greyhounds.html", "The Greyhounds", "".join(parts), section="greyhounds.html",
           description="Greyhound racing syndicate – Zeenat and Keen One winning run replays.")
    return photo


# --------------------------------------------------------------------------- photos

UI_IMAGES = {"blank.gif", "branding.gif", "next.gif", "pause.gif", "play.gif", "previous.gif", "prev.gif",
             "back.gif", "home.gif", "first.gif", "last.gif"}


def gallery_titles():
    titles = {}
    for page in (OLD / "Photos of the Family.htm", OLD / "babykeenan" / "Picture Gallery.htm"):
        for p, text in index_links(page):
            if text:
                titles.setdefault(p.parent.resolve(), text)
                titles.setdefault(p.resolve(), text)
    return titles


def gallery_captions(folder):
    """Photoshop web galleries keep per-photo captions in html/*.htm pages."""
    caps = {}
    hdir = folder / "html"
    if hdir.is_dir():
        for h in hdir.glob("*.htm*"):
            s = read(h)
            m = re.search(r"<img[^>]*src=\"([^\"]*)\"", s, re.I)
            if not m:
                continue
            img = resolve(h.parent, m.group(1))
            t = page_title(s)
            if img and t and not re.fullmatch(r"(?i)(dsc|dscf|dscn|img|p\d)\S*|\S+\.jpe?g|[\w\s]*slideshow[\w\s]*", t):
                caps[img] = t
    return caps


def build_photos():
    titles = gallery_titles()
    albums = []

    def add(folder, title, images, blurb=""):
        images = [p for p in images if p.suffix.lower() in IMG_EXT and p.name.lower() not in UI_IMAGES]
        images = sorted(set(images), key=lambda p: p.name.lower())
        if not images:
            return
        albums.append(dict(title=title, folder=folder, images=images, blurb=blurb))

    for d in sorted(OLD.rglob("default.htm")):
        if "_vti" in str(d):
            continue
        folder = d.parent
        t = titles.get(d.resolve()) or titles.get(folder.resolve()) or page_title(read(d)) or folder.name
        if t.lower() in ("", "untitled", "adobe photoshop album"):
            t = folder.name
        t = {"carport": "Building the carport enclosure", "Hot House": "The hot house"}.get(folder.name, t)
        t = t.replace("_", " ")
        add(folder, t.replace("Slideshow", "").replace("SlideShow", "").replace("slideshow", "").strip(" -") or folder.name,
            list((folder / "images").glob("*")))
    bk = OLD / "babykeenan"
    add(bk / "archimage", "Baby Archie – more photos", list((bk / "archimage").glob("*")))
    add(bk / "julespic", "Julian", list((bk / "julespic").glob("*")))
    add(bk / "slideshow", "The Keenan boys as babies", list((bk / "slideshow").glob("*")))
    add(bk, "Grandkids snapshots", [p for p in bk.glob("*") if p.is_file()])
    add(OLD / "mildura", "Mildura", list((OLD / "mildura").glob("*")))
    add(MK / "images" / "lincoln", "Port Lincoln", list((MK / "images" / "lincoln").glob("*")))
    add(MK / "images", "Around Tarpeena", [p for p in (MK / "images").glob("*") if p.is_file()])

    # the old house/greenhouse albums go last; grandkids first
    albums.sort(key=lambda a: a["folder"].name in ("carport", "Hot House"))
    # drop albums whose photos all already appear in an earlier album
    seen, kept = set(), []
    for a in albums:
        res = [MEDIA.image(p) for p in a["images"]]
        keys = {r["full"] for r in res if r}
        if keys and not keys <= seen:
            kept.append(a)
        seen |= keys
    albums[:] = kept
    # de-duplicate album slugs, render pages
    used = set()
    for a in albums:
        slug = slugify(a["title"])
        while slug in used:
            slug += "-2"
        used.add(slug)
        a["url"] = f"photos/{slug}.html"
        caps = gallery_captions(a["folder"])
        items = []
        for p in a["images"]:
            r = MEDIA.image(p)
            if not r:
                continue
            cap = caps.get(p, "")
            items.append(f'<a class="photo" href="@ROOT@{r["full"]}"{f" data-caption=\"{esc(cap)}\"" if cap else ""}>'
                         f'<img src="@ROOT@{r["med"]}" alt="{esc(cap)}" loading="lazy" decoding="async" '
                         f'width="{r["w"]}" height="{r["h"]}"></a>')
            a.setdefault("cover", r)
        a["count"] = len(items)
        page = (f'<div class="wrap"><header class="page-head"><p class="kicker"><a href="@ROOT@photos/index.html">Photos</a></p>'
                f'<h1>{esc(a["title"])}</h1><p class="muted">{len(items)} photos · click a photo to enlarge</p></header>'
                f'<div class="gallery">{"".join(items)}</div>'
                f'<p class="back"><a href="@ROOT@photos/index.html">← All albums</a></p></div>')
        render(a["url"], a["title"], page, section="photos/index.html")

    # home movies (.wmv – download only)
    movies = []
    wmv_titles = {"Banjoball": "The Kids & Banjo", "archie feeding": "Archie eating", "Jumping Keenans": "Jumping Keenans",
                  "Eleanor Walking": "Eleanor walking", "Julian_bathtime": "Julian's bath time",
                  "Julian_Dinner": "Julian's dinner", "Julian Sweeping": "Julian sweeping",
                  "High stepping Julian": "High-stepping Julian", "Birthday Movie": "Birthday movie"}
    for p in sorted(OLD.rglob("*.wmv")):
        if "_vti" in str(p):
            continue
        url = MEDIA.file(p, "video")
        movies.append(f'<li><a href="@ROOT@{url}">{esc(wmv_titles.get(p.stem, p.stem))}</a> '
                      f'<span class="muted">({p.stat().st_size / 1e6:.1f} MB .wmv)</span></li>')

    parts = ['<section class="hero small"><div class="wrap"><p class="kicker">Family album</p><h1>Photos</h1>'
             '<p class="lede">Grandkids, family gatherings and trips – gathered from the old picture galleries.</p>'
             '</div></section><div class="wrap"><div class="grid cards">']
    parts += [card(f'@ROOT@{a["url"]}', a["title"], "", a.get("cover"), f'{a["count"]} photos') for a in albums]
    parts.append("</div>")
    if movies:
        parts.append('<section class="volume"><h2>Home movies</h2><p class="muted">These older Windows Media '
                     'files download rather than play in the browser; they open in VLC or Windows Media Player.</p>'
                     f'<ul class="recipe-list">{"".join(movies)}</ul></section>')
    parts.append("</div>")
    render("photos/index.html", "Photos", "".join(parts), section="photos/index.html",
           description="Keenan family photo albums.")
    return albums


# --------------------------------------------------------------------------- home, 404, assets

def build_home(vols, disc, recipes, grey, albums):
    # a replacement hero photo dropped into build/source_images/ (home-hero.jpg etc.) wins
    custom = sorted(p for p in (HERE / "source_images").glob("home-hero.*") if p.suffix.lower() in IMG_EXT)
    hero = MEDIA.image(custom[0] if custom else MK / "golden wedding dinner.jpg")
    hero_alt = "Malcolm and Nuran" if custom else "Malcolm and Nuran at their golden wedding dinner"
    # keep faces in frame when a tall photo is cropped to the wide banner
    hero_pos = ' style="object-position: 50% 25%"' if custom else ""
    strip = [MEDIA.image(MK / n) for n in ("youngfamily.jpg", "bluelake.jpg", "banjo.jpg", "xmas09.JPG", "Max small.jpg")]
    latest = [t for v in vols for t in v["tales"]][-1]
    tales_count = sum(len(v["tales"]) for v in vols)
    disc_img, disc_text = disc
    kitchen, n_recipes = recipes
    photos_cover = next((a["cover"] for a in albums if "archie" in a["title"].lower()), albums[0]["cover"] if albums else None)
    parts = [
        f'<section class="home-hero"><img src="@ROOT@{hero["full"]}" alt="{hero_alt}"{hero_pos} '
        f'width="{hero["w"]}" height="{hero["h"]}"><div class="home-hero-text wrap"><p class="kicker">Tarpeena, South Australia</p>'
        '<h1>Malcolm &amp; Nuran</h1><p class="lede">Stories from the country, Nuran\'s favourite recipes, '
        'the greyhounds and the family photo album.</p>'
        f'<p><a class="btn" href="@ROOT@{latest["url"]}">Read the latest tale</a> '
        f'<a class="btn ghost" href="@ROOT@tales/index.html">All Tarpeena Tales</a></p></div></section>',
        '<div class="wrap"><div class="grid cards sections">',
        card("@ROOT@tales/index.html", "Tarpeena Tales",
             f"{tales_count} stories of cycling, home brew, darts, dogs and family, 2005 onwards.", strip[1]),
        card("@ROOT@discoveries.html", "Great Discoveries", disc_text, disc_img or strip[0]),
        card("@ROOT@recipes/index.html", "Nuran's Recipes", f"{n_recipes} family favourites, from curries and roti to sticky date pudding.", kitchen),
        card("@ROOT@greyhounds.html", "The Greyhounds", "Zeenat and Keen One – replays of the winning runs.", grey),
        card("@ROOT@photos/index.html", "Photos", f"{len(albums)} albums of grandkids, gatherings and trips.", photos_cover or strip[0]),
        '</div><section class="volume"><h2>Around the family</h2><div class="gallery">',
    ]
    for r in strip:
        parts.append(f'<a class="photo" href="@ROOT@{r["full"]}"><img src="@ROOT@{r["med"]}" alt="" loading="lazy" '
                     f'width="{r["w"]}" height="{r["h"]}"></a>')
    parts.append("</div></section></div>")
    render("index.html", "Malcolm & Nuran", "".join(parts), section="index.html", body_class="home")


def build_404():
    render("404.html", "Page not found",
           '<div class="wrap narrow prose"><header class="page-head"><h1>Page not found</h1></header>'
           '<p>That page has moved in the new version of the site.</p>'
           '<p><a class="btn" href="/index.html">Go to the home page</a></p></div>', root="/")


def copy_assets():
    for sub in ("css", "js"):
        (OUT / "assets" / sub).mkdir(parents=True, exist_ok=True)
    shutil.copy2(ASSETS / "site.css", OUT / "assets" / "css" / "site.css")
    shutil.copy2(ASSETS / "site.js", OUT / "assets" / "js" / "site.js")
    shutil.copy2(ASSETS / "favicon.svg", OUT / "assets" / "favicon.svg")
    (OUT / "CNAME").write_text(DOMAIN + "\n", encoding="utf-8")  # GitHub Pages custom domain
    (OUT / ".nojekyll").write_text("", encoding="utf-8")  # serve files as-is, no Jekyll processing


# --------------------------------------------------------------------------- main

def main():
    if not MK.is_dir():
        sys.exit(f"source not found: {MK}")
    if OUT.exists():
        shutil.rmtree(OUT)
    for d in ("media/img/m", "media/video", "media/docs"):
        (OUT / d).mkdir(parents=True, exist_ok=True)
    copy_assets()
    link_map = {}
    vols = build_tales(link_map)
    recipes = build_recipes(link_map)
    render_tales(vols, link_map)
    disc = build_discoveries(link_map)
    grey = build_greyhounds(link_map)
    albums = build_photos()
    build_home(vols, disc, recipes, grey, albums)
    build_404()
    (HERE / "report.txt").write_text("\n".join(sorted(set(report))) + "\n", encoding="utf-8")
    print(f"built {OUT}  ({len(report)} warnings, see build/report.txt)")


if __name__ == "__main__":
    main()
