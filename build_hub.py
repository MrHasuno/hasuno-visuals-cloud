#!/usr/bin/env python3
"""Rebuilds the hub from whatever is in sources/.

You do not need to pass anything. Drop a pack in sources/ and run this - or just push to
GitHub and the workflow in .github/workflows does it for you.

What it accepts in sources/
    <id>.zip                 a resource pack, already zipped
    <id>/                    a resource pack folder (pack.mcmeta + assets/...)
    <id>.png|.jpg|.webp      the card picture for that style
    previews/<id>.png        the same, if you prefer to keep pictures in one folder

The display name is taken, in this order, from
    names.txt                a line like   sword_hasunos_main=Hasuno's Main
    the pack's pack.mcmeta   its description
    the id                   "sword_hasunos_main" -> "Main"

Output: packs/<id>.zip, previews/<id>.png and index.json.
Run with --check to only report problems without writing anything.
"""
import datetime
import hashlib
import json
import os
import re
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.path.join(ROOT, "sources")
PACKS = os.path.join(ROOT, "packs")
PREVIEWS = os.path.join(ROOT, "previews")
INDEX = os.path.join(ROOT, "index.json")
NAMES = os.path.join(ROOT, "names.txt")

ID_RE = re.compile(r"^[a-z][a-z0-9]{1,15}_[a-z0-9_]{1,40}$")
CATEGORIES = {"sword", "axe", "pickaxe", "anchor", "crystal", "obsidian", "armor", "totem", "gap",
              "pearl", "fire", "deepslate", "stone", "snow", "grass", "shield", "cobweb",
              "inventory", "glowstone", "mace", "trident", "hotbar", "sky", "spear"}
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")


def read_names():
    names = {}
    if os.path.isfile(NAMES):
        for line in open(NAMES, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            names[key.strip()] = value.strip()[:40]
    return names


def name_from_meta(folder, fallback):
    meta = os.path.join(folder, "pack.mcmeta")
    if os.path.isfile(meta):
        try:
            desc = json.load(open(meta, encoding="utf-8"))["pack"]["description"]
            if isinstance(desc, str) and 0 < len(desc) <= 40:
                return desc
        except Exception:
            pass
    return fallback


def zip_dir(src, out):
    tmp = out + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for base, _, files in os.walk(src):
            for f in files:
                full = os.path.join(base, f)
                z.write(full, os.path.relpath(full, src))
    os.replace(tmp, out)


def find_preview(stem):
    for cand in [os.path.join(SOURCES, stem + ext) for ext in IMAGE_EXT] + \
                [os.path.join(SOURCES, "previews", stem + ext) for ext in IMAGE_EXT]:
        if os.path.isfile(cand):
            return cand
    # a pack folder may carry its own preview
    for base in (os.path.join(SOURCES, stem),):
        if os.path.isdir(base):
            for ext in IMAGE_EXT:
                cand = os.path.join(base, "preview" + ext)
                if os.path.isfile(cand):
                    return cand
    return None


def main():
    check_only = "--check" in sys.argv
    names = read_names()
    os.makedirs(PACKS, exist_ok=True)
    os.makedirs(PREVIEWS, exist_ok=True)

    old = {}
    categories, admin_categories = [], []
    if os.path.isfile(INDEX):
        try:
            previous = json.load(open(INDEX, encoding="utf-8"))
            for s in previous.get("styles", []):
                old[s["id"]] = s
            # the slot definitions (how a pack's files are picked apart) are hand-written and
            # must survive a rebuild
            categories = previous.get("categories", [])
            admin_categories = previous.get("adminCategories", [])
        except Exception:
            pass

    todo, problems = [], []
    for entry in sorted(os.listdir(SOURCES)) if os.path.isdir(SOURCES) else []:
        stem, ext = os.path.splitext(entry)
        full = os.path.join(SOURCES, entry)
        if entry in ("previews", ".DS_Store") or entry.startswith("."):
            continue
        if ext.lower() in IMAGE_EXT:          # a preview on its own, handled with its pack
            continue
        if ext.lower() != ".zip" and not os.path.isdir(full):
            continue
        if not ID_RE.match(stem):
            problems.append(f"{entry}: id must look like <category>_<name>, lowercase a-z 0-9 _")
            continue
        category = stem.split("_", 1)[0]
        if category not in CATEGORIES:
            problems.append(f"{entry}: category '{category}' is not one the mod knows")
            continue
        todo.append((stem, full, ext.lower() == ".zip"))

    styles = []
    for stem, full, is_zip in todo:
        out_zip = os.path.join(PACKS, stem + ".zip")
        if not check_only:
            if is_zip:
                shutil.copyfile(full, out_zip)
            else:
                zip_dir(full, out_zip)
        size = os.path.getsize(out_zip) if os.path.exists(out_zip) else (
            os.path.getsize(full) if is_zip else 0)
        sha = hashlib.sha256(open(out_zip, "rb").read()).hexdigest() if os.path.exists(out_zip) else ""
        preview = find_preview(stem)
        if preview and not check_only:
            target = os.path.join(PREVIEWS, stem + ".png")
            if os.path.abspath(preview) != os.path.abspath(target):
                shutil.copyfile(preview, target)
        display = names.get(stem) or name_from_meta(full, stem.split("_", 1)[-1].replace("_", " ").title())
        style = {
            "id": stem,
            "category": stem.split("_", 1)[0],
            "name": display[:40],
            "sha256": sha,
            "size": size,
            "added": old.get(stem, {}).get("added", datetime.date.today().isoformat()),
            "early": bool(old.get(stem, {}).get("early", False)),
        }
        if preview or stem in {os.path.splitext(f)[0] for f in os.listdir(PREVIEWS)}:
            style["preview"] = "previews/" + stem + ".png"
        styles.append(style)

    if not check_only:
        keep = {s["id"] for s in styles}
        for f in os.listdir(PACKS):
            if f.endswith(".zip") and f[:-4] not in keep:
                os.remove(os.path.join(PACKS, f))
        for f in os.listdir(PREVIEWS):
            if f.lower().endswith(IMAGE_EXT) and os.path.splitext(f)[0] not in keep:
                os.remove(os.path.join(PREVIEWS, f))
        index = {"version": 1, "publishUrl": None, "styles": styles,
                 "categories": categories, "adminCategories": admin_categories}
        with open(INDEX, "w", encoding="utf-8") as fh:
            json.dump(index, fh, indent=2)
            fh.write("\n")

    print(f"{len(styles)} style(s)" + (" (check only, nothing written)" if check_only else " written to index.json"))
    for s in styles:
        flag = "" if "preview" in s else "   no preview - the card shows the item icon"
        print(f"  {s['id']:34} {s['name']:26} {s['size']:>9} bytes{flag}")
    if problems:
        print("\nskipped:")
        for p in problems:
            print("  " + p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
