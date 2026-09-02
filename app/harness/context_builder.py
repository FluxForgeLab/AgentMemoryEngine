from __future__ import annotations


class MemoryContextBuilder:
    def build(self, *, memories: list[dict], budget_chars: int) -> str:
        if not memories:
            return ""

        ordered = sorted(
            memories,
            key=lambda x: (
                float(x.get("score", 0.0)),
                float(x.get("importance", 0.0)),
            ),
            reverse=True,
        )

        lines = ["Relevant historical memory (may be incomplete or outdated):"]
        used = len(lines[0])

        for index, item in enumerate(ordered, start=1):
            line = f"{index}. [{item.get('memory_type')}] {item.get('content', '').strip()}"
            if used + len(line) > budget_chars:
                break
            lines.append(line)
            used += len(line)

        return "\n".join(lines)
