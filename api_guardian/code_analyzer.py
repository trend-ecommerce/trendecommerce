import ast
import os


class CodeAnalyzer(ast.NodeVisitor):
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.http_calls = []
        self.syntax_errors = []
        self.invalid_imports = []
        self.unhandled_exceptions = []
        self.current_function = "global"
        self.is_internal_guardian = "api_guardian" in filepath.replace('\\', '/')

    def visit_FunctionDef(self, node):
        prev_function = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = prev_function

    def visit_AsyncFunctionDef(self, node):
        prev_function = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = prev_function

    def visit_Import(self, node):
        if not self.is_internal_guardian:
            for alias in node.names:
                if alias.name in ['urllib', 'requests', 'httpx', 'aiohttp', 'urllib.request']:
                    self.invalid_imports.append({
                        'file': self.filepath,
                        'line': node.lineno,
                        'module': alias.name,
                        'reason': f"Import direto de biblioteca HTTP '{alias.name}'. Deve-se usar o runtime_guard (guarded_request)."
                    })
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        module = node.module or ''
        if not self.is_internal_guardian:
            if module in ['urllib', 'requests', 'httpx', 'aiohttp', 'urllib.request']:
                if module != 'api_guardian.runtime_guard':
                    self.invalid_imports.append({
                        'file': self.filepath,
                        'line': node.lineno,
                        'module': module,
                        'reason': f"Import direto do módulo HTTP '{module}'. Use api_guardian.runtime_guard."
                    })
        self.generic_visit(node)

    def visit_Call(self, node):
        func_name = ""
        func_obj = ""

        if isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
            if isinstance(node.func.value, ast.Name):
                func_obj = node.func.value.id
            elif isinstance(node.func.value, ast.Attribute):
                func_obj = node.func.value.attr
        elif isinstance(node.func, ast.Name):
            func_name = node.func.id

        full_call = f"{func_obj}.{func_name}" if func_obj else func_name

        is_direct_http = False
        if not self.is_internal_guardian:
            if func_obj in ['requests', 'httpx', 'urllib', 'urlopen', 'aiohttp', 'session']:
                if func_name in ['get', 'post', 'put', 'delete', 'patch', 'urlopen', 'request']:
                    is_direct_http = True

        if full_call == 'runtime_guard.guarded_request' or func_name == 'guarded_request':
            is_direct_http = False

        url_val = ""
        method = "GET"
        params_dict = {}

        # Extract keyword arguments (like params={"q": "phone"})
        for kw in node.keywords:
            if kw.arg == 'params' and isinstance(kw.value, ast.Dict):
                for k_node, v_node in zip(kw.value.keys, kw.value.values):
                    k_str = self._extract_string(k_node)
                    v_str = self._extract_string(v_node) or "dummy"
                    if k_str:
                        params_dict[k_str] = v_str

        if func_name == 'guarded_request':
            if len(node.args) >= 1:
                method = self._extract_string(node.args[0]).upper() or "GET"
            if len(node.args) >= 2:
                url_val = self._extract_string(node.args[1])
        else:
            if node.args:
                url_val = self._extract_string(node.args[0])
            if func_name in ['get', 'post', 'put', 'delete', 'patch']:
                method = func_name.upper()

        if is_direct_http or func_name == 'guarded_request':
            self.http_calls.append({
                'file': self.filepath,
                'line': node.lineno,
                'function': self.current_function,
                'method': method,
                'url': url_val,
                'params': params_dict,
                'is_direct_bypassing': is_direct_http,
                'call_expr': full_call
            })

        self.generic_visit(node)

    def _extract_string(self, node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        elif isinstance(node, ast.JoinedStr):
            parts = []
            for val in node.values:
                if isinstance(val, ast.Constant):
                    parts.append(str(val.value))
                else:
                    parts.append("{param}")
            return "".join(parts)
        return ""


def analyze_code_file(filepath: str) -> dict:
    """
    Statically analyzes a Python file for HTTP calls, syntax errors, and direct imports.
    """
    if not os.path.exists(filepath) or not filepath.endswith('.py'):
        return {'http_calls': [], 'syntax_errors': [], 'invalid_imports': []}

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
    except Exception as e:
        return {
            'http_calls': [],
            'syntax_errors': [{'file': filepath, 'line': 1, 'reason': f"Erro de leitura: {e}"}],
            'invalid_imports': []
        }

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as se:
        return {
            'http_calls': [],
            'syntax_errors': [{'file': filepath, 'line': se.lineno, 'reason': f"SyntaxError: {se.msg}"}],
            'invalid_imports': []
        }

    analyzer = CodeAnalyzer(filepath)
    analyzer.visit(tree)

    return {
        'http_calls': analyzer.http_calls,
        'syntax_errors': analyzer.syntax_errors,
        'invalid_imports': analyzer.invalid_imports
    }
