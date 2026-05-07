# AI Reading Comprehension Worksheet Generator

A polished, classroom-ready reading comprehension worksheet that you can generate **in seconds** with this AI agent powered by GPT-4. An AI-generated story that can be however long you want it to be, with a layered set of short and long answer questions whose depth scales with your class's grade, and a vocabulary page listing the passage's most advanced terms with definitions and example sentences. 

🔎 [View a full sample student worksheet (PDF)](Worksheets/G8%20-%20Notebook%20on%20the%20Windowsill.pdf)

Each worksheet ships in two matching editions: a **student edition** with clean handwriting-ready answer lines beneath every question, and a **teacher edition** with a concise bullet-point answer key in place of the lines (claim, evidence, and analysis at the higher grades). Both are PDFs, ready to print and hand out to a class.

<img width="656" height="529" alt="Screenshot 2026-05-07 002129" src="https://github.com/user-attachments/assets/3f02716c-865b-4e74-b180-2f5b8f77fee1" />

<br>

<img width="1275" height="1650" alt="page-1" src="https://github.com/user-attachments/assets/503698c7-00bc-4e79-b710-855d4f4ab38e" />

<br>

<img width="1275" height="1650" alt="page-2" src="https://github.com/user-attachments/assets/08acbed7-2c3b-4689-b4ec-a07cce1316d8" />

<br>

<img width="1275" height="1650" alt="page-6" src="https://github.com/user-attachments/assets/17a947ac-591c-424b-b336-3353c4caae00" />

<br>

<img width="1275" height="1650" alt="page-7" src="https://github.com/user-attachments/assets/5f082a2a-08ca-418c-9e57-4e0d4354c04f" />

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
