import json
import urllib.request
import urllib.error

SERVER_URL = "http://127.0.0.1:8099"
NAME = "strands-decider"

class ServerUnavailable(RuntimeError):
    pass


class Decider:

    @staticmethod
    def noul(instructions, criteria=None):
        question = {
            "type": "noul",
            "instructions": instructions
        }

        if criteria:
            question["criteria"] = criteria

        return question

    def ask(self, state, questions):
        payload = {
            "state": state,
            "model": "hobson-latest",
            "questions": questions
        }

        request = urllib.request.Request(
            f"{SERVER_URL}/v1/systemone",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))

            return result["answers"]

        except urllib.error.URLError as exc:
            raise ServerUnavailable(
                f"Decision server unavailable: {exc}"
            ) from exc

    def health(self):
        try:
            with urllib.request.urlopen(
                f"{SERVER_URL}/health", timeout=10
            ) as response:
                return json.loads(response.read().decode("utf-8"))

        except urllib.error.URLError as exc:
            raise ServerUnavailable(
                f"Decision server unavailable: {exc}"
            ) from exc

    def banner(self):
        health = self.health()
        return (
            f"Decision server: {health['checkpoint']} "
            f"at {SERVER_URL}"
        )

    def __str__(self):
        return "Decision model client"
