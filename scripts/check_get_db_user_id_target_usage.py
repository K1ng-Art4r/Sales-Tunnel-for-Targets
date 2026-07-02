import ast
from pathlib import Path

FILE = Path('app/handlers/start.py')

source = FILE.read_text(encoding='utf-8')
tree = ast.parse(source)

errors = []

class Visitor(ast.NodeVisitor):
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        arg_names = {a.arg for a in node.args.args}
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            if not isinstance(child.func, ast.Name) or child.func.id != 'get_db_user_id':
                continue
            if not child.args:
                continue
            first = child.args[0]
            if isinstance(first, ast.Name) and first.id == 'target' and 'target' not in arg_names:
                errors.append((node.name, child.lineno))
        self.generic_visit(node)

Visitor().visit(tree)

if errors:
    for fn, line in errors:
        print(f"Invalid get_db_user_id(target) in function '{fn}' at line {line}")
    raise SystemExit(1)

print('OK: get_db_user_id(target) usage is valid.')
