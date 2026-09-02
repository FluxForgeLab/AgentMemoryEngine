from __future__ import annotations

from app.observability.trace import emit, span


class MemoryContextBuilder:
    def build(self, *, memories: list[dict], budget_chars: int) -> str:
        if not memories:
            emit("context.built", input_count=0, used_count=0, chars=0, dropped_ids=[])
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
        kept_ids: list[str] = []
        dropped_ids: list[str] = []

        with span("context.build"):
            for index, item in enumerate(ordered, start=1):
                line = f"{index}. [{item.get('memory_type')}] {item.get('content', '').strip()}"
                if used + len(line) > budget_chars:
                    dropped_ids.extend(
                        str(x.get("id", "")) for x in ordered[index - 1 :]
                    )
                    break
                lines.append(line)
                used += len(line)
                kept_ids.append(str(item.get("id", "")))

            text = "\n".join(lines)
            emit(
                "context.built",
                input_count=len(memories),
                used_count=len(kept_ids),
                chars=len(text),
                budget_chars=budget_chars,
                dropped_ids=dropped_ids,
                used_ids=kept_ids,
                memory_context=text,
            )
            return text
