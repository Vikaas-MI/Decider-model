# Decider-model

A small bug-triage demo that puts a fast decision model in front of an AI agent.

A bug assignment agent (Claude on Amazon Bedrock) reads a bug report and tries to call an `assign_bug` tool. Before that tool runs, **Strands Decider 2B** checks the report and scores two yes/no questions. Your code then decides whether to let the call through, send the agent back for more detail, or ask a human.

## How it works

1. You type a bug report in the terminal.
2. The agent proposes a call to the `assign_bug` tool.
3. An intervention handler (`ToolCallReviewer`) pauses the call and sends the conversation and the proposed call to the local decider server.
4. The decider returns a probability for each question:

   | Question | Meaning |
   |---|---|
   | `has_steps` | Does the report include steps to reproduce the problem? |
   | `data_loss` | Does the report indicate user data may be lost, deleted, or missing? |

5. The handler applies simple rules:

   | Condition | Action |
   |---|---|
   | `data_loss` is 0.7 or higher | Ask a human in the terminal (`y`/`n`). `y` proceeds, anything else is denied |
   | `has_steps` is below 0.5 | Guide the agent to ask the reporter for reproduction steps |
   | Otherwise | Proceed and assign the bug |

The cutoffs (`STEPS = 0.5`, `RISK = 0.7`) are set at the top of `handler.py`. Tune them on your own bug reports.

## Files

| File | What it does |
|---|---|
| `client.py` | Small client for the local decider server (`Decider.noul(...)`, `ask(...)`, `health()`) |
| `handler.py` | The questions, the `ToolCallReviewer` intervention handler, the `assign_bug` tool, and the terminal demo |
| `.gitignore` | Files git should ignore |

## Requirements

- Python 3.10 or newer
- About 5 GB of free disk space (the model downloads on first run)
- AWS credentials with Amazon Bedrock access to the Claude model named in `handler.py` (`us.anthropic.claude-haiku-4-5-20251001-v1:0`)

## Setup

**1. Clone the repo**

```
git clone https://github.com/Vikaas-MI/Decider-model.git
cd Decider-model
```

**2. Create and activate a virtual environment**

Windows:

```
python -m venv venv
venv\Scripts\activate
```

Mac or Linux:

```
python3 -m venv venv
source venv/bin/activate
```

**3. Install the packages**

```
pip install strands-decider strands-agents
```

**4. Set your AWS credentials** (the agent's LLM runs on Bedrock)

```
aws configure
```

Or set `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` and `AWS_DEFAULT_REGION` yourself.

**5. Start the decider server** in a first terminal (venv active) and leave it running

```
strands-decider serve StrandsAgents/strands-decider-2B-hobson-v19 --port 8099
```

The first run downloads the model (about 4.6 GB), so expect a wait. Port 8099 must match `SERVER_URL` in `client.py`.

**6. Run the demo** in a second terminal (venv active, same folder)

```
python handler.py
```

Type a bug report when prompted.

## Try it

- **Clear report, should proceed:** `Steps: 1) open orders page 2) export CSV. Expected a file, got a 500 error.`
- **Vague report, should be guided:** `Search is slow sometimes.`
- **Data loss, should ask a human:** `After the update, all my saved projects are gone.`

The terminal prints the decider's probabilities (`has_steps`, `data_loss`) and the verdict for each tool call.

## Troubleshooting

- **`Decision server unavailable`:** the server from step 5 is not running, or its port does not match `SERVER_URL` in `client.py`.
- **AWS or Bedrock errors:** check your credentials, your region, and that your account has access to the Claude model named in `handler.py`.
- **`strands-decider: command not found`:** activate the virtual environment in that terminal first.
- **Server flags differ:** run `strands-decider serve --help` to check the options for your installed version.

## Credits

Built on [Strands Decider](https://github.com/strands-labs/strands-decider) and [Strands Agents](https://strandsagents.com).
