"""Termux-native Textual interface for Wayground study tools.

This TUI focuses on study help, configuration, and diagnostics.
It does not automate answer selection or submission in live assessments.
Run from the repository root: python src/tui.py
"""
from __future__ import annotations

import asyncio
import os
import platform
import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Markdown, Static, TextArea

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"


def read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip("'\"")
    return values


def write_env(values: dict[str, str]) -> None:
    ENV_PATH.write_text(
        "# Local settings for Wayground Study TUI. Keep this file private.\n"
        + "".join(f"{key}={value}\n" for key, value in values.items()),
        encoding="utf-8",
    )
    try:
        ENV_PATH.chmod(0o600)
    except OSError:
        pass


class HomeScreen(Screen):
    BINDINGS = [("q", "app.quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="home"):
            yield Static("WAYGROUND  /  TERMUX", id="brand")
            yield Static("Terminal study workspace", id="subtitle")
            yield Static(
                "Study concepts, manage local AI settings, and check your Termux environment.\n"
                "This interface does not submit answers to live assessments.",
                id="intro",
            )
            with Vertical(id="menu"):
                yield Button("Study assistant", id="study", variant="primary")
                yield Button("AI configuration", id="settings")
                yield Button("Environment diagnostics", id="diagnostics")
                yield Button("Quit", id="quit", variant="error")
            yield Static("↑/↓ navigate  •  Enter activate  •  Ctrl+C quit", id="hint")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "study":
            self.app.push_screen(StudyScreen())
        elif event.button.id == "settings":
            self.app.push_screen(SettingsScreen())
        elif event.button.id == "diagnostics":
            self.app.push_screen(DiagnosticsScreen())
        elif event.button.id == "quit":
            self.app.exit()


class StudyScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="study-view"):
            yield Label("STUDY ASSISTANT", classes="section-title")
            yield Static("Enter a concept or practice question. The assistant will explain the reasoning.", classes="muted")
            yield TextArea(
                "Explain the concept of subnetting and show a small worked example.",
                id="question",
                language="markdown",
            )
            with Horizontal(id="study-actions"):
                yield Button("Explain", id="explain", variant="primary")
                yield Button("Clear", id="clear")
                yield Button("Back", id="back")
            yield Static("Ready.", id="study-status")
            with VerticalScroll(id="answer-scroll"):
                yield Markdown("Your explanation will appear here.", id="answer")
        yield Footer()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()
            return
        if event.button.id == "clear":
            self.query_one("#question", TextArea).text = ""
            self.query_one("#answer", Markdown).update("Your explanation will appear here.")
            self.query_one("#study-status", Static).update("Cleared.")
            return
        if event.button.id != "explain":
            return

        prompt = self.query_one("#question", TextArea).text.strip()
        if not prompt:
            self.query_one("#study-status", Static).update("Enter a question or concept first.")
            return

        env = read_env()
        api_key = (
            env.get("OPENAI_API_KEY") or env.get("AI_API_KEY") or env.get("GROQ_API_KEY")
            or os.getenv("OPENAI_API_KEY") or os.getenv("AI_API_KEY") or os.getenv("GROQ_API_KEY")
        )
        base_url = (
            env.get("OPENAI_API_BASE") or env.get("AI_API_BASE")
            or os.getenv("OPENAI_API_BASE") or os.getenv("AI_API_BASE")
            or "https://api.openai.com/v1"
        )
        model = env.get("AI_MODEL") or os.getenv("AI_MODEL") or "gpt-4o-mini"
        if not api_key:
            self.query_one("#study-status", Static).update(
                "No API key configured. Open AI configuration and add your provider key."
            )
            return

        self.query_one("#study-status", Static).update("Thinking…")
        self.query_one("#answer", Markdown).update("Preparing an explanation…")
        self.query_one("#explain", Button).disabled = True
        try:
            from openai import OpenAI

            def request_explanation() -> str:
                client = OpenAI(api_key=api_key, base_url=base_url, timeout=45, max_retries=1)
                response = client.chat.completions.create(
                    model=model,
                    temperature=0.3,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a patient study tutor. Explain concepts clearly, show "
                                "steps and examples, and help the learner understand rather than "
                                "merely giving an answer. For graded-test questions, teach the "
                                "underlying concept and reasoning."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                )
                return response.choices[0].message.content or "The provider returned an empty response."

            result = await asyncio.to_thread(request_explanation)
            self.query_one("#answer", Markdown).update(result)
            self.query_one("#study-status", Static).update(f"Done · {model}")
        except Exception as exc:
            self.query_one("#answer", Markdown).update(
                "Could not get an explanation. Check the provider, API base URL, model, and network."
            )
            self.query_one("#study-status", Static).update(f"Request failed: {type(exc).__name__}: {exc}")
        finally:
            self.query_one("#explain", Button).disabled = False


class SettingsScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        env = read_env()
        yield Header()
        with Vertical(id="settings-view"):
            yield Label("AI CONFIGURATION", classes="section-title")
            yield Static("Settings are saved to .env with owner-only permissions where supported.", classes="muted")
            yield Label("Provider API key")
            yield Input(value=env.get("OPENAI_API_KEY", env.get("AI_API_KEY", env.get("GROQ_API_KEY", ""))), password=True, id="api-key", placeholder="Paste API key")
            yield Label("OpenAI-compatible base URL")
            yield Input(value=env.get("OPENAI_API_BASE", env.get("AI_API_BASE", "https://api.openai.com/v1")), id="base-url")
            yield Label("Model name")
            yield Input(value=env.get("AI_MODEL", "gpt-4o-mini"), id="model")
            with Horizontal(id="settings-actions"):
                yield Button("Save settings", id="save", variant="primary")
                yield Button("Back", id="back")
            yield Static("", id="settings-status")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()
            return
        if event.button.id != "save":
            return
        key = self.query_one("#api-key", Input).value.strip()
        base = self.query_one("#base-url", Input).value.strip()
        model = self.query_one("#model", Input).value.strip()
        if not base.startswith(("https://", "http://")):
            self.query_one("#settings-status", Static).update("Base URL must start with https:// or http://")
            return
        if not model:
            self.query_one("#settings-status", Static).update("Model name cannot be empty.")
            return
        values = read_env()
        for name in ("OPENAI_API_KEY", "AI_API_KEY", "GROQ_API_KEY", "OPENAI_API_BASE", "AI_API_BASE", "AI_MODEL"):
            values.pop(name, None)
        if key:
            values["OPENAI_API_KEY"] = key
        values["OPENAI_API_BASE"] = base
        values["AI_MODEL"] = model
        try:
            write_env(values)
            self.query_one("#settings-status", Static).update(f"Saved to {ENV_PATH}")
        except OSError as exc:
            self.query_one("#settings-status", Static).update(f"Could not save settings: {exc}")


class DiagnosticsScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="diagnostics-view"):
            yield Label("ENVIRONMENT DIAGNOSTICS", classes="section-title")
            yield Static(self.report(), id="report")
            with Horizontal():
                yield Button("Refresh", id="refresh", variant="primary")
                yield Button("Back", id="back")
        yield Footer()

    @staticmethod
    def report() -> str:
        lines = [
            f"Python       : {sys.version.split()[0]}",
            f"Platform     : {platform.platform()}",
            f"Architecture : {platform.machine()}",
            f"Prefix       : {sys.prefix}",
            f"Termux       : {'yes' if os.getenv('TERMUX_VERSION') else 'not detected'}",
            f"Project root : {ROOT}",
            f".env exists  : {'yes' if ENV_PATH.exists() else 'no'}",
        ]
        try:
            import textual
            lines.append(f"Textual      : {textual.__version__}")
        except Exception:
            lines.append("Textual      : unavailable")
        try:
            import openai
            lines.append(f"OpenAI SDK   : {openai.__version__}")
        except Exception:
            lines.append("OpenAI SDK   : unavailable")
        try:
            import playwright
            lines.append(f"Playwright   : {playwright.__version__} (not required for study TUI)")
        except Exception:
            lines.append("Playwright   : not installed (not required for study TUI)")
        return "\n".join(lines)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "refresh":
            self.query_one("#report", Static).update(self.report())


class WaygroundTUI(App):
    TITLE = "Wayground Study TUI"
    SUB_TITLE = "FarizGD · Termux edition"
    CSS = """
    Screen { background: #0b1020; color: #e5e7eb; }
    Header { background: #171b2e; color: #c4b5fd; }
    Footer { background: #171b2e; }
    #home, #study-view, #settings-view, #diagnostics-view {
        width: 100%; height: 1fr; padding: 1 2; align: center top;
    }
    #brand { color: #c4b5fd; text-style: bold; text-align: center; width: 100%; margin-top: 1; }
    #subtitle { color: #9ca3af; text-align: center; width: 100%; }
    #intro { width: 100%; max-width: 72; margin: 2 0; padding: 1; border: round #4c4775; }
    #menu { width: 100%; max-width: 52; height: auto; }
    #menu Button { width: 100%; margin: 1 0; }
    #hint, .muted { color: #9ca3af; text-align: center; width: 100%; margin: 1 0; }
    .section-title { color: #c4b5fd; text-style: bold; margin-bottom: 1; }
    #question { height: 8; margin: 1 0; border: round #4c4775; }
    #study-actions, #settings-actions { height: auto; margin-bottom: 1; }
    #study-actions Button, #settings-actions Button { margin-right: 1; }
    #study-status, #settings-status { color: #a5b4fc; margin: 1 0; }
    #answer-scroll { height: 1fr; border: round #343a55; padding: 1; }
    #answer { width: 100%; }
    #settings-view Input { width: 100%; margin-bottom: 1; }
    #settings-view Label { margin-top: 1; }
    #report { width: 100%; height: auto; border: round #343a55; padding: 1; margin-top: 1; }
    """
    ENABLE_COMMAND_PALETTE = False

    def on_mount(self) -> None:
        self.push_screen(HomeScreen())


if __name__ == "__main__":
    WaygroundTUI().run()
