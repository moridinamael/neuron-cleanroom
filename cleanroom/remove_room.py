"""Delete a room safely: unlink the model and environment links FIRST, so no tool can follow them
into the real weights or Python environment, then delete the rest.

  python -m cleanroom.remove_room ../rooms/L14_N2222      (collect the run first)
"""
import os
import shutil
import sys
from pathlib import Path


def unlink(p: Path):
    if os.name == "nt":
        os.rmdir(p)  # removes a junction without touching its target
    else:
        p.unlink()


def main():
    room = Path(sys.argv[1]).resolve()
    if not (room / "BRIEF.md").exists() or not (room / ".claude" / "settings.json").exists():
        sys.exit(f"{room} does not look like a clean room; refusing")
    links = [room / ".venv", *((room / "models").iterdir() if (room / "models").exists() else [])]
    for p in links:
        if p.is_symlink() or (os.name == "nt" and p.is_dir() and os.path.realpath(p) != str(p)):
            unlink(p)
            print("unlinked", p.name)
    shutil.rmtree(room)
    print("removed", room)


if __name__ == "__main__":
    main()
