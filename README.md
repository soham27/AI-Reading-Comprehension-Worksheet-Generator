# AI Reading Comprehension Worksheet Generator

A polished, classroom-ready reading comprehension worksheet that you can generate **in seconds** with this AI agent powered by GPT-4. An AI-generated story that can be however long you want it to be, with a layered set of short and long answer questions whose depth scales with your class's grade, and a vocabulary page listing the passage's most advanced terms with definitions and example sentences. 

Each worksheet ships in two matching editions: a **student edition** with clean handwriting-ready answer lines beneath every question, and a **teacher edition** with a concise bullet-point answer key in place of the lines (claim, evidence, and analysis at the higher grades). Both are PDFs, ready to print and hand out to a class.

📄 [View a full sample student worksheet (PDF)](Worksheets/G10%20-%20A%20Bookmark's%20Truth.pdf)

<br>

<img width="656" height="529" alt="Screenshot 2026-05-07 002129" src="https://github.com/user-attachments/assets/3f02716c-865b-4e74-b180-2f5b8f77fee1" />

<br>

<img width="2550" height="3300" alt="G10 - A Bookmark&#39;s Truth-images-0" src="https://github.com/user-attachments/assets/8f0b5931-1283-4ff2-aa05-f7e0bca4baf4" />

<br>

<img width="2550" height="3300" alt="G10 - A Bookmark&#39;s Truth-images-1" src="https://github.com/user-attachments/assets/f1aff0d6-4042-4f3b-8050-98ad0e532efe" />

<br>

<img width="2550" height="3300" alt="G10 - A Bookmark&#39;s Truth-images-7" src="https://github.com/user-attachments/assets/851bbfd2-8de3-441f-accb-a6e3309b0e9b" />

<br>



## Features

- Grade-calibrated stories (1–12) in any genre you specify
- Approve / revise loop — request edits until the story is right
- Auto-generated short and long answer questions, tuned to grade level
- Teacher edition with concise bullet-point answer key
- Vocabulary reference page on both editions (advanced / uncommon words with definitions and examples)

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
