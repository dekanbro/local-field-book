# Fieldbook 1.1 gold

An omalauncher drawer app. Ask Gemma on the phone. Answers can cite library pages, and a tap opens the cited page.

This zip is the screen, the program, and two notes. It does not include the Gemma model or the libraries. The app downloads those from the Library screen when the phone has room.

- `docs/process-and-notes.md` is how this version was built and what is on this phone.
- `docs/android-app.md` is the note for a native Android app, which is the better thing to share.

The code is MIT. The books and the model keep their own licenses.

## Install on an omalauncher phone

From the Linux terminal inside omalauncher, with this zip unpacked in the current directory:

```bash
mkdir -p ~/.config/omalauncher/widgets /sdcard/Documents/Lastbook/gemma/tools
cp widgets/fieldbook.owl widgets/fieldbook.py ~/.config/omalauncher/widgets/
cp Lastbook/lbsearch.py /sdcard/Documents/Lastbook/
cp Lastbook/zimindex.py /sdcard/Documents/Lastbook/
cp Lastbook/gemma/preset.py /sdcard/Documents/Lastbook/gemma/
cp Lastbook/gemma/tools/*.py /sdcard/Documents/Lastbook/gemma/tools/
python3 -m venv ~/.local/litert-venv
~/.local/litert-venv/bin/pip install litert-lm
pacman -S --noconfirm zim-tools
```

Open Fieldbook from the app drawer. Tap Library. Download Gemma 4 E2B and Lastbook Small when there is room. English Wikibooks, Vikidia English, and Public Domain Recipes are on that screen too. After that, chat works offline.

One question at a time. Gemma runs on the CPU inside the launcher. A library question can take a minute. The gold line under the title counts up while it works.

Downloaded ZIM files are saved under `/sdcard/Documents/Lastbook/zim/`. The first search after a download indexes them with `zimdump`. See `docs/process-and-notes.md` for why that package is only a stand-in.

## What each file does

- `widgets/fieldbook.owl` is the screen.
- `widgets/fieldbook.py` is the program the buttons call. It has to stay at `~/.config/omalauncher/widgets/fieldbook.py`.
- `Lastbook/lbsearch.py` searches the Lastbook index and any indexed ZIM.
- `Lastbook/zimindex.py` builds that ZIM index.
- `Lastbook/gemma/preset.py` tells Gemma which tools it may call.
- `Lastbook/gemma/tools/` holds those tools. A new `.py` file in that folder is picked up on the next question.
