import os
from .config import GuardianConfig
from .policy_engine import PolicyEngine
from .secret_scanner import SecretScanner
from .code_analyzer import analyze_code_file
from .reporter import GuardianReporter


class GuardianChecker:
    def __init__(self, config: GuardianConfig = None):
        if config is None:
            config = GuardianConfig()
        self.config = config
        self.policy_engine = PolicyEngine(config)
        self.secret_scanner = SecretScanner()

    def check_file(self, filepath: str) -> dict:
        """
        Runs complete static verification on a single file.
        """
        results = {
            'file': filepath,
            'violations': [],
            'api_calls': [],
            'approved_count': 0,
            'blocked_count': 0,
            'warning_count': 0
        }

        # 1. Scan for hardcoded secrets
        secret_violations = self.secret_scanner.scan_file(filepath)
        for sv in secret_violations:
            results['blocked_count'] += 1
            results['violations'].append({
                'file': filepath,
                'line': sv['line'],
                'severity': 'A — CRITICAL',
                'reason': sv['reason']
            })

        # 2. Analyze Python code if .py
        if filepath.endswith('.py'):
            analysis = analyze_code_file(filepath)

            # Syntax errors
            for se in analysis['syntax_errors']:
                results['blocked_count'] += 1
                results['violations'].append({
                    'file': filepath,
                    'line': se['line'],
                    'severity': 'A — CRITICAL',
                    'reason': se['reason']
                })

            # Direct HTTP imports bypassing Guardian
            for imp in analysis['invalid_imports']:
                results['blocked_count'] += 1
                results['violations'].append({
                    'file': filepath,
                    'line': imp['line'],
                    'severity': 'B — HIGH',
                    'reason': imp['reason']
                })

            # HTTP Calls analysis
            for call in analysis['http_calls']:
                results['api_calls'].append(call)
                if call.get('is_direct_bypassing'):
                    results['blocked_count'] += 1
                    results['violations'].append({
                        'file': filepath,
                        'line': call['line'],
                        'severity': 'B — HIGH',
                        'reason': f"Chamada HTTP direta '{call['call_expr']}' ignorando o API Guardian Runtime Guard."
                    })
                elif call.get('url'):
                    # Statically evaluate URL against Policy Engine
                    eval_res = self.policy_engine.evaluate({
                        'url': call['url'],
                        'method': call['method'],
                        'params': call.get('params', {}),
                        'file': filepath,
                        'line': call['line']
                    })
                    if eval_res['decision'] == 'BLOCK':
                        results['blocked_count'] += 1
                        results['violations'].append({
                            'file': filepath,
                            'line': call['line'],
                            'severity': eval_res['severity'],
                            'reason': eval_res['reason']
                        })
                    else:
                        results['approved_count'] += 1

        return results

    def scan_directory(self, target_dir: str) -> dict:
        """
        Recursively scans directory for code quality, secrets, and policy compliance.
        """
        total_files = 0
        total_api_calls = 0
        total_approved = 0
        total_warnings = 0
        total_blocked = 0
        all_violations = []

        ignore_dirs = ['.git', '__pycache__', '.pytest_cache', 'venv', 'env', '.gemini', 'node_modules', '.venv']

        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            for file in files:
                filepath = os.path.join(root, file)
                # Only check code, config, and env files
                if file.endswith(('.py', '.yaml', '.yml', '.json', '.env')):
                    total_files += 1
                    res = self.check_file(filepath)
                    total_api_calls += len(res['api_calls'])
                    total_approved += res['approved_count']
                    total_warnings += res['warning_count']
                    total_blocked += res['blocked_count']
                    all_violations.extend(res['violations'])

        summary_report = GuardianReporter.format_audit_summary(
            scanned_files=total_files,
            api_calls_count=total_api_calls,
            policies_count=len(self.config.policies),
            approved=total_approved,
            warnings=total_warnings,
            blocked=total_blocked,
            violations=all_violations
        )

        return {
            'files_scanned': total_files,
            'api_calls_found': total_api_calls,
            'policies_loaded': len(self.config.policies),
            'approved': total_approved,
            'warnings': total_warnings,
            'blocked': total_blocked,
            'violations': all_violations,
            'report': summary_report,
            'is_clean': (total_blocked == 0)
        }
