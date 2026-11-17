# A native Android Fieldbook

Notes for a possible Android app, 17 November 2026. This is the shape that matches the goal. It is not started.

## Goal

One app a person can install. While the phone has a network, they download Gemma and the libraries they want. With no network, they ask a question. The app searches what is already stored and Gemma answers from those pages.

The people who receive it should not need omalauncher, Termux, Arch, Python, or a package install.

## Why an Android app fits

The current Fieldbook screen is an omalauncher `.owl` file. Only that launcher runs it. A stock Arch system will not. Inside the launcher, a program also stops when its window closes, and Gemma is stuck on the CPU because the proot cannot see the phone's GPU.

Android already has the pieces the emergency path needs:

- SQLite, including full-text search, in the system. No extra database to install.
- A normal place for large downloads, with a download that can resume.
- LiteRT-LM, the same runtime as Google AI Edge Gallery. It runs the Gemma 4 E2B `.litertlm` file this phone already uses, and it supports tool calls. On Android it can use the GPU, which this Linux environment cannot see.

The app install stays small. The model is about 2.6 GB and the libraries are larger. Both stay downloads, the way they are now.

## What the app does

Three screens, the same ones Fieldbook already has:

1. Chat. One question at a time. A visible timer while Gemma works. The answer lists the pages it used.
2. Library. Free space, Gemma, and each library with its size and a download button. A tap downloads, checks the checksum, and stores the file.
3. Page. The cited text. Pictures that belong to an HTML chapter can be shown. A video or a PDF is handed to another app the person already has. The Fieldbook app does not grow its own video player.

The reliable search is: the app searches first, puts the matching pages into the prompt, and asks Gemma to answer only from those pages and to say when they do not cover it. LiteRT-LM can also call a search tool itself. Doing the search in the app is the behavior to trust in an emergency, because the answer does not depend on the model remembering to search.

## Libraries

Keep the current catalog. Sizes and checksums below are the ones already verified.

| Library | File | Bytes | sha256 |
| --- | --- | --- | --- |
| Gemma 4 E2B | `gemma-4-E2B-it.litertlm` | 2588147712 | checked by size |
| Lastbook Small | `Lastbook-Small-20261113.zip` | 7691528852 | `bfe8b0b66d898cac18b7f979dd5e560b8fd653f03244b6186e0436306cf96291` |
| English Wikibooks, text only, October 2026 | `wikibooks_en_all_nopic_2026-10.zim` | 3544612812 | `bda3410005656daeb523c81774e151b750cd5a8828f081ded0848cd7fdccba7c` |
| Vikidia English, September 2026 | `vikidia_en_all_maxi_2026-09.zim` | 77565163 | `16728e6be34081f6c627b3cbf2c36ff31823defb0f30b68fab146b5ca68e591e` |
| Public Domain Recipes, November 2026 | `publicdomainrecipes.com_en_all_2026-11.zim` | 17143913 | `dc1593da2f990c31b583b4d00e3219d8efae6f2f1f51629f2d3d5a79d4984839` |

Lastbook Medium is about 67.5 GB and needs roughly 137 GB free. Leave it visible and refuse the download. The All pack does not fit a phone.

Lastbook Small already contains `search.sqlite`. The app can query that file. It does not need to rebuild it.

A ZIM is one packed file. This cookbook already has a full-text index inside it, and `kiwix-search` can return titles from that index. The index does not include the article text Gemma has to read. For a shared app, do not ask the person to install ZIM tools. Two ways to handle that:

- Small libraries, such as the 16 MB cookbook: publish the SQLite of article text as the download. The phone never opens a ZIM.
- Large libraries, such as Wikibooks: at the end of the download, while still online, build the SQLite once inside the app. After that, emergency search is only SQLite plus Gemma.

The cookbook on this phone is already indexed: 415 recipes in `~/.local/share/fieldbook/zim.sqlite`. There is no recipe titled chicken noodle soup. Chicken Soup has optional pasta. Japanese Noodle Soup is made with chicken stock.

Folders of `.txt` and `.md` notes, which Fieldbook can add today, are worth keeping. They are the person's own files, searched the same way as a library.

## What is inside the APK, and what is not

Inside the app:

- The chat, library, and page screens.
- The LiteRT-LM Android library.
- The list of libraries, their URLs, sizes, and checksums.
- The search that reads SQLite and builds the prompt.

Not inside the app:

- The Gemma file.
- Lastbook, Wikibooks, Vikidia, or the cookbook.
- Chat history. That stays on the phone that made it.

Gemma and the books keep their own licenses. The app code can stay MIT, as the omalauncher screen is.

## Build notes

Build it with the Android SDK, in Kotlin, on a computer. This omalauncher proot is a poor place to compile an APK: no full Android SDK workflow, and the Linux side is not the phone's own app process.

Use the same model URL the library screen uses now. Download with resume, check the size, and check the sha256 where we have one. Store libraries in app storage. Copies the person should see in other apps can also be written under Documents.

Keep one question at a time. If the GPU delegate is missing on a phone, use the CPU. The proot version already shows that CPU works on this device, and that a question can take a minute, so the timer stays.

The omalauncher Fieldbook is the working prototype: the catalog, the checksums, the prompt, and the "search, then answer from these pages" rule. The Android app is the thing to hand to someone else.
