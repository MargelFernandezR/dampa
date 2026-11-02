from pathlib import Path


_PROJECT_DIR = Path(__file__).resolve().parent
_GAME_PARTS = (
	"01_core.py",
	"02_assets_ui.py",
	"03_karera.py",
	"04_pogs.py",
	"05_screens.py",
)

# The original game shares globals across sections, so execute them in order
# in this module's namespace while keeping each section in its own file.
_GAME_PARTS_LOADING = True
for _part in _GAME_PARTS:
	_path = _PROJECT_DIR / "game_parts" / _part
	_source = _path.read_text(encoding="utf-8")
	exec(compile(_source, str(_path), "exec"), globals())
