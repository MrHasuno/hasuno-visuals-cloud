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


def publish_url():
    """The preset board address, read from worker-url.txt so a rebuild never loses it.

    worker-url.txt holds one line, the Worker URL, for example
        https://hasuno-presets.mrhasuno.workers.dev
    The mod only accepts https://<name>.<account>.workers.dev, so anything else is ignored.
    """
    path = os.path.join(ROOT, "worker-url.txt")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            if re.fullmatch(r"https://[a-z0-9-]+\.[a-z0-9-]+\.workers\.dev", line):
                return line
            print(f"worker-url.txt: '{line}' is not a workers.dev URL - ignored")
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
                # hardlink where the filesystem allows it: packs/ can be 350 MB of skies and
                # there is no reason to keep two copies of the bytes
                try:
                    if os.path.exists(out_zip):
                        os.remove(out_zip)
                    os.link(full, out_zip)
                except OSError:
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

    # a pack file that exists but is not in the catalogue (dropped in by hand, or restored from an
    # old commit) is indexed rather than ignored - and never deleted
    if not check_only:
        seen_now = {s["id"] for s in styles}
        for f in sorted(os.listdir(PACKS)) if os.path.isdir(PACKS) else []:
            if not f.endswith(".zip"):
                continue
            sid = f[:-4]
            if sid in seen_now or not ID_RE.match(sid):
                continue
            category = sid.split("_", 1)[0]
            if category not in CATEGORIES:
                continue
            full = os.path.join(PACKS, f)
            style = {
                "id": sid,
                "category": category,
                "name": (names.get(sid) or sid.split("_", 1)[-1].replace("_", " ").title())[:40],
                "sha256": hashlib.sha256(open(full, "rb").read()).hexdigest(),
                "size": os.path.getsize(full),
                "added": old.get(sid, {}).get("added", datetime.date.today().isoformat()),
                "early": bool(old.get(sid, {}).get("early", False)),
            }
            if os.path.isfile(os.path.join(PREVIEWS, sid + ".png")):
                style["preview"] = "previews/" + sid + ".png"
            styles.append(style)
            print(f"  indexed {sid} from packs/ (it had no catalogue entry)")

    if not check_only:
        # anything the catalogue already knew about but whose files are not in this checkout
        # (the big sky packs are uploaded straight from our side) is carried over untouched -
        # dropping it would silently remove styles from everybody's menu
        seen = {s["id"] for s in styles}
        for sid, entry in old.items():
            if sid not in seen:
                styles.append(entry)
                print(f"  kept {sid} from the previous index (no files for it in this checkout)")
        keep = {s["id"] for s in styles}
        # packs/ is never pruned: deleting a zip here once removed 26 sky packs. Files with no
        # catalogue entry are reported instead, so a human decides.
        for f in sorted(os.listdir(PACKS)) if os.path.isdir(PACKS) else []:
            if f.endswith(".zip") and f[:-4] not in keep:
                print(f"   note: packs/{f} is not in the catalogue and was left alone")
        for f in sorted(os.listdir(PREVIEWS)) if os.path.isdir(PREVIEWS) else []:
            if f.lower().endswith(IMAGE_EXT) and os.path.splitext(f)[0] not in keep:
                print(f"   note: previews/{f} has no style and was left alone")
        index = {"version": 1, "publishUrl": publish_url(), "styles": styles,
                 "categories": categories, "adminCategories": admin_categories}
        with open(INDEX, "w", encoding="utf-8") as fh:
            json.dump(index, fh, indent=2)
            fh.write("\n")

    # be loud about styles whose pack file is not here: they stay in the catalogue (so a rebuild
    # never drops styles that only exist in the cloud) but they cannot download
    orphans = [s["id"] for s in styles if not os.path.isfile(os.path.join(PACKS, s["id"] + ".zip"))]
    if orphans:
        print(f"!! {len(orphans)} style(s) have a catalogue entry but no pack file - "
              f"they will not download:")
        for o in orphans:
            print("   " + o)
        print("   restore them before pushing (see RESTORE-SKIES.md)")

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
