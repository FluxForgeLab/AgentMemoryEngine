from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

from app.adapters.llm import build_chat_llm, build_chat_messages
from app.api.dependencies import get_agent_harness, get_memory_service
from app.config import get_settings
from app.domain.models import MemoryType
from app.observability.setup import setup_logging, shutdown_logging
from app.observability.trace import bind_turn, emit, reset_context

HELP = """
Commands:
  /help                         Show this help
  /quit                         Exit
  /debug                        Toggle printing memory_context
  /nomem                        Toggle skipping memory injection
  /compare                      Toggle with/without memory answers
  /project <name>               Set context.project
  /add <type> | <content>       Store a memory (e.g. /add reflection | ...)
""".strip()


class CliState:
    def __init__(self):
        self.debug = False
        self.nomem = False
        self.compare = False
        self.context: dict[str, Any] = {"project": "harness"}


async def handle_command(
    line: str,
    *,
    state: CliState,
    service,
) -> bool:
    command = line.strip()
    emit("cli.command", command=command.split()[0])

    if command in {"/quit", "/exit"}:
        return False
    if command == "/help":
        print(HELP)
        return True
    if command == "/debug":
        state.debug = not state.debug
        print(f"debug={state.debug}")
        return True
    if command == "/nomem":
        state.nomem = not state.nomem
        print(f"nomem={state.nomem}")
        return True
    if command == "/compare":
        state.compare = not state.compare
        print(f"compare={state.compare}")
        return True
    if command.startswith("/project "):
        state.context["project"] = command[len("/project ") :].strip()
        print(f"project={state.context['project']}")
        return True
    if command.startswith("/add "):
        body = command[len("/add ") :]
        if "|" not in body:
            print("usage: /add <memory_type> | <content>")
            return True
        type_raw, content = [x.strip() for x in body.split("|", 1)]
        try:
            memory_type = MemoryType(type_raw)
        except ValueError:
            print(f"unknown memory_type: {type_raw}")
            return True
        if not content:
            print("content is empty")
            return True
        memory = await service.store_memory(
            content=content,
            memory_type=memory_type,
            importance=0.9,
            metadata=dict(state.context),
        )
        emit("memory.stored", id=memory.id, memory_type=memory_type.value, content=content)
        print(f"stored {memory.id} ({memory.memory_type.value})")
        return True

    print("unknown command; /help")
    return True


async def run_turn(
    task: str,
    *,
    state: CliState,
    harness,
    llm,
) -> None:
    turn_id = bind_turn()
    emit(
        "cli.turn.start",
        task=task,
        context=state.context,
        debug=state.debug,
        nomem=state.nomem,
        compare=state.compare,
        provider=llm.provider,
        model=llm.model,
    )
    try:
        bundle = await harness.prepare_context(task=task, context=state.context)
        use_memory = not state.nomem
        messages = build_chat_messages(
            task=task,
            memory_context=bundle.get("memory_context") or "",
            use_memory=use_memory,
        )
        emit("llm.request", provider=llm.provider, model=llm.model, messages=messages, use_memory=use_memory)
        result = await llm.complete(messages)
        emit(
            "llm.response",
            answer=result.text,
            elapsed_ms=result.elapsed_ms,
            usage=result.usage,
            finish_reason=result.finish_reason,
        )

        gate = (bundle.get("gate_decision") or {}).get("decision")
        plan = bundle.get("retrieval_plan") or {}
        hits = len(bundle.get("memories") or [])
        print()
        print(result.text.strip() or "(empty answer)")
        print()
        print(
            f"gate={gate} method={plan.get('method')} hits={hits} "
            f"{result.elapsed_ms}ms"
        )
        if state.debug:
            print("--- memory_context ---")
            print(bundle.get("memory_context") or "(empty)")
            print("--- plan ---")
            print(plan)

        if state.compare:
            nomem_messages = build_chat_messages(
                task=task,
                memory_context=bundle.get("memory_context") or "",
                use_memory=False,
            )
            emit(
                "llm.request_nomem",
                provider=llm.provider,
                model=llm.model,
                messages=nomem_messages,
                use_memory=False,
            )
            compared = await llm.complete(nomem_messages)
            emit(
                "llm.response_nomem",
                answer=compared.text,
                elapsed_ms=compared.elapsed_ms,
            )
            print()
            print("--- without memory ---")
            print(compared.text.strip() or "(empty answer)")

        emit("cli.turn.end", status="ok", hits=hits)
    except Exception as exc:
        emit("cli.turn.end", status="error", error_type=type(exc).__name__)
        raise
    finally:
        reset_context()


async def async_main() -> int:
    settings = get_settings()
    log_path = setup_logging(source="cli", log_dir=settings.log_dir or None)
    try:
        try:
            llm = build_chat_llm(settings)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        harness = get_agent_harness()
        service = get_memory_service()
        state = CliState()

        print(f"LLM {llm.provider}/{llm.model}")
        print(f"memory table {settings.memory_table_name} @ {settings.memory_db_path}")
        if log_path:
            print(f"log -> {log_path}")
        print("Type a task, or /help. /quit to exit.")

        while True:
            try:
                line = input("task> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                continue
            if line.startswith("/"):
                keep = await handle_command(line, state=state, service=service)
                if not keep:
                    break
                continue
            try:
                await run_turn(line, state=state, harness=harness, llm=llm)
            except Exception as exc:
                print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)

        return 0
    finally:
        shutdown_logging()


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent Memory Engine CLI")
    parser.parse_args()
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
