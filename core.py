"""
Shared logic for the Reading Comprehension Worksheet AI Agent.

Contains:
- GPT calls (story / revise / questions / answers / vocabulary)
- PDF building (student and teacher editions)
- Path helpers (Worksheets folder resolution, filename construction)
- Anti-repetition machinery (story seeds + prior-title avoidance)

Both `main.py` (CLI) and `gui.py` (tkinter GUI) import from this module.
"""

import os
import re
import sys
import glob
import json
import random

from openai import OpenAI

# ── ReportLab imports ────────────────────────────────────────
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, PageBreak,
    KeepTogether, Table, TableStyle
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY


# ════════════════════════════════════════════════════════════
#  GRADE LEVEL DESCRIPTORS
# ════════════════════════════════════════════════════════════

GRADE_DESCRIPTORS = {
    1:  "Grade 1 (age 6-7): Very simple sentences, basic sight words, simple 3-5 sentence stories about everyday life.",
    2:  "Grade 2 (age 7-8): Simple sentences, common vocabulary, short stories of 1-2 short paragraphs.",
    3:  "Grade 3 (age 8-9): Compound sentences, slightly varied vocabulary, 2-3 paragraph stories with a clear beginning, middle, end.",
    4:  "Grade 4 (age 9-10): Varied sentence structure, descriptive language, 3-4 paragraphs, basic plot and character.",
    5:  "Grade 5 (age 10-11): Multi-paragraph stories with clear themes, figurative language introduced (simile, metaphor), moderate vocabulary.",
    6:  "Grade 6 (age 11-12): Strong paragraph structure, richer vocabulary, introduced to point of view, foreshadowing, and mood.",
    7:  "Grade 7 (age 12-13): Complex sentences, well-developed characters, themes, conflict, and resolution. Introduce alliteration, hyperbole.",
    8:  "Grade 8 (age 13-14): Sophisticated vocabulary, multi-layered plot, use of irony, symbolism, and imagery.",
    9:  "Grade 9 (age 14-15): Literary analysis level — allusion, tone shifts, narrative perspective, complex themes, varied syntax.",
    10: "Grade 10 (age 15-16): Deep literary devices — motif, allegory, dramatic irony, extended metaphor, unreliable narrator.",
    11: "Grade 11 (age 16-17): University-prep level — nuanced themes, intertextuality, stylistic choices, social/political subtext.",
    12: "Grade 12 (age 17-18): Near-university level — sophisticated prose, ambiguity, philosophical undertones, author's craft discussion.",
}

GRADE_QUESTION_GUIDANCE = {
    range(1, 4):  "simple recall questions (who, what, where). Questions should be answerable in 1-2 sentences.",
    range(4, 6):  "recall and basic inference questions. Short answers: 2-3 sentences. Long answers: 4-5 sentences with a reason.",
    range(6, 8):  "comprehension and inference questions. Short answers: 3-4 sentences. Long answers: a full paragraph with textual evidence.",
    range(8, 10): "inference, theme, and literary device questions. Short answers: 4-5 sentences. Long answers: two well-structured paragraphs.",
    range(10, 13):"analytical questions requiring identification of literary devices, themes, author's craft, and supported arguments. Short answers: 5-6 sentences with quotes. Long answers: 3 structured paragraphs (claim, evidence, analysis).",
}


def get_question_guidance(grade: int) -> str:
    for grade_range, guidance in GRADE_QUESTION_GUIDANCE.items():
        if grade in grade_range:
            return guidance
    return "age-appropriate comprehension questions."


# ════════════════════════════════════════════════════════════
#  PATH / FILENAME HELPERS
# ════════════════════════════════════════════════════════════

def sanitize_filename(name: str) -> str:
    """Strip characters that are invalid in Windows/Mac/Linux filenames."""
    for ch in '<>:"/\\|?*':
        name = name.replace(ch, "")
    return name.strip().rstrip(".")


def worksheets_dir() -> str:
    """Resolve the Worksheets folder.

    When frozen by PyInstaller, anchor relative to the .exe's location so the
    user's existing Worksheets folder (next to the .exe) is used. Otherwise,
    anchor relative to this source file.
    """
    if getattr(sys, "frozen", False):
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "Worksheets")


def build_output_path(grade: int, story_text: str, teacher: bool = False) -> str:
    """Return <base>/Worksheets/G{grade} - {title}[ (T)].pdf, creating the folder if needed."""
    out_dir = worksheets_dir()
    os.makedirs(out_dir, exist_ok=True)

    first_line = story_text.strip().split("\n", 1)[0]
    title = sanitize_filename(first_line.strip().strip("*#").strip()) or "Untitled"
    suffix = " (T)" if teacher else ""

    return os.path.join(out_dir, f"G{grade} - {title}{suffix}.pdf")


# ════════════════════════════════════════════════════════════
#  STORY DIVERSITY  (anti-repetition machinery)
# ════════════════════════════════════════════════════════════

# Words ignored when scanning prior titles for overused vocabulary.
TITLE_STOP_WORDS = {
    "the", "a", "an", "of", "and", "or", "in", "on", "to", "for",
    "with", "at", "from", "by", "as", "is", "are", "be", "into",
    "that", "this", "it", "its", "but", "if", "then", "than", "so",
}

# Concrete creative anchors. Each call samples one and forces the model to
# build the story around it — this is the main lever that breaks GPT-4o's
# default "Whispers/Echoes/Shadows of X" templates.
STORY_SEEDS = [
    # Specific objects
    "a lighthouse keeper's logbook discovered in the back of a city library",
    "a stolen metronome that ticks faster whenever someone in the room is lying",
    "a city bus that only runs between 3:00 and 3:17 a.m.",
    "a recipe handed down for four generations that lists no measurements",
    "a window that consistently shows yesterday's weather instead of today's",
    "a typewriter that auto-corrects sentences to truths the writer didn't intend",
    "a key that opens any lock exactly once, then refuses every other door",
    "a jar of buttons collected from the clothing of strangers",
    "a backyard well that returns whatever you whisper into it three days later",
    "a pocket watch missing its hour hand but otherwise running perfectly",
    "a single child's sock found deep in a forest, miles from any house",
    "a postage stamp from a country that does not exist",
    "an answering machine that records messages from people who never called",
    "a bookmark that always slips back to the page where the reader stopped reading honestly",
    # Specific characters
    "a retired weather forecaster who insists the sky is hiding something",
    "a twelve-year-old who has memorized every bus route in their city",
    "a former competitive speller who now runs a tiny overnight bakery",
    "two estranged siblings who collide by accident in a hardware store aisle",
    "a substitute teacher who knows every student's name on the first day",
    "a child convinced their reflection is exactly one second behind them",
    "a beekeeper who claims her bees can spell out names mid-flight",
    "an elderly piano tuner with perfect pitch and a quiet fear of melodies",
    # Specific settings
    "a public library where every book carries a handwritten note from a previous reader",
    "a town whose power fails for exactly twelve minutes every Tuesday at noon",
    "a community garden built on the foundations of a closed drive-in theater",
    "a high school whose lockers were salvaged from an abandoned train station",
    "a roadside diner that has been open continuously for forty-three years",
    "a fishing pier where the tide leaves behind objects people lost decades ago",
    "a bookstore basement filled with letters that were never delivered",
    # Structural twists
    "told entirely as a sequence of voicemails left on one answering machine",
    "told as the marginal notes left in the pages of a used textbook",
    "told as a packing list for a trip the narrator may not actually take",
    "told in second-person ('You step into the room…') throughout",
    "told as a series of weather reports across one strange summer",
    "told in reverse chronological order, ending at the beginning",
    "told as the transcript of a school's morning announcements over one week",
    "told as letters between two people who never meet face to face",
    "framed as a museum exhibit's placards, gradually revealing the story",
    # Situations
    "a small crime that nobody noticed except one bystander unsure it was a crime",
    "a family inheriting a house with one room they aren't allowed to renovate",
    "a found object that someone is desperately trying to return to its rightful owner",
    "a yearly tradition the town has performed every spring that nobody remembers starting",
    "a neighbor who waters a garden that doesn't belong to them",
    "a misdelivered package containing something more meaningful than its sender realized",
    "a chance reunion at the wrong funeral",
    "a quiet protest staged by a single person on a busy street corner",
]


def get_existing_titles() -> list:
    """Return distinct titles parsed from prior worksheet filenames (ignoring student/teacher pairs)."""
    out_dir = worksheets_dir()
    if not os.path.isdir(out_dir):
        return []
    titles = set()
    for path in glob.glob(os.path.join(out_dir, "G* - *.pdf")):
        name = os.path.basename(path)
        m = re.match(r"^G\d+\s*-\s*(.+?)(?:\s*\(T\))?\.pdf$", name, flags=re.IGNORECASE)
        if m:
            titles.add(m.group(1).strip())
    return sorted(titles)


def extract_overused_words(titles: list) -> list:
    """Return distinct content words used in prior titles, lowercased and sorted."""
    words = set()
    for title in titles:
        for w in re.findall(r"[A-Za-z']+", title.lower()):
            if len(w) > 2 and w not in TITLE_STOP_WORDS:
                words.add(w)
    return sorted(words)


def pick_story_seed() -> str:
    return random.choice(STORY_SEEDS)


# ════════════════════════════════════════════════════════════
#  OPENAI AGENT CALLS
# ════════════════════════════════════════════════════════════

def generate_story(client: OpenAI, genre: str, length: str, grade: int) -> str:
    """Generate a reading comprehension story via GPT-4."""
    grade_desc = GRADE_DESCRIPTORS.get(grade, f"Grade {grade}")
    length_map = {"short": "200-300 words", "medium": "400-550 words", "long": "700-900 words"}
    word_target = length_map.get(length, "400-550 words")

    seed = pick_story_seed()
    prior_titles = get_existing_titles()
    overused = extract_overused_words(prior_titles)

    avoid_block = ""
    if overused:
        avoid_block += (
            f"\n- Do NOT reuse any of these words anywhere in the title "
            f"(they appeared in earlier worksheets): {', '.join(overused)}."
        )
    if prior_titles:
        avoid_block += (
            f"\n- Do NOT write a title that resembles any of these prior titles: "
            f"{'; '.join(prior_titles)}."
        )

    system_prompt = (
        "You are an expert curriculum writer specializing in reading comprehension passages "
        "for K-12 English education. You write engaging, age-appropriate stories that "
        "naturally embed opportunities for literary analysis and comprehension questions. "
        "You actively resist clichéd 'literary' titles and templates."
    )

    user_prompt = f"""
Write a {genre} reading comprehension story for {grade_desc}.

Build the story around this concrete anchor (treat it as the seed of the plot, NOT as a line to quote verbatim):
{seed}

Requirements:
- Length: {word_target}
- Genre: {genre}
- Writing level: Precisely calibrated for {grade_desc}
- The story must have a clear title, natural paragraph breaks, and rich content
  that supports {get_question_guidance(grade)}
- Do NOT include any questions in the story
- Output ONLY the story title (on its own line), followed by the story text
- Make it genuinely engaging and creative — students should enjoy reading it

Title rules (strict):
- Do NOT use the templates "The X of [the] Y", "Whispers of …", "Echo(es) of …", "Shadow(s) of …", "Silence of …", or any variation of these.
- Do NOT use the words: whisper, whispers, whispering, echo, echoes, echoing, shadow, shadows, silence, solitude, secret, secrets, forgotten, lost, hidden, beyond.
- Prefer titles that are specific and concrete: a place name, a person's name, a small object, a date, a question, or an unusual phrase.{avoid_block}
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.95,
        presence_penalty=0.6,
        max_tokens=1500,
    )
    return response.choices[0].message.content.strip()


def revise_story(client: OpenAI, genre: str, length: str, grade: int,
                 previous_story: str, feedback: str) -> str:
    """Revise the story based on teacher feedback."""
    grade_desc = GRADE_DESCRIPTORS.get(grade, f"Grade {grade}")
    length_map = {"short": "200-300 words", "medium": "400-550 words", "long": "700-900 words"}
    word_target = length_map.get(length, "400-550 words")

    system_prompt = (
        "You are an expert curriculum writer specializing in reading comprehension passages "
        "for K-12 English education. You revise stories based on teacher feedback while "
        "maintaining appropriate grade-level writing and engagement."
    )

    user_prompt = f"""
The following reading comprehension story was written for {grade_desc} ({genre} genre, {word_target}).

--- PREVIOUS STORY ---
{previous_story}
--- END STORY ---

The teacher was not satisfied and provided this feedback:
"{feedback}"

Please revise the story to fully address the teacher's feedback while keeping it:
- Appropriate for {grade_desc}
- Around {word_target} in length
- In the {genre} genre
- Rich enough to support comprehension questions

Title rules (strict — apply even if the teacher's feedback didn't mention the title):
- Do NOT use the templates "The X of [the] Y", "Whispers of …", "Echo(es) of …", "Shadow(s) of …", "Silence of …", or any variation of these.
- Do NOT use the words: whisper, whispers, whispering, echo, echoes, echoing, shadow, shadows, silence, solitude, secret, secrets, forgotten, lost, hidden, beyond.
- Prefer titles that are specific and concrete: a place name, a person's name, a small object, a date, a question, or an unusual phrase.

Output ONLY the revised story title (on its own line), followed by the revised story text.
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.9,
        presence_penalty=0.4,
        max_tokens=1500,
    )
    return response.choices[0].message.content.strip()


def generate_questions(client: OpenAI, story: str, grade: int,
                       num_short: int, num_long: int) -> dict:
    """Generate short and long answer questions for the approved story."""
    grade_desc = GRADE_DESCRIPTORS.get(grade, f"Grade {grade}")
    question_guidance = get_question_guidance(grade)

    system_prompt = (
        "You are an expert English teacher and curriculum designer. "
        "You write thoughtful, grade-appropriate reading comprehension questions "
        "that test a range of skills from recall to literary analysis."
    )

    user_prompt = f"""
Based on the following reading comprehension story written for {grade_desc},
create exactly {num_short} short-answer questions and {num_long} long-answer questions.

Story:
{story}

Question guidelines for this grade:
{question_guidance}

Format your response EXACTLY as follows (use these exact headers):
SHORT ANSWER QUESTIONS:
1. [question]
2. [question]
...

LONG ANSWER QUESTIONS:
1. [question]
2. [question]
...

Rules:
- Short answer questions should be specific and answerable concisely
- Long answer questions should require analysis, explanation, or personal response with evidence
- Questions must be directly tied to the story content
- For grades 8+, at least one question per section should address a literary device or author's craft
- Do not include model answers
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.6,
        max_tokens=1200,
    )

    raw = response.choices[0].message.content.strip()
    return parse_questions(raw, num_short, num_long)


def parse_questions(raw: str, num_short: int, num_long: int) -> dict:
    """Parse GPT question output into structured lists."""
    short_questions = []
    long_questions = []
    current_section = None

    for line in raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        if "SHORT ANSWER" in line.upper():
            current_section = "short"
            continue
        if "LONG ANSWER" in line.upper():
            current_section = "long"
            continue
        # Match numbered lines like "1.", "2.", etc.
        if line and line[0].isdigit() and "." in line[:3]:
            question_text = line.split(".", 1)[-1].strip()
            if current_section == "short":
                short_questions.append(question_text)
            elif current_section == "long":
                long_questions.append(question_text)

    return {
        "short": short_questions[:num_short],
        "long": long_questions[:num_long],
    }


def generate_answers(client: OpenAI, story: str, questions: dict, grade: int) -> dict:
    """Produce a bullet-form answer key for every question (teacher reference)."""
    grade_desc = GRADE_DESCRIPTORS.get(grade, f"Grade {grade}")

    short_qs = "\n".join(f"{i}. {q}" for i, q in enumerate(questions.get("short", []), 1)) or "(none)"
    long_qs = "\n".join(f"{i}. {q}" for i, q in enumerate(questions.get("long", []), 1)) or "(none)"

    system_prompt = (
        "You are an expert English teacher creating an answer key for reading "
        "comprehension questions. You write concise, bullet-form answers that "
        "capture the key ideas a strong student at the target grade level should "
        "include. Each bullet is one short clause or sentence."
    )

    user_prompt = f"""
Below is a reading comprehension story written for {grade_desc}, followed by short-answer
and long-answer questions. Produce a concise bullet-point answer key for every question.

Story:
{story}

SHORT-ANSWER QUESTIONS:
{short_qs}

LONG-ANSWER QUESTIONS:
{long_qs}

Output strictly as JSON with this exact shape:
{{
  "short": [["bullet 1", "bullet 2", "..."], "..."],
  "long":  [["bullet 1", "bullet 2", "..."], "..."]
}}
- The "short" array must have one inner list per short-answer question, in order.
- The "long" array must have one inner list per long-answer question, in order.

Bullet rules:
- Short-answer key: 2-4 short bullets per question.
- Long-answer key: 4-7 short bullets per question, organized as claim / evidence / analysis where appropriate.
- Each bullet is one clause or short sentence — never a full paragraph.
- Do NOT include the question text in the bullets.
- For grades 8+, when a question targets a literary device, name the device explicitly in a bullet.
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        response_format={"type": "json_object"},
        max_tokens=1800,
    )

    data = json.loads(response.choices[0].message.content)
    return {
        "short": data.get("short", []),
        "long": data.get("long", []),
    }


def generate_vocabulary(client: OpenAI, story: str, grade: int) -> list:
    """Extract advanced/uncommon words from the passage with definitions and examples."""
    grade_desc = GRADE_DESCRIPTORS.get(grade, f"Grade {grade}")

    system_prompt = (
        "You are an expert English teacher building a vocabulary reference for a "
        "reading comprehension worksheet. You select words that are genuinely "
        "advanced or uncommon for the target grade level and provide clear, "
        "age-appropriate definitions."
    )

    user_prompt = f"""
Below is a reading comprehension story written for {grade_desc}.

Identify every word from the passage that meets at least one of these criteria:
- Uncommon in everyday colloquial speech for {grade_desc} students.
- Advanced for {grade_desc} (i.e., would meaningfully stretch a student at that grade).
- Domain-specific, formal, or literary vocabulary.

Skip words that are common everyday vocabulary at this grade. Aim for between 6 and 18 words
depending on the passage's actual difficulty — do not pad the list.

Story:
{story}

Output strictly as JSON with this exact shape:
{{
  "words": [
    {{
      "word": "lemma form of the word (e.g. 'vanish' not 'vanishing')",
      "definition": "One short, clear, dictionary-style definition appropriate for {grade_desc}.",
      "example": "An example sentence — preferably the actual sentence from the passage where the word appears, otherwise a representative short sentence."
    }}
  ]
}}

Rules:
- Sort the words alphabetically by the "word" field.
- Definitions: one sentence, no jargon, age-appropriate.
- Examples: prefer the passage sentence (shortened if very long) so students can locate it in context.
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
        max_tokens=1800,
    )

    data = json.loads(response.choices[0].message.content)
    return data.get("words", [])


# ════════════════════════════════════════════════════════════
#  PDF GENERATION  (ReportLab)
# ════════════════════════════════════════════════════════════

def build_styles() -> dict:
    """Build a set of custom paragraph styles for the worksheet."""
    base = getSampleStyleSheet()

    styles = {
        "doc_title": ParagraphStyle(
            "DocTitle",
            parent=base["Title"],
            fontSize=20,
            textColor=colors.HexColor("#1a1a2e"),
            spaceAfter=4,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
        ),
        "doc_subtitle": ParagraphStyle(
            "DocSubtitle",
            parent=base["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#555555"),
            spaceAfter=2,
            alignment=TA_CENTER,
            fontName="Helvetica",
        ),
        "story_title": ParagraphStyle(
            "StoryTitle",
            parent=base["Heading1"],
            fontSize=15,
            textColor=colors.HexColor("#1a1a2e"),
            spaceBefore=14,
            spaceAfter=8,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
        ),
        "section_header": ParagraphStyle(
            "SectionHeader",
            parent=base["Heading2"],
            fontSize=12,
            textColor=colors.white,
            backColor=colors.HexColor("#1a1a2e"),
            spaceBefore=16,
            spaceAfter=10,
            leftIndent=-12,
            rightIndent=-12,
            fontName="Helvetica-Bold",
            borderPad=5,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["Normal"],
            fontSize=11,
            leading=17,
            spaceAfter=8,
            alignment=TA_JUSTIFY,
            fontName="Helvetica",
        ),
        "question_label": ParagraphStyle(
            "QuestionLabel",
            parent=base["Normal"],
            fontSize=11,
            leading=15,
            spaceBefore=10,
            spaceAfter=4,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor("#1a1a2e"),
        ),
        "question_text": ParagraphStyle(
            "QuestionText",
            parent=base["Normal"],
            fontSize=11,
            leading=15,
            spaceAfter=2,
            fontName="Helvetica",
        ),
        "answer_line_label": ParagraphStyle(
            "AnswerLabel",
            parent=base["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#888888"),
            spaceBefore=4,
            spaceAfter=2,
            fontName="Helvetica-Oblique",
        ),
        "name_line": ParagraphStyle(
            "NameLine",
            parent=base["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#333333"),
            fontName="Helvetica",
            spaceAfter=4,
        ),
        "answer_key_label": ParagraphStyle(
            "AnswerKeyLabel",
            parent=base["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#1a1a2e"),
            spaceBefore=4,
            spaceAfter=2,
            fontName="Helvetica-BoldOblique",
        ),
        "answer_bullet": ParagraphStyle(
            "AnswerBullet",
            parent=base["Normal"],
            fontSize=10,
            leading=14,
            leftIndent=18,
            spaceAfter=2,
            fontName="Helvetica",
            textColor=colors.HexColor("#333333"),
        ),
        "vocab_word": ParagraphStyle(
            "VocabWord",
            parent=base["Normal"],
            fontSize=11,
            textColor=colors.HexColor("#1a1a2e"),
            spaceBefore=10,
            spaceAfter=2,
            fontName="Helvetica-Bold",
        ),
        "vocab_def": ParagraphStyle(
            "VocabDef",
            parent=base["Normal"],
            fontSize=10,
            leading=14,
            leftIndent=14,
            spaceAfter=2,
            fontName="Helvetica",
        ),
        "vocab_example": ParagraphStyle(
            "VocabExample",
            parent=base["Normal"],
            fontSize=10,
            leading=14,
            leftIndent=14,
            spaceAfter=4,
            fontName="Helvetica-Oblique",
            textColor=colors.HexColor("#555555"),
        ),
    }
    return styles


def answer_lines(count: int = 4) -> list:
    """Return a list of blank answer line flowables with generous handwriting spacing."""
    elements = []
    for _ in range(count):
        elements.append(Spacer(1, 10))
        elements.append(HRFlowable(width="100%", thickness=0.5,
                                   color=colors.HexColor("#cccccc"),
                                   hAlign="LEFT", spaceAfter=14))
    return elements


def lines_for_answer(grade: int, kind: str) -> int:
    """Scale the number of writing lines to grade level and question type.

    Higher grades expect longer responses (per GRADE_QUESTION_GUIDANCE), and
    long-answer questions always get noticeably more space than short-answer.
    """
    if kind == "short":
        if grade <= 3:  return 3
        if grade <= 5:  return 4
        if grade <= 7:  return 5
        if grade <= 9:  return 6
        return 8
    # long answer
    if grade <= 3:  return 5
    if grade <= 5:  return 8
    if grade <= 7:  return 11
    if grade <= 9:  return 15
    return 20


def create_pdf(output_path: str, story_text: str, questions: dict,
               grade: int, genre: str,
               answers: dict = None, vocabulary: list = None):
    """Build a worksheet PDF.

    Student version: blank answer lines after each question.
    Teacher version: provide `answers` (dict matching `questions` shape, but with
        bullet-list values) to render an answer key in place of the lines.
    Vocabulary page: provide `vocabulary` (list of {word, definition, example})
        to append a vocab reference page (works for either version).
    """
    is_teacher = answers is not None

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=0.9 * inch,
        leftMargin=0.9 * inch,
        topMargin=0.9 * inch,
        bottomMargin=0.9 * inch,
    )

    styles = build_styles()
    story_elements = []

    # ── Header block ────────────────────────────────────────
    title_text = "Reading Comprehension — Teacher Edition" if is_teacher else "Reading Comprehension Worksheet"
    story_elements.append(Paragraph(title_text, styles["doc_title"]))
    story_elements.append(Paragraph(
        f"Grade {grade} &nbsp;|&nbsp; {genre.title()}",
        styles["doc_subtitle"]
    ))
    story_elements.append(Spacer(1, 6))
    story_elements.append(HRFlowable(width="100%", thickness=1.5,
                                     color=colors.HexColor("#1a1a2e"), spaceAfter=10))

    # ── Student info fields (student version only) ──────────
    if not is_teacher:
        info_data = [
            [Paragraph("Name: ___________________________________", styles["name_line"]),
             Paragraph("Date: ____________________", styles["name_line"])],
        ]
        info_table = Table(info_data, colWidths=[4 * inch, 2.8 * inch])
        info_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story_elements.append(info_table)
        story_elements.append(Spacer(1, 8))

    # ── Reading passage section ──────────────────────────────
    story_elements.append(Paragraph("&#9632; &nbsp; Reading Passage", styles["section_header"]))

    # Split story into title + body
    lines = story_text.strip().split("\n")
    passage_title = lines[0].strip().strip("*#").strip()
    passage_body = "\n".join(lines[1:]).strip()

    story_elements.append(Paragraph(passage_title, styles["story_title"]))

    for para in passage_body.split("\n"):
        para = para.strip()
        if para:
            story_elements.append(Paragraph(para, styles["body"]))

    story_elements.append(Spacer(1, 10))

    def render_question_block(kind: str, header: str, instructions: str):
        qs = questions.get(kind) or []
        if not qs:
            return
        story_elements.append(Paragraph(header, styles["section_header"]))
        if not is_teacher:
            story_elements.append(Paragraph(instructions, styles["answer_line_label"]))
        story_elements.append(Spacer(1, 6))

        bullets_for_q = (answers.get(kind, []) if is_teacher else None)

        for i, q in enumerate(qs, 1):
            block = [
                Paragraph(f"Question {i}.", styles["question_label"]),
                Paragraph(q, styles["question_text"]),
                Spacer(1, 4),
            ]
            if is_teacher:
                block.append(Paragraph("Answer key:", styles["answer_key_label"]))
                bullets = bullets_for_q[i - 1] if (bullets_for_q and i - 1 < len(bullets_for_q)) else []
                if bullets:
                    for b in bullets:
                        block.append(Paragraph(f"&#8226;&nbsp;&nbsp;{b}", styles["answer_bullet"]))
                else:
                    block.append(Paragraph("(no answer generated)", styles["answer_bullet"]))
            else:
                block += answer_lines(lines_for_answer(grade, kind))
            story_elements.append(KeepTogether(block))

    render_question_block(
        "short",
        "&#9632; &nbsp; Part A — Short Answer Questions",
        "Answer each question in 1–3 complete sentences.",
    )
    story_elements.append(Spacer(1, 12))
    render_question_block(
        "long",
        "&#9632; &nbsp; Part B — Long Answer Questions",
        "Answer each question in full paragraphs with supporting detail from the text.",
    )

    # ── Vocabulary page ──────────────────────────────────────
    if vocabulary:
        story_elements.append(PageBreak())
        story_elements.append(Paragraph(
            "&#9632; &nbsp; Vocabulary Reference",
            styles["section_header"]
        ))
        story_elements.append(Spacer(1, 6))

        for entry in vocabulary:
            word = (entry.get("word") or "").strip()
            definition = (entry.get("definition") or "").strip()
            example = (entry.get("example") or "").strip()
            if not word:
                continue
            block = [Paragraph(word, styles["vocab_word"])]
            if definition:
                block.append(Paragraph(definition, styles["vocab_def"]))
            if example:
                block.append(Paragraph(f"<i>Example:</i> {example}", styles["vocab_example"]))
            story_elements.append(KeepTogether(block))

    doc.build(story_elements)
