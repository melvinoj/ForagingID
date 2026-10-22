#!/usr/bin/env python3
"""Context-size warnings for Claude Code sessions (config only, not part of the app).

Two modes, one calculation (context_tokens):
  context_check.py               UserPromptSubmit hook: prints a warning above WARN_TOKENS
  context_check.py --statusline  status line: prints "ctx ~<N>k"

Both read the hook/status-line JSON on stdin and use its transcript_path.
Never fails the prompt: on any error it prints nothing and exits 0.
"""
import json
import sys

WARN_TOKENS = 400_000
LIMIT_TOKENS = 500_000


def context_tokens(transcript_path):
    """Context size of the last main-thread assistant turn in the transcript, or None."""
    last = None
    with open(transcript_path, encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if entry.get("type") != "assistant" or entry.get("isSidechain"):
                continue
            message = entry.get("message") or {}
            usage = message.get("usage")
            if not usage or message.get("model") == "<synthetic>":
                continue
            last = usage
    if last is None:
        return None
    return (
        (last.get("input_tokens") or 0)
        + (last.get("cache_creation_input_tokens") or 0)
        + (last.get("cache_read_input_tokens") or 0)
    )


def hook_message(tokens):
    k = round(tokens / 1000)
    if tokens > LIMIT_TOKENS:
        return (
            f"CONTEXT LIMIT: ~{k}k tokens. Tell Melvin in your first line. Do not start new work; "
            "finish or safely pause the current step and give the End Session state."
        )
    if tokens >= WARN_TOKENS:
        return (
            f"CONTEXT WARNING: ~{k}k tokens. Tell Melvin in your first line, finish the current "
            "step only, then recommend End Session and a new session."
        )
    return None


def main():
    try:
        data = json.load(sys.stdin)
        tokens = context_tokens(data["transcript_path"])
        if tokens is None:
            return
        if "--statusline" in sys.argv[1:]:
            print(f"ctx ~{round(tokens / 1000)}k")
            return
        message = hook_message(tokens)
        if message:
            print(message)
    except Exception:
        pass


if __name__ == "__main__":
    main()
    sys.exit(0)
