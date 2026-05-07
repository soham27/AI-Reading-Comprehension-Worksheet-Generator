"""
=============================================================
  Reading Comprehension Worksheet AI Agent  —  CLI entry point
  For English Teachers | Powered by OpenAI GPT-4
=============================================================
  Install dependencies before running:
    pip install openai reportlab

  Set your API key as an environment variable:
    Windows:  set OPENAI_API_KEY=your_key_here
    Mac/Linux: export OPENAI_API_KEY=your_key_here

  Or paste it directly when prompted at startup.

  For a windowed GUI version, run `python gui.py` instead
  (or use the packaged WorksheetAgent.exe).
=============================================================
"""

import os
import sys
import textwrap
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI

from core import (
    GRADE_DESCRIPTORS,
    generate_story, revise_story, generate_questions,
    generate_answers, generate_vocabulary,
    create_pdf, build_output_path,
)


# ════════════════════════════════════════════════════════════
#  CLI HELPER UTILITIES
# ════════════════════════════════════════════════════════════

def print_banner():
    print("\n" + "═" * 62)
    print("   📚  Reading Comprehension Worksheet Generator")
    print("   Powered by GPT-4  |  For English Educators")
    print("═" * 62 + "\n")


def divider(char="─", width=62):
    print(char * width)


def ask(prompt: str, valid_options: list = None, cast=str) -> str:
    """Prompt the teacher for input with optional validation."""
    while True:
        raw = input(f"  {prompt} ").strip()
        if not raw:
            print("  ⚠  Please enter a value.\n")
            continue
        try:
            value = cast(raw)
        except (ValueError, TypeError):
            print(f"  ⚠  Please enter a valid number.\n")
            continue
        if valid_options and value not in valid_options:
            print(f"  ⚠  Choose from: {', '.join(str(v) for v in valid_options)}\n")
            continue
        return value


def wrap_print(text: str, width: int = 90, indent: str = "  "):
    """Pretty-print long text blocks."""
    paragraphs = text.split("\n")
    for para in paragraphs:
        if para.strip() == "":
            print()
        else:
            wrapped = textwrap.fill(para, width=width, initial_indent=indent,
                                    subsequent_indent=indent)
            print(wrapped)


def get_api_key() -> str:
    """Retrieve OpenAI API key from environment or prompt."""
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if key:
        print("  ✅  API key loaded from environment variable.\n")
        return key
    print("  🔑  No OPENAI_API_KEY environment variable found.")
    key = input("  Paste your OpenAI API key here: ").strip()
    if not key:
        print("  ✖  No API key provided. Exiting.")
        sys.exit(1)
    return key


# ════════════════════════════════════════════════════════════
#  MAIN AGENT LOOP
# ════════════════════════════════════════════════════════════

def collect_inputs() -> dict:
    """Interactively collect worksheet parameters from the teacher."""
    divider()
    print("  📋  Let's set up your worksheet. Answer the prompts below.\n")

    grade = ask("What grade level is this for? (1–12):", cast=int,
                valid_options=list(range(1, 13)))

    print(f"\n  ✅  Grade {grade} selected: {GRADE_DESCRIPTORS[grade]}\n")

    genre = ask("What genre should the story be?\n"
                "    (e.g. adventure, mystery, science fiction, historical fiction,\n"
                "           realistic fiction, fantasy, fable, horror, drama):\n  →")

    lengths = ["short", "medium", "long"]
    length = ask("How long should the story be?\n"
                 "    short (~250 words) / medium (~475 words) / long (~800 words):\n  →",
                 valid_options=lengths)

    num_short = ask("How many short-answer questions? (1–10):", cast=int,
                    valid_options=list(range(1, 11)))

    num_long = ask("How many long-answer questions? (0–5):", cast=int,
                   valid_options=list(range(0, 6)))

    return {
        "grade": grade,
        "genre": genre,
        "length": length,
        "num_short": num_short,
        "num_long": num_long,
    }


def run_agent():
    print_banner()

    # ── API key setup ────────────────────────────────────────
    api_key = get_api_key()
    client = OpenAI(api_key=api_key)

    # ── Gather inputs ────────────────────────────────────────
    inputs = collect_inputs()

    # ── Story generation & approval loop ─────────────────────
    approved = False
    story = None
    attempt = 0

    while not approved:
        attempt += 1
        divider()
        if attempt == 1:
            print(f"\n  ✍️   Generating your Grade {inputs['grade']} {inputs['genre']} story...\n")
            story = generate_story(client, inputs["genre"], inputs["length"], inputs["grade"])
        else:
            feedback = input(
                "\n  📝  Please describe what you'd like changed or improved:\n  → "
            ).strip()
            if not feedback:
                feedback = "Please try a different story with different content."
            print(f"\n  🔄  Revising the story based on your feedback...\n")
            story = revise_story(client, inputs["genre"], inputs["length"],
                                 inputs["grade"], story, feedback)

        # Display the story
        divider("═")
        print()
        wrap_print(story)
        print()
        divider("═")

        # Ask for approval
        print("\n  👆  Review the story above.")
        approval = ask(
            "Do you approve this story? (yes / no):",
            valid_options=["yes", "no", "y", "n", "YES", "NO", "Y", "N"]
        ).lower()

        if approval in ("yes", "y"):
            approved = True
        else:
            print("\n  👍  No problem — let's improve it!")

    # ── Generate questions ───────────────────────────────────
    divider()
    print(f"\n  ❓  Generating {inputs['num_short']} short-answer and "
          f"{inputs['num_long']} long-answer questions...\n")

    questions = generate_questions(
        client, story, inputs["grade"],
        inputs["num_short"], inputs["num_long"]
    )

    # Show questions to teacher
    print("  Generated questions preview:")
    print()
    if questions["short"]:
        print("  SHORT ANSWER:")
        for i, q in enumerate(questions["short"], 1):
            wrap_print(f"{i}. {q}", indent="    ")
    if questions["long"]:
        print("\n  LONG ANSWER:")
        for i, q in enumerate(questions["long"], 1):
            wrap_print(f"{i}. {q}", indent="    ")
    print()

    # ── Generate teacher-edition extras (in parallel) ────────
    divider()
    print("\n  ✏️   Generating answer key and vocabulary list for the teacher's edition (in parallel)...\n")
    with ThreadPoolExecutor(max_workers=2) as pool:
        answers_future = pool.submit(generate_answers, client, story, questions, inputs["grade"])
        vocabulary_future = pool.submit(generate_vocabulary, client, story, inputs["grade"])
        answers = answers_future.result()
        vocabulary = vocabulary_future.result()

    # ── Build both PDFs ──────────────────────────────────────
    student_path = build_output_path(inputs["grade"], story, teacher=False)
    teacher_path = build_output_path(inputs["grade"], story, teacher=True)

    divider()
    print(f"\n  📄  Building student PDF: {os.path.basename(student_path)}")
    print(f"  📄  Building teacher PDF: {os.path.basename(teacher_path)}\n")

    try:
        create_pdf(
            output_path=student_path,
            story_text=story,
            questions=questions,
            grade=inputs["grade"],
            genre=inputs["genre"],
            vocabulary=vocabulary,
        )
        create_pdf(
            output_path=teacher_path,
            story_text=story,
            questions=questions,
            grade=inputs["grade"],
            genre=inputs["genre"],
            answers=answers,
            vocabulary=vocabulary,
        )
        divider("═")
        print(f"\n  🎉  Done! Your worksheets have been saved to:\n")
        print(f"       📁  {student_path}")
        print(f"       📁  {teacher_path}\n")
        divider("═")
    except Exception as e:
        print(f"\n  ✖  Error creating PDF: {e}")
        print("  Make sure reportlab is installed: pip install reportlab\n")
        sys.exit(1)


# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    run_agent()
