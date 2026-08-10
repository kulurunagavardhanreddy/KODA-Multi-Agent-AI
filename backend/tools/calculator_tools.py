# calculator_tools.py

from langchain_core.tools import tool
import ast
import subprocess
import sys

@tool
def python_repl_tool(code: str) -> str:
    """Safe Python execution sandbox for lightweight calculations and data processing."""
    # Security Configuration
    libs = {
        'math', 'random', 'statistics', 'datetime', 'time', 'json', 're', 'collections', 'itertools',
        'functools', 'decimal', 'fractions', 'numpy', 'pandas'
    }

    funcs = {
        'print', 'len', 'range', 'sum', 'min', 'max', 'sorted', 'round', 'abs', 'enumerate', 'zip', 'map',
        'filter', 'list', 'dict', 'set', 'tuple', 'int', 'float', 'str', 'bool', 'type', 'isinstance', 'any', 'all'
    }

    bad_attrs = {
        'system', 'popen', 'remove', 'unlink', 'rmdir', 'rename', 'replace', 'chmod', 'chown', 'fork',
        'kill', 'walk', 'spawn', 'load_dotenv'
    }

    try:
        tree = ast.parse(code)

        for node in ast.walk(tree):
            # Validate Imports
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mods = (
                    [n.name.split('.')[0] for n in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module.split('.')[0] if node.module else ""]
                )

                for m in mods:
                    if m not in libs:
                        return f"Security Error: Import '{m}' not allowed."

            # Validate Function Calls & Attributes
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id not in funcs:
                        return f"Security Error: Function '{node.func.id}()' not allowed."

                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in bad_attrs:
                        return f"Security Error: Attribute '{node.func.attr}' forbidden."

            # Block Dunder Attribute Access
            elif isinstance(node, ast.Attribute):
                if node.attr.startswith("__"):
                    return "Security Error: Dunder attributes forbidden."

            # Block Dangerous Structures
            elif isinstance(node, ast.While):
                return "Security Error: While loops are not allowed."

            elif isinstance(node, (ast.Lambda, ast.ClassDef, ast.With)):
                return f"Security Error: {type(node).__name__} is not allowed."

    except SyntaxError as e:
        return f"Syntax Error: {e}"

    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=5,
            env={"PYTHONIOENCODING": "utf-8"}
        )

        out = (proc.stdout + proc.stderr).strip()
        return out if out else "Code executed successfully."

    except subprocess.TimeoutExpired:
        return "Execution Error: 5 second timeout exceeded."

    except Exception as e:
        return f"Execution Error: {type(e).__name__}: {e}"
