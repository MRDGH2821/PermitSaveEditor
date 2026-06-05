"""Allow `python -m permit_save_editor` to invoke the CLI."""

from .cli import app

if __name__ == "__main__":
    app()
