# Hasuno's Visuals — style hub

The cloud this mod reads its styles from. A plain GitHub repository, nothing else: no server to
run, no worker to pay for. GitHub serves the files; the mod verifies every pack by its SHA-256
before it uses it.

## What the mod asks for

```
index.json                 the catalogue
packs/<id>.zip             one resource pack per style
previews/<id>.png          the picture on the card (256x256 is ideal)
```

`index.json`:

```json
{
  "version": 1,
  "publishUrl": null,
  "styles": [
    {
      "id": "sword_hasunos_main",
      "category": "sword",
      "name": "Hasuno's Main",
      "sha256": "697a2c9ed560de3ee45ccdc37179862332614fecdfc36c48ad757856b7b1bae0",
      "size": 5151,
      "preview": "previews/sword_hasunos_main.png",
      "added": "2026-10-23",
      "early": false
    }
  ],
  "categories": [],
  "adminCategories": []
}
```

Rules the mod enforces (it silently skips anything that breaks them):

- `id` matches `^[a-z][a-z0-9]{1,15}_[a-z0-9_]{1,40}$` and **starts with the category**
  (`sword_…`, `axe_…`, `gap_…`).
- `category` is one of: sword, axe, pickaxe, anchor, crystal, obsidian, armor, totem, gap, pearl,
  fire, deepslate, stone, snow, grass, shield, cobweb, inventory, glowstone, mace, trident, hotbar.
- `sha256` is 64 lowercase hex characters and matches the zip.
- `size` is the zip's size in bytes (max 95 MB), `name` is 1–40 characters.
- `preview` is optional; without it the card shows the item icon instead of a picture.
- `early: true` hides a style behind early access.

## Adding a style (no commands)

1. Drop the pack into `sources/` as either
   - `<id>.zip`, or
   - a folder `<id>/` containing `pack.mcmeta` + `assets/…`
2. Drop its card picture in `sources/previews/` (or next to the pack) as `<id>.png`.
3. Push.

`.github/workflows/hub.yml` runs the rebuild on GitHub for you: it zips folders, hashes the packs,
copies the previews and rewrites `index.json`, then commits the result. Nothing to install, no
commands to type. (If you do want to run it locally, `python3 build_hub.py` with no arguments does
the same thing; `--check` only reports problems.)

The display name comes from `names.txt` — one `id=Name` per line. Leave a pack out and its
`pack.mcmeta` description is used, and failing that the id is prettied up.

The id rules the mod enforces: `<category>_<something>`, lowercase `a-z 0-9 _`, starting with one
of the categories listed above. A pack whose id breaks that is skipped with a message rather than
breaking the whole hub.

## Pointing the mod at this repo

In `StylesCloud.java`:

```java
public static final String OWNER = "YOUR-GITHUB-NAME";
public static final String REPO  = "hasuno-visuals-cloud";
```

Also worth changing while you are in there:

- the jsDelivr and worker mirrors in `MIRRORS` (they belong to the old cloud),
- the `User-Agent` string,
- `StylesBlock.java`'s `blocked.json` URL,
- `GitHubPublisher`'s API base — that is what the in-mod uploader publishes with.

## Rights

Only ship packs you made or that are licensed for redistribution (MIT, CC0, CC-BY **with the credit
filled in**). Every style in this hub is content you are publishing, so the licence text has to be
right. Put the credit in the style's `name` or in a `CREDITS.md` here.
