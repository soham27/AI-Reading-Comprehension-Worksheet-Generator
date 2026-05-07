# Reading Comprehension Resources Creation AI Agent

Generate grade-appropriate reading comprehension worksheets in seconds, powered by GPT-4. The agent produces a **student PDF** (with blank answer lines for handwriting) and a **teacher PDF** (with a bullet-point answer key in place of the lines). Both editions end with a vocabulary reference page.

📄 [View a full sample student worksheet (PDF)](Worksheets/G10%20-%20A%20Bookmark's%20Truth.pdf)

<img width="2550" height="3300" alt="G10 - A Bookmark&#39;s Truth-images-0" src="https://github.com/user-attachments/assets/8f0b5931-1283-4ff2-aa05-f7e0bca4baf4" />

<br>

<img width="2550" height="3300" alt="G10 - A Bookmark&#39;s Truth-images-1" src="https://github.com/user-attachments/assets/f1aff0d6-4042-4f3b-8050-98ad0e532efe" />

<br>

<img width="2550" height="3300" alt="G10 - A Bookmark&#39;s Truth-images-7" src="https://github.com/user-attachments/assets/851bbfd2-8de3-441f-accb-a6e3309b0e9b" />

<br>

<img width="656" height="808" alt="Screenshot 2026-05-07 002129" src="https://github.com/user-attachments/assets/8c03f761-88c7-4c51-b99a-eb09e964fd55" />

<br>

<img width="657" height="807" alt="Screenshot 2026-05-07 002231" src="https://github.com/user-attachments/assets/1f87d518-89ef-47d7-8e87-34b2b9b247e1" />



## Features

- Grade-calibrated stories (1–12) in any genre you specify
- Approve / revise loop — request edits until the story is right
- Auto-generated short and long answer questions, tuned to grade level
- Teacher edition with concise bullet-point answer key
- Vocabulary reference page on both editions (advanced / uncommon words with definitions and examples)
- Anti-repetition: tracks prior worksheet titles to avoid clichéd phrasings

## Quick Start

Install runtime dependencies:

```bash
pip install openai reportlab
```

Set your OpenAI API key:

```powershell
setx OPENAI_API_KEY "sk-proj-..."
```

Then launch one of:

```bash
python gui.py     # windowed GUI
python main.py    # terminal CLI
```

## Build a standalone .exe (Windows)

```bash
build.bat
```

Produces `dist/WorksheetAgent.exe` — move it next to a `Worksheets/` folder and double-click. No Python required at runtime.

## Project structure

| File | Purpose |
| --- | --- |
| `core.py` | Shared logic: GPT calls, PDF building, anti-repetition |
| `gui.py`  | Tkinter GUI entry point |
| `main.py` | Terminal CLI entry point |
| `gui.spec` | PyInstaller spec for building the .exe |
| `build.bat` | One-click build script |

## License

MIT — see [LICENSE](LICENSE).
