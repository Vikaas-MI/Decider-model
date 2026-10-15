from __future__ import annotations

import json
import sys
from client import NAME, Decider, ServerUnavailable
from strands import Agent, tool
from strands.interventions import Guide, InterventionHandler, Proceed, Confirm, Deny

QUESTIONS = {
    "has_steps": Decider.noul(
        "Does the report include steps to reproduce the problem?",
        {
            "true": "the reporter lists concrete steps that lead to the problem",
            "false": "the report only describes the symptom, with no steps",
        },
    ),
    "data_loss": Decider.noul(
        "Does the report indicate that user data may have been lost, deleted, or become missing?",
        {
            "true": "The report states or strongly indicates missing, deleted, or lost user data",
            "false": "The report does not indicate missing, deleted, or lost user data",
        },
    ),
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

        print("----Probabilities----")
        print(f"has_steps: {has_steps:.2f}")
        print(f"data_loss: {data_loss:.2f}")

        if data_loss >= RISK:
            prompt = "Critical Bug. Escale to a human (y/n):"
            user_response = input(prompt).strip().lower()

            if user_response in ("y", "yes"):
                verdict = "Approved"
                action = Proceed()
            elif user_response in ("n", "no"):
                verdict = "Rejected"
                action = Deny(reason="Human rejected the critical bug assignment.")
            else:
                print("Invalid response. Please enter y or n.")
                verdict = "Rejected" 
                action = Deny(reason="Human rejected the critical bug assignment.")          

            print(f"{verdict}\n")
            return action

        elif has_steps < STEPS:
            verdict, action = "guided", Guide(
                feedback=(
                    "The report has no reproduction steps. Ask the reporter for the "
                    "steps, then try again."
                )
            )
        else:
            verdict, action = "Proceeded", Proceed()

        self.log.append(
            {
                "tool": name,
                "has_steps": round(has_steps, 2),
                "data_loss": round(data_loss, 2),
                "verdict": verdict,
            }
        )
        print(f"{verdict}\n")
        return action


@tool
def assign_bug(team: str) -> str:
    """Assign a bug report to a development team."""
    print("Bug Assigning tool called...")
    return f"Bug assigned to {team}"


SYSTEM_PROMPT = (
    "You are an eager bug assignment assistant. Always answer bug reports by calling the "
    "assign_bug tool immediately. Never ask the user for clarification -- if no reproducible steps are"
    "given, just assume it is a less critical bug and call the tool with team='Software Engineering'."
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
        callback_handler=None, 
    )

    print(f"\nUSER: {USER_REQUEST}\n")
    result=agent(USER_REQUEST)

    print(f"AGENT: {result}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())