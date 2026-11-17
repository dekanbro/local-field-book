# Fieldbook 1.1 — process and notes

Gold snapshot, 17 November 2026. This file is the record of how the omalauncher app was built on this phone, what is on disk, and which choices we made so it can be shared.

The code in this zip is the screen and the program. It does not include the Gemma model, Lastbook, or any downloaded library.

## What we were building

An offline assistant on this phone. While there is a network, the person downloads a model and some libraries. With no network, they ask a question, the phone searches those libraries, and Gemma answers from the pages it found.

The first library was Lastbook Small, from https://lastbook.org/. The model was Gemma 4 E2B, the same `.litertlm` file already used in Termux and in Google AI Edge Gallery. The screen is a drawer app called Fieldbook.

## This phone

The Linux side is Arch Linux ARM under proot, inside the omalauncher Android app. It is not a booted Linux system.

- You are already root. There is no sudo.
- There is no systemd, cron, Docker, or kernel modules. A program keeps running only while the window it was started in stays open.
- `/sdcard` is the phone storage Linux is allowed to see. Files for other Android apps go in `/sdcard/Download` or `/sdcard/Documents`.
- `/sdcard` cannot run programs. A script there, or a symlink to one, fails. The terminal helper is a real file at `~/.local/bin/ask`.
- Python 3.14.9 is installed because this omalauncher image installed it. A stock Arch `base` system does not include Python.
- The phone has about 7.4 GB of RAM. Gemma still runs when free memory is near 1 GB and swap is busy. One question at a time.
- GPU and NPU are not available in this proot. `/dev/dri` is denied. Gemma uses `--backend=cpu`.

Termux (Ubuntu under proot) and this Arch proot are two sandboxes. They share the phone, the RAM, and `/sdcard`. They do not share installed packages.

## Lastbook

The official Linux installer is an Ubuntu x86_64 package. It does not run here.

Lastbook Small was downloaded and checked:

- URL: `https://downloads.lastbook.org/Lastbook-Small-20261113.zip`
- Size: 7,691,528,852 bytes
- sha256: `bfe8b0b66d898cac18b7f979dd5e560b8fd653f03244b6186e0436306cf96291`

It unpacks to `/sdcard/Documents/Lastbook/LastbookData/library-data/`. The useful files are `catalog.json` (314 records: PDF, video, HTML, metadata, transcripts, and two ZIMs) and `search.sqlite`. Search is SQLite FTS5 on the `pages` table: document id, title, collection, path, page, and body. About 12,750 page rows.

The two ZIMs inside Small, MDWiki and Appropedia, are not in that FTS index. HTML chapters can include pictures beside the HTML. Videos are real `.mp4` files. Fieldbook can share a video file to another Android app. It does not play video itself.

Lastbook Medium is about 67.5 GB and needs roughly 137 GB free to unpack. It is listed on the library screen and cannot be downloaded. The All pack is hundreds of gigabytes. Neither fits.

`lbsearch.py` searches that SQLite file. It drops common stopwords when at least two real words remain, ANDs the remaining words, and ranks with bm25. Page text is read from `search.sqlite`, not from a separate text split, because PDF page numbers and the text-file splits did not always match.

## Gemma

File: `/sdcard/Documents/Lastbook/models/gemma-4-E2B-it.litertlm`

- Size: 2,588,147,712 bytes
- Source: `https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm/resolve/main/gemma-4-E2B-it.litertlm`
- Runtime: `litert-lm` 0.19.2 in `~/.local/litert-venv`, installed with pip on Python 3.14
- Flags: `--backend=cpu --cache=disk --max-num-tokens=4096 --thinking=false --cpu-thread-count=4 --preset=.../gemma/preset.py`

The preset loads every tool in `gemma/tools/` that publishes a `TOOLS` list. The tools are:

- `search_library` and `read_page`, the library
- `search_folders`, `.txt` and `.md` notes the person added
- `current_time`

The model is told to search before answering questions about recipes, food, cooking, survival, health, water, shelter, repairs, or power, to cite the document id and page, and to say when the pages do not cover the question.

Tool lines from LiteRT look like `[tool_call] {"name","arguments"}` and `[tool_response] ...`. Fieldbook reads those through a pty so the status line can change while Gemma is still running. A run that lasts more than 10 minutes is stopped.

The screen shows a gold status line, an elapsed `m:ss` timer, and pulsing dots, because a question often takes a minute. The send button reads "thinking…" while busy.

## The app

Fieldbook is a drawer app, `app "fieldbook"`, not a home-screen widget. The files are:

- `~/.config/omalauncher/widgets/fieldbook.owl`, the screen, owl 19
- `~/.config/omalauncher/widgets/fieldbook.py`, the program the buttons call

Long-press Share on the icon only carries the `.owl` file, compressed into a link or QR. The Python program, the model, and the libraries are not in that share. This zip is the package that includes the program.

State lives in `~/.local/share/fieldbook/`: `thread.json`, `status.json`, `reading.json`, `folders.json`, download progress, and `ask.log`. Long jobs detach from the owl `run()` call so the launcher's command timeout does not kill a download or a Gemma answer.

Three screens:

- Chat. Newest message first. Under an answer, each cited page is a tappable line.
- Library. Free space, Gemma, the catalog below, added folders, and the tool list.
- Page. The cited text. HTML chapters can show up to 8 raster images of at least 15 KB. SVG and tiny images are skipped. "Open pdf", "open page", or "open file" hands the file to Android through `omalauncher share`.

The catalog on the library screen:

| Id | What | Size | On this phone |
| --- | --- | --- | --- |
| lastbook-small | Lastbook Small, zip, then unpack | 7.7 GB | yes |
| wikibooks-en | English Wikibooks, text only, October 2026 | 3.5 GB | no, download is offered |
| vikidia-en | Vikidia English, with pictures, September 2026 | 74 MB | no, download is offered |
| recipes-en | Public Domain Recipes, November 2026 | 16 MB | yes |
| lastbook-medium | Lastbook Medium | 67.5 GB | listed, download refused |

A ZIM download is saved under `/sdcard/Documents/Lastbook/zim/` and is not unpacked. The checksum is checked. After a ZIM download, and again on the next search if needed, `zimindex.py` builds `~/.local/share/fieldbook/zim.sqlite`. That step uses `zimdump` from the Arch package `zim-tools`.

## Recipes, and the index

Public Domain Recipes was downloaded, then a question for chicken noodle soup failed. The file was on disk. Search still looked only at Lastbook, which has chicken wire and canning charts, not recipes.

The cookbook was then indexed: 415 articles. There is no page titled chicken noodle soup. The closest are:

- `pdr-chicken-soup`, Chicken Soup, which says pasta is optional if you want noodles
- `pdr-japanese-noodle-soup`, Japanese Noodle Soup, made with chicken stock

The ZIM already contains its own full-text index. `kiwix-search` reads it and returns titles. "Chicken soup" returns Chicken Soup first. That index does not hand over the recipe text. Gemma needs the ingredients and the steps, which is why the articles were also copied into the SQLite index.

SQLite is not a separate install. It is the `sqlite3` module in Python 3.14 (SQLite 3.54.1 on this phone). Lastbook's own search file is SQLite too.

`zim-tools` and `kiwix-tools` are separate Arch packages. They were installed here so the cookbook could be read. They are a poor dependency for a program we hand to someone else. The emergency search path should stay Python plus the SQLite file. Building that file belongs at the end of the download, while the phone is still online.

## What this package is, and is not

This app runs in omalauncher. A base Arch install will not open the `.owl` screen, does not have `omalauncher share`, and does not have `/sdcard`. Installing Python on base Arch would not fix that.

The better thing to share for the original goal — download libraries online, then search them with Gemma when there is no network — is a native Android app. That is written up in `docs/android-app.md`.

## Left unfinished on purpose

- Wikibooks and Vikidia are on the library screen and have not been downloaded.
- MDWiki and Appropedia, already inside Lastbook Small, are still outside the FTS index.
- There is no in-app video player, and PDF pages are opened by sharing the file.
- The GitHub repo was described and not created. `gh` is installed and not logged in.
- Termux and Google AI Edge Gallery were left installed.
- The ZIM index still depends on `zimdump` until a download builds a SQLite file another way.
