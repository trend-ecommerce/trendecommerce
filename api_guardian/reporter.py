import sys

class GuardianReporter:
    @staticmethod
    def format_request_result(result: dict) -> str:
        """
        Formats evaluation result into official API Guardian report layout.
        """
        decision = result.get('decision', 'BLOCK')
        file = result.get('file', 'unknown')
        line = result.get('line', 0)
        policy = result.get('policy', 'Unknown API')
        reason = result.get('reason', 'Nenhum motivo informado.')
        severity = result.get('severity', 'B — HIGH')
        details = result.get('details', [])

        # Check if terminal supports unicode emojis
        use_emoji = True
        encoding = getattr(sys.stdout, 'encoding', None)
        if encoding and 'cp1252' in encoding.lower():
            use_emoji = False

        icon_ok = "🟢" if use_emoji else "[APPROVED]"
        icon_block = "🚨" if use_emoji else "[BLOCKED]"
        chk = "✓" if use_emoji else "OK"
        cross = "✗" if use_emoji else "FAIL"

        if decision == 'ALLOW':
            output = [
                f"{icon_ok} API GUARDIAN",
                "",
                "STATUS: APROVADO",
                "",
                f"API: {policy}",
                f"ARQUIVO: {file}",
                f"LINHA: {line}",
                "",
                "DETALHES:"
            ]
            for detail in details:
                detail_clean = detail.replace("✓", chk).replace("✗", cross)
                output.append(f"  {detail_clean}")
            output.extend([
                "",
                "REQUISIÇÃO LIBERADA"
            ])
            return "\n".join(output)
        else:
            output = [
                f"{icon_block} API GUARDIAN",
                "",
                "STATUS: BLOQUEADO",
                "",
                f"API: {policy}",
                f"ARQUIVO: {file}",
                f"LINHA: {line}",
                "",
                f"SEVERIDADE: {severity}",
                "",
                "MOTIVO:",
                f"  {reason}",
                "",
                "DETALHES:"
            ]
            for detail in details:
                detail_clean = detail.replace("✓", chk).replace("✗", cross)
                output.append(f"  {detail_clean}")
            output.extend([
                "",
                "REQUISIÇÃO CANCELADA"
            ])
            return "\n".join(output)

    @staticmethod
    def format_audit_summary(scanned_files: int, api_calls_count: int, policies_count: int,
                             approved: int, warnings: int, blocked: int, violations: list) -> str:
        status_str = "BLOQUEADO" if blocked > 0 else "APROVADO"
        use_emoji = True
        encoding = getattr(sys.stdout, 'encoding', None)
        if encoding and 'cp1252' in encoding.lower():
            use_emoji = False

        icon = ("🚨" if blocked > 0 else "🟢") if use_emoji else ("" if blocked == 0 else "[BLOCKED]")

        lines = [
            "API GUARDIAN AUDIT",
            "==================",
            "",
            f"Files scanned: {scanned_files}",
            f"API calls found: {api_calls_count}",
            f"Policies loaded: {policies_count}",
            "",
            f"Approved: {approved}",
            f"Warnings: {warnings}",
            f"Blocked: {blocked}",
            "",
            f"STATUS: {icon} {status_str}".strip(),
            ""
        ]

        if violations:
            lines.append("VIOLATIONS DETECTED:")
            lines.append("--------------------")
            for idx, v in enumerate(violations, 1):
                lines.append(f"{idx}. [{v.get('file')}:{v.get('line')}] - {v.get('reason')}")
            lines.append("")

        return "\n".join(lines)
