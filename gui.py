"""
Reading Comprehension Worksheet AI Agent — windowed GUI.

Run with `python gui.py` (or via the packaged WorksheetAgent.exe). For the
terminal-based flow, use `python main.py` instead.
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from concurrent.futures import ThreadPoolExecutor

from openai import OpenAI

from core import (
    GRADE_DESCRIPTORS,
    generate_story, revise_story, generate_questions,
    generate_answers, generate_vocabulary,
    create_pdf, build_output_path, worksheets_dir,
)


PAD = 12
WINDOW_W = 660
WINDOW_H = 780


# ════════════════════════════════════════════════════════════
#  Top-level application controller
# ════════════════════════════════════════════════════════════

class WorksheetApp:
    """Controller — owns the Tk root, shared state, and frame switching."""

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Reading Comprehension Worksheet Generator")
        root.geometry(f"{WINDOW_W}x{WINDOW_H}")
        root.resizable(False, False)
        root.minsize(WINDOW_W, WINDOW_H)

        # Use a clean ttk theme.
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        elif "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("Heading.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("Status.TLabel", font=("Segoe UI", 10, "italic"), foreground="#555555")
        style.configure("Path.TLabel", font=("Consolas", 9), foreground="#1a1a2e")
        style.configure("Big.TButton", padding=(14, 8))

        # Shared state across frames.
        self.client: OpenAI | None = None
        self.inputs: dict = {}
        self.story: str | None = None
        self.questions: dict | None = None
        self.answers: dict | None = None
        self.vocabulary: list | None = None
        self.student_path: str | None = None
        self.teacher_path: str | None = None

        container = ttk.Frame(root, padding=PAD)
        container.pack(fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for FrameCls in (SetupFrame, ReviewFrame, BuildingFrame, DoneFrame):
            frame = FrameCls(container, self)
            self.frames[FrameCls.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show("SetupFrame")

    def show(self, name: str):
        frame = self.frames[name]
        frame.tkraise()
        if hasattr(frame, "on_show"):
            frame.on_show()

    def run_async(self, work, on_done):
        """Run `work()` in a worker thread; deliver result on main thread via after()."""
        def runner():
            try:
                result = work()
                self.root.after(0, lambda: on_done(result, None))
            except Exception as exc:
                self.root.after(0, lambda: on_done(None, exc))
        threading.Thread(target=runner, daemon=True).start()

    def reset_for_new_worksheet(self):
        self.story = None
        self.questions = None
        self.answers = None
        self.vocabulary = None
        self.student_path = None
        self.teacher_path = None


# ════════════════════════════════════════════════════════════
#  Setup frame — collect form inputs
# ════════════════════════════════════════════════════════════

class SetupFrame(ttk.Frame):
    def __init__(self, parent, app: WorksheetApp):
        super().__init__(parent, padding=PAD)
        self.app = app

        ttk.Label(self, text="📚  Reading Comprehension Worksheet Generator",
                  style="Title.TLabel").pack(pady=(0, 4))
        ttk.Label(self, text="Powered by GPT-4  ·  For English Educators",
                  style="Status.TLabel").pack(pady=(0, 14))

        form = ttk.Frame(self)
        form.pack(fill="x", expand=False)
        form.grid_columnconfigure(1, weight=1)

        row = 0

        # API key
        ttk.Label(form, text="OpenAI API Key:").grid(row=row, column=0, sticky="w", pady=4)
        self.api_key_var = tk.StringVar(value=os.getenv("OPENAI_API_KEY", "").strip())
        self.api_entry = ttk.Entry(form, textvariable=self.api_key_var, show="•", width=50)
        self.api_entry.grid(row=row, column=1, sticky="ew", pady=4, padx=(8, 0))
        row += 1

        env_status = "(loaded from OPENAI_API_KEY)" if self.api_key_var.get() else "(not found in environment — paste here)"
        ttk.Label(form, text=env_status, style="Status.TLabel").grid(
            row=row, column=1, sticky="w", padx=(8, 0), pady=(0, 10))
        row += 1

        # Grade
        ttk.Label(form, text="Grade level:").grid(row=row, column=0, sticky="w", pady=4)
        self.grade_var = tk.StringVar(value="9")
        grade_box = ttk.Combobox(form, textvariable=self.grade_var, state="readonly",
                                 values=[str(g) for g in range(1, 13)], width=6)
        grade_box.grid(row=row, column=1, sticky="w", pady=4, padx=(8, 0))
        row += 1

        self.grade_desc_var = tk.StringVar()
        ttk.Label(form, textvariable=self.grade_desc_var, style="Status.TLabel",
                  wraplength=WINDOW_W - 100).grid(row=row, column=1, sticky="w",
                                                  padx=(8, 0), pady=(0, 10))
        row += 1
        grade_box.bind("<<ComboboxSelected>>", lambda e: self._refresh_grade_desc())
        self._refresh_grade_desc()

        # Genre
        ttk.Label(form, text="Genre:").grid(row=row, column=0, sticky="w", pady=4)
        self.genre_var = tk.StringVar()
        genre_entry = ttk.Entry(form, textvariable=self.genre_var, width=40)
        genre_entry.grid(row=row, column=1, sticky="ew", pady=4, padx=(8, 0))
        row += 1
        ttk.Label(form, text="e.g. mystery, fantasy, historical fiction, realistic fiction…",
                  style="Status.TLabel").grid(row=row, column=1, sticky="w",
                                              padx=(8, 0), pady=(0, 10))
        row += 1

        # Length
        ttk.Label(form, text="Story length:").grid(row=row, column=0, sticky="w", pady=4)
        self.length_var = tk.StringVar(value="medium")
        length_frame = ttk.Frame(form)
        length_frame.grid(row=row, column=1, sticky="w", pady=4, padx=(8, 0))
        for label, value in [("Short (~250 words)", "short"),
                             ("Medium (~475 words)", "medium"),
                             ("Long (~800 words)", "long")]:
            ttk.Radiobutton(length_frame, text=label, variable=self.length_var,
                            value=value).pack(side="left", padx=(0, 12))
        row += 1
        ttk.Label(form, text="").grid(row=row, column=0, pady=4)  # spacer
        row += 1

        # Question counts
        ttk.Label(form, text="# Short-answer questions:").grid(row=row, column=0, sticky="w", pady=4)
        self.num_short_var = tk.IntVar(value=4)
        ttk.Spinbox(form, from_=1, to=10, textvariable=self.num_short_var, width=6).grid(
            row=row, column=1, sticky="w", pady=4, padx=(8, 0))
        row += 1

        ttk.Label(form, text="# Long-answer questions:").grid(row=row, column=0, sticky="w", pady=4)
        self.num_long_var = tk.IntVar(value=2)
        ttk.Spinbox(form, from_=0, to=5, textvariable=self.num_long_var, width=6).grid(
            row=row, column=1, sticky="w", pady=4, padx=(8, 0))
        row += 1

        # Generate button
        btn_row = ttk.Frame(self)
        btn_row.pack(fill="x", pady=(20, 0))
        ttk.Button(btn_row, text="✍️  Generate Story", style="Big.TButton",
                   command=self.on_generate).pack()

    def _refresh_grade_desc(self):
        try:
            grade = int(self.grade_var.get())
        except ValueError:
            grade = 9
        self.grade_desc_var.set(GRADE_DESCRIPTORS.get(grade, ""))

    def on_show(self):
        # Re-read env var in case it was set after launch.
        if not self.api_key_var.get():
            env_key = os.getenv("OPENAI_API_KEY", "").strip()
            if env_key:
                self.api_key_var.set(env_key)

    def on_generate(self):
        api_key = self.api_key_var.get().strip()
        genre = self.genre_var.get().strip()
        if not api_key:
            messagebox.showerror("Missing API key",
                                 "Please paste your OpenAI API key (or set the OPENAI_API_KEY environment variable before launching).")
            return
        if not genre:
            messagebox.showerror("Missing genre", "Please enter a story genre.")
            return
        try:
            grade = int(self.grade_var.get())
            num_short = int(self.num_short_var.get())
            num_long = int(self.num_long_var.get())
        except (ValueError, tk.TclError):
            messagebox.showerror("Invalid input", "Grade and question counts must be numbers.")
            return

        self.app.client = OpenAI(api_key=api_key)
        self.app.inputs = {
            "grade": grade,
            "genre": genre,
            "length": self.length_var.get(),
            "num_short": num_short,
            "num_long": num_long,
        }
        self.app.reset_for_new_worksheet()
        self.app.show("ReviewFrame")


# ════════════════════════════════════════════════════════════
#  Review frame — story display + approve/revise
# ════════════════════════════════════════════════════════════

class ReviewFrame(ttk.Frame):
    def __init__(self, parent, app: WorksheetApp):
        super().__init__(parent, padding=PAD)
        self.app = app

        ttk.Label(self, text="Story Review", style="Title.TLabel").pack(anchor="w")
        self.status_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.status_var, style="Status.TLabel").pack(
            anchor="w", pady=(2, 8))

        # Story text area (read-only).
        text_frame = ttk.Frame(self)
        text_frame.pack(fill="both", expand=True)
        self.story_text = tk.Text(text_frame, wrap="word", font=("Georgia", 11),
                                  padx=10, pady=10, borderwidth=1, relief="solid",
                                  state="disabled")
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.story_text.yview)
        self.story_text.configure(yscrollcommand=scrollbar.set)
        self.story_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.progress = ttk.Progressbar(self, mode="indeterminate")
        self.progress.pack(fill="x", pady=(8, 4))

        btn_row = ttk.Frame(self)
        btn_row.pack(fill="x", pady=(8, 0))
        self.approve_btn = ttk.Button(btn_row, text="✅  Approve & Build Worksheets",
                                      style="Big.TButton", command=self.on_approve)
        self.approve_btn.pack(side="right")
        self.revise_btn = ttk.Button(btn_row, text="🔄  Revise…", style="Big.TButton",
                                     command=self.on_revise)
        self.revise_btn.pack(side="right", padx=(0, 8))
        self.back_btn = ttk.Button(btn_row, text="← Back to Setup",
                                   command=lambda: self.app.show("SetupFrame"))
        self.back_btn.pack(side="left")

    def on_show(self):
        if self.app.story is None:
            # First entry — generate fresh story.
            self._set_busy(True, "Generating your Grade {} {} story…".format(
                self.app.inputs["grade"], self.app.inputs["genre"]))
            self._clear_story()
            self.app.run_async(
                lambda: generate_story(
                    self.app.client,
                    self.app.inputs["genre"],
                    self.app.inputs["length"],
                    self.app.inputs["grade"],
                ),
                self._on_story_ready,
            )
        else:
            # Returning to this frame after a successful build (Generate another) — shouldn't happen
            # because we route through SetupFrame, but render whatever we have.
            self._render_story(self.app.story)
            self._set_busy(False, "Review the story below.")

    def _set_busy(self, busy: bool, status: str):
        self.status_var.set(status)
        if busy:
            self.progress.start(12)
            self.approve_btn.state(["disabled"])
            self.revise_btn.state(["disabled"])
            self.back_btn.state(["disabled"])
        else:
            self.progress.stop()
            self.approve_btn.state(["!disabled"])
            self.revise_btn.state(["!disabled"])
            self.back_btn.state(["!disabled"])

    def _clear_story(self):
        self.story_text.configure(state="normal")
        self.story_text.delete("1.0", "end")
        self.story_text.configure(state="disabled")

    def _render_story(self, story: str):
        self.story_text.configure(state="normal")
        self.story_text.delete("1.0", "end")
        self.story_text.insert("1.0", story)
        self.story_text.configure(state="disabled")

    def _on_story_ready(self, story, exc):
        if exc is not None:
            self._set_busy(False, "")
            messagebox.showerror("Story generation failed", str(exc))
            self.app.show("SetupFrame")
            return
        self.app.story = story
        self._render_story(story)
        self._set_busy(False, "Review the story below — approve to continue, or request a revision.")

    def on_approve(self):
        self.app.show("BuildingFrame")

    def on_revise(self):
        FeedbackDialog(self, on_submit=self._submit_revision)

    def _submit_revision(self, feedback: str):
        if not feedback.strip():
            feedback = "Please try a different story with different content."
        self._set_busy(True, "Revising the story based on your feedback…")
        self.app.run_async(
            lambda: revise_story(
                self.app.client,
                self.app.inputs["genre"],
                self.app.inputs["length"],
                self.app.inputs["grade"],
                self.app.story,
                feedback,
            ),
            self._on_story_ready,
        )


class FeedbackDialog(tk.Toplevel):
    """Modal dialog asking the teacher for revision feedback."""

    def __init__(self, parent, on_submit):
        super().__init__(parent)
        self.title("Revision Feedback")
        self.geometry("520x320")
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        self.resizable(False, False)
        self.on_submit = on_submit

        ttk.Label(self, text="What would you like changed or improved?",
                  style="Heading.TLabel", padding=(PAD, PAD, PAD, 0)).pack(anchor="w")

        text_frame = ttk.Frame(self, padding=(PAD, 6, PAD, PAD))
        text_frame.pack(fill="both", expand=True)
        self.text = tk.Text(text_frame, wrap="word", height=10, font=("Segoe UI", 10),
                            borderwidth=1, relief="solid")
        self.text.pack(fill="both", expand=True)
        self.text.focus_set()

        btn_row = ttk.Frame(self, padding=(PAD, 0, PAD, PAD))
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(btn_row, text="Submit", style="Big.TButton",
                   command=self._on_submit).pack(side="right", padx=(0, 8))

    def _on_submit(self):
        feedback = self.text.get("1.0", "end").strip()
        self.destroy()
        self.on_submit(feedback)


# ════════════════════════════════════════════════════════════
#  Building frame — questions / answers / vocab / PDFs
# ════════════════════════════════════════════════════════════

class BuildingFrame(ttk.Frame):
    def __init__(self, parent, app: WorksheetApp):
        super().__init__(parent, padding=PAD)
        self.app = app

        ttk.Label(self, text="Building your worksheets…", style="Title.TLabel").pack(
            anchor="w", pady=(40, 8))
        self.status_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.status_var, style="Status.TLabel",
                  wraplength=WINDOW_W - 60).pack(anchor="w", pady=(0, 16))

        self.progress = ttk.Progressbar(self, mode="indeterminate")
        self.progress.pack(fill="x", pady=4)

    def on_show(self):
        self.progress.start(12)
        self._step_questions()

    def _set_status(self, text: str):
        self.status_var.set(text)

    def _step_questions(self):
        self._set_status(f"Generating {self.app.inputs['num_short']} short-answer and "
                         f"{self.app.inputs['num_long']} long-answer questions…")
        self.app.run_async(
            lambda: generate_questions(
                self.app.client,
                self.app.story,
                self.app.inputs["grade"],
                self.app.inputs["num_short"],
                self.app.inputs["num_long"],
            ),
            self._on_questions_ready,
        )

    def _on_questions_ready(self, questions, exc):
        if exc is not None:
            self._fail(exc)
            return
        self.app.questions = questions
        self._step_extras()

    def _step_extras(self):
        self._set_status("Generating answer key and vocabulary list (in parallel)…")

        def work():
            with ThreadPoolExecutor(max_workers=2) as pool:
                af = pool.submit(generate_answers, self.app.client, self.app.story,
                                 self.app.questions, self.app.inputs["grade"])
                vf = pool.submit(generate_vocabulary, self.app.client, self.app.story,
                                 self.app.inputs["grade"])
                return af.result(), vf.result()

        self.app.run_async(work, self._on_extras_ready)

    def _on_extras_ready(self, result, exc):
        if exc is not None:
            self._fail(exc)
            return
        self.app.answers, self.app.vocabulary = result
        self._step_pdfs()

    def _step_pdfs(self):
        self._set_status("Building student and teacher PDFs…")
        inputs = self.app.inputs
        self.app.student_path = build_output_path(inputs["grade"], self.app.story, teacher=False)
        self.app.teacher_path = build_output_path(inputs["grade"], self.app.story, teacher=True)

        def work():
            create_pdf(
                output_path=self.app.student_path,
                story_text=self.app.story,
                questions=self.app.questions,
                grade=inputs["grade"],
                genre=inputs["genre"],
                vocabulary=self.app.vocabulary,
            )
            create_pdf(
                output_path=self.app.teacher_path,
                story_text=self.app.story,
                questions=self.app.questions,
                grade=inputs["grade"],
                genre=inputs["genre"],
                answers=self.app.answers,
                vocabulary=self.app.vocabulary,
            )

        self.app.run_async(work, self._on_pdfs_ready)

    def _on_pdfs_ready(self, _result, exc):
        self.progress.stop()
        if exc is not None:
            self._fail(exc)
            return
        self.app.show("DoneFrame")

    def _fail(self, exc: Exception):
        self.progress.stop()
        messagebox.showerror("Generation failed", f"{type(exc).__name__}: {exc}")
        self.app.show("SetupFrame")


# ════════════════════════════════════════════════════════════
#  Done frame — show paths, open buttons, generate-another
# ════════════════════════════════════════════════════════════

class DoneFrame(ttk.Frame):
    def __init__(self, parent, app: WorksheetApp):
        super().__init__(parent, padding=PAD)
        self.app = app

        ttk.Label(self, text="🎉  Worksheets saved!", style="Title.TLabel").pack(
            anchor="w", pady=(20, 12))

        ttk.Label(self, text="Student version:", style="Heading.TLabel").pack(anchor="w")
        self.student_path_var = tk.StringVar()
        ttk.Label(self, textvariable=self.student_path_var, style="Path.TLabel",
                  wraplength=WINDOW_W - 60).pack(anchor="w", pady=(0, 12))

        ttk.Label(self, text="Teacher version:", style="Heading.TLabel").pack(anchor="w")
        self.teacher_path_var = tk.StringVar()
        ttk.Label(self, textvariable=self.teacher_path_var, style="Path.TLabel",
                  wraplength=WINDOW_W - 60).pack(anchor="w", pady=(0, 20))

        btn_row = ttk.Frame(self)
        btn_row.pack(fill="x", pady=(8, 0))
        ttk.Button(btn_row, text="📄  Open student PDF", style="Big.TButton",
                   command=self._open_student).pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="📕  Open teacher PDF", style="Big.TButton",
                   command=self._open_teacher).pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="📁  Open Worksheets folder", style="Big.TButton",
                   command=self._open_folder).pack(side="left")

        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=20)
        ttk.Button(self, text="✍️  Generate another worksheet", style="Big.TButton",
                   command=self._generate_another).pack()

    def on_show(self):
        self.student_path_var.set(self.app.student_path or "")
        self.teacher_path_var.set(self.app.teacher_path or "")

    def _open_path(self, path: str | None):
        if not path or not os.path.exists(path):
            messagebox.showerror("File not found", f"Could not find:\n{path}")
            return
        try:
            os.startfile(path)  # Windows-only
        except AttributeError:
            messagebox.showerror("Unsupported", "Opening files from the GUI is only supported on Windows.")
        except Exception as exc:
            messagebox.showerror("Could not open file", str(exc))

    def _open_student(self):
        self._open_path(self.app.student_path)

    def _open_teacher(self):
        self._open_path(self.app.teacher_path)

    def _open_folder(self):
        self._open_path(worksheets_dir())

    def _generate_another(self):
        self.app.reset_for_new_worksheet()
        self.app.show("SetupFrame")


# ════════════════════════════════════════════════════════════

def main():
    root = tk.Tk()
    WorksheetApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
