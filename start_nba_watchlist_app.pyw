"""Launch the NBA watchlist example application with a double click.

This helper script can be placed anywhere (including the desktop) and will
remember the location of the ``espn-api`` repository after the first run. If the
repository path changes, simply delete the stored configuration file and run the
launcher again to pick the new location.
"""

from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path
from typing import Optional


CONFIG_PATH = Path.home() / ".espn_api_watchlist_launcher.json"
APP_RELATIVE_PATH = Path("examples") / "nba_watchlist_app.py"


def load_saved_repo_path() -> Optional[Path]:
    """Return the repository path stored in the config file, if it is valid."""

    if not CONFIG_PATH.exists():
        return None

    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        raw_path = data.get("repo_path")
    except (json.JSONDecodeError, OSError):
        return None

    if not raw_path:
        return None

    candidate = Path(raw_path).expanduser()
    if (candidate / APP_RELATIVE_PATH).exists():
        return candidate

    return None


def save_repo_path(path: Path) -> None:
    """Persist the repository path so the launcher can be double clicked."""

    CONFIG_PATH.write_text(
        json.dumps({"repo_path": str(path)}),
        encoding="utf-8",
    )


def prompt_for_repo_path() -> Optional[Path]:
    """Ask the user to locate the ``espn-api`` repository directory."""

    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except Exception:  # pragma: no cover - tkinter always available with the app
        return None

    root = tk.Tk()
    root.withdraw()

    messagebox.showinfo(
        "Select Repository",
        "Please choose the folder that contains the espn-api project.",
        parent=root,
    )

    selected = filedialog.askdirectory(parent=root)
    root.destroy()

    if not selected:
        return None

    repo_path = Path(selected)
    if not (repo_path / APP_RELATIVE_PATH).exists():
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Invalid Selection",
            "The selected folder does not contain examples/nba_watchlist_app.py.",
            parent=root,
        )
        root.destroy()
        return None

    return repo_path


def resolve_repo_path() -> Path:
    """Determine the repository path, prompting the user if necessary."""

    repo_path = load_saved_repo_path()
    if repo_path is not None:
        return repo_path

    while True:
        repo_path = prompt_for_repo_path()
        if repo_path is None:
            raise SystemExit(
                "The espn-api repository could not be located. Run the launcher "
                "again and choose the folder that contains the project."
            )

        app_path = repo_path / APP_RELATIVE_PATH
        if app_path.exists():
            save_repo_path(repo_path)
            return repo_path


def main() -> None:
    repo_path = resolve_repo_path()
    app_path = repo_path / APP_RELATIVE_PATH

    sys.path.insert(0, str(repo_path))
    runpy.run_path(str(app_path), run_name="__main__")


if __name__ == "__main__":
    main()
