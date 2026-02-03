import sys
from pathlib import Path

from ndevio.bioio_plugins._utils import BIOIO_PLUGINS

# Ensure src is on path so we can import the package in editable installs
repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / 'src'
out_dir = Path(__file__).resolve().parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


def normalize_ext(e: str) -> str:
    e = e.strip().lower()
    if e.startswith('.'):
        e = e[1:]
    return e


def main():
    exts = set()
    for info in BIOIO_PLUGINS.values():
        for e in info.get('extensions', []):
            ne = normalize_ext(e)
            if ne:
                exts.add(ne)

    sorted_exts = sorted(exts)

    # Produce napari YAML snippet (pretty, one-per-line quoted)
    patterns = [f"'*.{ext}'" for ext in sorted_exts]
    # Break into lines of ~10 entries for readability
    lines = []
    chunk = 10
    for i in range(0, len(patterns), chunk):
        lines.append('  ' + ', '.join(patterns[i : i + chunk]) + ',')

    snippet_file = out_dir / 'napari_patterns_snippet.txt'
    snippet_text = 'filename_patterns: [\n' + '\n'.join(lines) + '\n]\n'
    snippet_file.write_text(snippet_text)
    print(f'Wrote napari snippet to {snippet_file}')


if __name__ == '__main__':
    main()
