import os
import sys
import ast
from pathlib import Path
from collections import defaultdict

EXCLUDE_DIRS = {
    ".venv", "venv", ".venv311", "venv311",
    "__pycache__", ".git", ".pytest_cache",
    "node_modules", "dist", "build"
}

def iter_py_files(root: Path):
    for p in root.rglob("*.py"):
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        yield p

def check_syntax(py_file: Path) -> str | None:
    try:
        src = py_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        src = py_file.read_text(encoding="utf-8", errors="replace")

    try:
        ast.parse(src, filename=str(py_file))
        return None
    except SyntaxError as e:
        return f"{py_file}:{e.lineno}:{e.offset} SyntaxError: {e.msg}"

def scan_duplicate_function_names(root: Path):
    funcs = defaultdict(list)

    for f in iter_py_files(root):
        try:
            src = f.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(src, filename=str(f))
        except Exception:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                funcs[node.name].append((str(f), node.lineno))
            elif isinstance(node, ast.AsyncFunctionDef):
                funcs[node.name].append((str(f), node.lineno))

    return {k: v for k, v in funcs.items() if len(v) > 1}

def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()

    print(f"Root: {root}")
    print("1) Syntax check...")
    errors = []
    for f in iter_py_files(root):
        err = check_syntax(f)
        if err:
            errors.append(err)

    if errors:
        print("\n".join(errors))
        print(f"\nSyntax errors: {len(errors)}")
    else:
        print("No syntax errors")

    print("\n2) Duplicate function names...")
    dups = scan_duplicate_function_names(root)
    if not dups:
        print("No duplicate function names")
    else:
        for name, locs in sorted(dups.items()):
            print(f"\n- {name}")
            for file, line in locs:
                print(f"  {file}:{line}")

if __name__ == "__main__":
    main()
