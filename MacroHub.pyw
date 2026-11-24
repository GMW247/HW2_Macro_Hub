"""Double-click to open the Macro Hub GUI (no console window)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from macrohub.app import main  # noqa: E402

main()
