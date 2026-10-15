from __future__ import annotations

import json
import sys
from client import NAME, Decider, ServerUnavailable
from strands import Agent, tool
from strands.interventions import Guide, InterventionHandler, Proceed, Confirm

QUESTIONS = {
    "has_steps": Decider.noul(
        "Does the report include steps to reproduce the problem?",
        {
            "true": "the reporter lists concrete steps that lead to the problem",
            "false": "the report only describes the symptom, with no steps",
        },
    ),
    "data_loss": Decider.noul(
        "Does the report mention data loss or a security problem?",
        {
            "true": "data is lost, exposed, or accessible to the wrong person",
            "false": "no data loss or security concern is mentioned",
        },
    )
}

STEPS = 0.5
RISK = 0.7

class ToolCallReviewer(InterventionHandler):
    """Review each proposed tool call before it runs, using strands-decider."""

    name = f"{NAME}-tool-call-reviewer"

    def __init__(self, decider: Decider) -> None:
        self._decider = decider
        self.log: list[dict[str, object]] = []

    @staticmethod
    def _render(messages: list[dict]) -> str:
        """Flatten Strands' message list to plain text: only the human-readable blocks."""
        lines: list[str] = []
        for message in messages:
            role = message.get("role", "unknown")
            for block in message.get("content", []):
                if isinstance(block, dict) and "text" in block:
                    lines.append(f"{role}: {block['text']}")
        return "\n".join(lines) if lines else "(no conversation yet)"

    def before_tool_call(self, event, **kwargs):
        name = event.tool_use["name"]
        arguments = event.tool_use.get("input") or {}
        state = (
            "A conversation between a user and a Bug reporting AI assistant is below, followed by a "
            "tool call the assistant now wants to make.\n\n"
            f"--- CONVERSATION ---\n{self._render(event.agent.messages)}\n\n"
            f"--- PROPOSED TOOL CALL ---\ntool: {name}\n"
            f"arguments: {json.dumps(arguments)}"
        )

        answers = self._decider.ask(state, QUESTIONS)

        has_steps = answers["has_steps"]["noul"]
        data_loss = answers["data_loss"]["noul"]

        print("[intervention] classifications (probability of 'yes'):")
        print(f"    has_steps  : {has_steps:.2f}")
        print(f"    data_loss      : {data_loss:.2f}")

        if has_steps < STEPS:
            verdict, action = "guided", Guide(
                feedback=(
                    "The report has no reproduction steps. Ask the reporter for the "
                    "steps, then try again."
                )
            )
        elif data_loss >= RISK:
            verdict, action = "confirmed", Confirm(
                prompt=(
                    "Critical bug or possible data loss. Escalate to a human?"
                )
            )
        else:
            verdict, action = "proceeded", Proceed()

        self.log.append(
            {
                "tool": name,
                "has_steps": round(has_steps, 2),
                "data_loss": round(data_loss, 2),
                "verdict": verdict,
            }
        )
        print(f"    -> {verdict}\n")
        return action


@tool
def assign_bug(team: str) -> str:
    """Assign a bug report to a development team."""
    return f"Bug assigned to {team}"


SYSTEM_PROMPT = (
    "You are an eager bug assignment assistant. Always answer bug reports by calling the "
    "assign_bug tool immediately. Never ask the user for clarification -- if no reproducible steps are"
    "given, just assume it is a less critical bug and call the tool with team='RD'."
)


def main() -> int:
    decider = Decider()
    try:
        print(decider.banner(), "\n")
    except ServerUnavailable as exc:
        print(exc)
        return 1

    USER_REQUEST = input ("Enter Bug: ")

    gate = ToolCallReviewer(decider)
    agent = Agent(
        model="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        tools=[assign_bug],
        interventions=[gate],
        system_prompt=SYSTEM_PROMPT,
        callback_handler=None,  # the gate's own log is the interesting output
    )

    print(f"the agent proposes each tool call; {NAME} decides whether it is ready to run\n")
    print(f"USER: {USER_REQUEST}\n")
    result = agent(USER_REQUEST)

    guided = sum(1 for row in gate.log if row["verdict"] == "guided")
    print(f"{decider}; guided {guided} of {len(gate.log)} proposed calls back for clarification")
    print(f"\n--- what the agent finally replied ---\n{result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())