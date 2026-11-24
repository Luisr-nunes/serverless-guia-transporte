# Individual Activity 1: Serverless (Rota Vital)

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)

[Português](README.md) | **English**

Infraestrutura de Software · ADS · CESAR School · 2026.2

An HTTP function that receives a Rota Vital request and returns the **transport guide**, running on the local machine with the **AWS SAM CLI** (Path A of the assignment: no AWS account, nothing published to the cloud).

- **Path chosen:** A (local AWS SAM CLI, Python 3.12, Docker Desktop).
- **Environment:** Windows, commands run in Git Bash. SAM CLI 1.174.0 installed with `python -m pip install --user aws-sam-cli` (`sam.exe` ends up in `...\Python312\Scripts`, which must be on the `PATH`).
- **Evidence:** the [`evidencias/`](evidencias/) folder holds the output of every command.

## How to run

```bash
export SAM_CLI_TELEMETRY=0
# Docker Desktop must be open

# unit tests for the handler (no Docker)
python -m unittest tests.unit.test_handler -v

# Step 3: event + invocation
sam local generate-event apigateway aws-proxy --method POST --path guias \
  --body '{"requisicaoId":"R-001","hospital":"H-Recife","bolsas":["O-NEG-0142"]}' > events/pedido.json
sam build
sam local invoke -e events/pedido.json

# Step 4: HTTP (use another terminal for curl)
sam local start-api                         # then: sam local start-api --warm-containers LAZY
curl -X POST http://127.0.0.1:3000/guias -H "Content-Type: application/json" \
  -d '{"requisicaoId":"R-002","hospital":"H-Caruaru"}'

# Step 5: time limit (Timeout 3 in the template, then 10)
curl -X POST http://127.0.0.1:3000/guias -H "Content-Type: application/json" \
  -d '{"requisicaoId":"R-003","demorar":true}'
```

The project comes from `sam init` (Hello World, Python 3.12, zip). In `template.yaml` the route changed from `/hello` (GET) to `/guias` (POST), and `hello_world/app.py` is the function from the assignment. The template `Timeout` is **10** because Step 5 ends with that adjustment.

## What differs from the assignment PDF

**1. Event body in base64.** `sam local generate-event` in version 1.174 produces the `body` in base64 with `"isBase64Encoded": true`. The assignment handler reads `body` directly and failed with `JSONDecodeError` (the output of that attempt is in `evidencias/02a-...` and `02b-...`). I added decoding to the handler when `isBase64Encoded` is true (3 lines) and a unit test for that case. Over HTTP (`start-api`) the body arrives as plain text and is not affected.

**2. `start-api` without `--warm-containers` already reuses the environment.** The PDF expects `invocacaoNesteAmbiente` to go back to 1 on every call without the option. In this SAM version the log shows "Initializing the lambda functions containers" at startup: the container is created before the first request and reused. The counter grew 1, 2, 3 in both modes. The visible difference was the first call time (table below). `sam local invoke`, on the other hand, starts a new container on every run and the counter stayed at 1 in both.

## Measured results

| Experiment | Result | Time | Evidence |
|---|---|---|---|
| `sam local invoke` (1st, failed on base64) | `JSONDecodeError`, Duration 96.38 ms | 28.06 s wall clock (included building the Docker image) | `02a-...` |
| `sam local invoke` (2nd, failed on base64) | `JSONDecodeError`, Duration 115.78 ms | 6.52 s | `02b-...` |
| `sam local invoke` (1st, fixed) | 201, guide `G-R-001`, counter 1, Duration 93.95 ms, Init 0.08 ms | 5.38 s | `03-invoke-1.txt` |
| `sam local invoke` (2nd, fixed) | 201, counter 1, Duration 104.30 ms, Init 0.13 ms | 5.59 s | `03-invoke-2.txt` |
| `start-api` no option, 3 calls | 201 on all, counter 1, 2, 3 | 1.21 s, 1.08 s, 1.08 s | `04a-curl-sem-warm.txt` |
| `start-api --warm-containers LAZY`, 3 calls | 201 on all, counter 1, 2, 3 | 3.93 s, 1.10 s, 1.12 s | `04b-curl-warm-lazy.txt` |
| `demorar: true`, Timeout 3 | HTTP 502 `{"message":"Internal server error"}`; log: `Function 'HelloWorldFunction' timed out after 3 seconds` | 4.18 s | `05a-curl-timeout3.txt` |
| `demorar: true`, Timeout 10 | 201, guide `G-R-003` | 6.21 s | `05b-curl-timeout10.txt` |

Wall-clock time includes the emulator overhead (starting the Docker container, sending the event), so it is much larger than the function's `Duration`, which is the handler time.

## Answers

**1. Why was the first invocation slower than the second? What happens in the Init phase?**
In the attempt that failed, the first invocation took 28 s and the second 6.5 s. The difference came from the first one having to build the runtime's Docker image; on the second the image already existed. After the event was fixed, both took almost the same time (5.4 s and 5.6 s), because every `sam local invoke` starts a new container, so every invocation is a cold start. In the Init phase the service creates the environment, downloads the code, starts the runtime and runs whatever sits outside the handler (imports and the global variable `contador`). Only then does it call the handler. In the emulator, `Init Duration` shows 0.06 to 0.13 ms: it does not measure the real startup, so the cost of a real cold start can only be seen in the CloudWatch logs (path B).

**2. What did `invocacaoNesteAmbiente` show with and without `--warm-containers`? What does that say about keeping state in a global variable?**
With `sam local invoke` it stayed at 1 every time, because each run uses a new environment. With `start-api` it grew 1, 2, 3 in both modes (in this SAM version the container is already created at startup; with LAZY it is only created on the first request, which is why the first call took 3.9 s). The conclusion is the same: the global variable only survives while the environment is reused, and the platform decides that, not the code. It cannot be relied on, because a new instance starts from zero and two instances in parallel would have different counters. Any state that matters (counts, sessions, a cache that must not be lost) has to live outside the function, for example in a database.

**3. What happened with `demorar = true`? What is the maximum execution time in Lambda, and what to do with longer work?**
The function sleeps 5 s, but the template limits execution to 3 s. SAM stopped the function (`timed out after 3 seconds`) and the HTTP call returned 502 with `Internal server error`. With the Timeout at 10, the same call finished with 201 in 6.2 s. In Lambda the maximum execution time is 15 minutes, according to the service quotas. Work longer than that is split into smaller steps, put on a queue for a worker that runs without that limit (a container, for example), or orchestrated step by step with a workflow service.

**4. How much does one million executions cost with 128 MB and 100 ms (us-east-1 prices from class)?**
- Requests: 1,000,000 ÷ 1,000,000 × US$ 0.20 = **US$ 0.20**.
- Compute: 128 MB = 0.125 GB; 100 ms = 0.1 s; 0.125 × 0.1 = 0.0125 GB-s per execution. For one million: 0.0125 × 1,000,000 = 12,500 GB-s. Cost: 12,500 × US$ 0.0000166667 = **US$ 0.2083**.
- Total: 0.20 + 0.2083 = **US$ 0.4083, about US$ 0.41** per million executions.

Within the always-free tier (1 million requests and 400 thousand GB-s per month, cited in the assignment), this load would cost zero.

**5. Where in Rota Vital would a function like this make sense, and where not?**
It makes sense for generating the transport guide when a requisition is approved: short, stateless work that only runs when the event happens and needs no server running the rest of the time. It does not make sense for temperature telemetry: it receives readings all the time (up to 500 per second in the high scenario of Section E of the group work), and the aggregator keeps state in memory and needs a single instance. That is the opposite of the serverless model, where several instances are born and die without shared memory.

## AI use

- **Tool:** Claude (Anthropic).
- **Purpose:** install SAM CLI and open Docker, run the commands of steps 3 to 5 on this computer and save the outputs in `evidencias/`, fix the handler for the base64 event, write the unit tests and draft this README.
- **How it was validated:** every result cited in the answers and in the table comes from a file in `evidencias/`, generated by the commands themselves; the 4 unit tests pass; the author reviewed the text before delivery (PO-CESAR-021, allowed with declaration).
