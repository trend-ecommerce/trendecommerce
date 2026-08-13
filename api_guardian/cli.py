import sys
import os
from .checker import GuardianChecker
from .config import GuardianConfig


def main():
    target_path = "."
    if len(sys.argv) > 1:
        target_path = sys.argv[1]

    if not os.path.exists(target_path):
        print(f"Error: Target path '{target_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    config = GuardianConfig()
    checker = GuardianChecker(config)

    if os.path.isfile(target_path):
        res = checker.check_file(target_path)
        summary = {
            'files_scanned': 1,
            'api_calls_found': len(res['api_calls']),
            'policies_loaded': len(config.policies),
            'approved': res['approved_count'],
            'warnings': res['warning_count'],
            'blocked': res['blocked_count'],
            'violations': res['violations'],
            'is_clean': res['blocked_count'] == 0
        }
        report = checker.secret_scanner.scan_file(target_path)
        print(f"API GUARDIAN AUDIT FILE: {target_path}")
        print(f"Status: {'APROVADO' if summary['is_clean'] else 'BLOQUEADO'}")
        if res['violations']:
            for v in res['violations']:
                print(f"  ✗ [{v.get('line')}] - {v.get('reason')}")
        clean = summary['is_clean']
    else:
        results = checker.scan_directory(target_path)
        print(results['report'])
        clean = results['is_clean']

    if clean:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
