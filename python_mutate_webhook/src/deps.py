def setup_deps():
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).resolve().parents[0]
    LIB_DIR = str(BASE_DIR.joinpath("lib"))
    sys.path.insert(0, str(BASE_DIR))
    sys.path.insert(0, str(LIB_DIR))

setup_deps()