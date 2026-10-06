# ApertusOpt

ApertusOpt is a starter project for converting a natural-language optimization problem into a structured mathematical optimization model, validating it, solving it with a mathematical solver, and evaluating the result.

The first MVP supports only the 0/1 Knapsack Problem.

The key idea is separation of responsibilities: Apertus translates human language into structured JSON, Pydantic validates the generated model, and OR-Tools computes the optimal solution. The LLM is not asked to solve the optimization problem.

```text
Natural Language
|
v
Apertus
|
v
Structured JSON
|
v
Validator
|
v
OR-Tools
|
v
Optimal Solution
```

## Architecture

The pipeline is:

1. Natural-language problem text is inserted into `prompts/knapsack_prompt.txt`.
2. `src/apertus_client.py` sends the prompt to an Apertus-compatible API, or returns a deterministic response in mock mode.
3. `src/parser.py` extracts JSON, removes accidental markdown fences, parses it, and validates it with Pydantic.
4. `src/formatter.py` renders the validated problem as a readable mathematical formulation.
5. `src/solver.py` solves the validated 0/1 knapsack problem with Google OR-Tools.
6. `src/evaluator.py` checks solution feasibility and reported totals.

The command-line demo prints every major step: generated JSON, readable mathematical formulation, solver result, and evaluation.

## Installation

Use Python 3.11 or newer.

```bash
git clone https://github.com/thomas240103/ApertusOpt.git
cd ApertusOpt
python -m pip install -r requirements.txt
```

If you are working from an already cloned copy, just run the last two commands from inside the project directory.

## Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

On PowerShell:

```powershell
Copy-Item .env.example .env
```

The template selects CSCS for real API calls. For offline mode, use `--mock` or set:

```env
MOCK_APERTUS=true
```

When you are ready to use a real Apertus API, set `MOCK_APERTUS=false` or remove it, then fill in:

```env
APERTUS_API_URL=https://your-apertus-endpoint.example/v1/chat/completions
APERTUS_API_KEY=your_api_key
APERTUS_MODEL=your_model_name
```

The client uses an OpenAI-compatible chat completions payload by default:

```json
{
  "model": "your_model_name",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."}
  ],
  "temperature": 0
}
```

## Run Mock Mode

Mock mode needs no API connection:

```powershell
cd ApertusOpt
python main.py --mock
```

On macOS or Linux:

```bash
cd ApertusOpt
python main.py --mock
```

You can also set `MOCK_APERTUS=true` in `.env` and run `python main.py`.

Mock mode always returns the built-in example JSON, so it is best for testing the pipeline without an API key.

## Run With Apertus API

Set these variables in `.env` or in your shell.

### Selected Provider: CSCS

We use CSCS with Apertus 1.5 70B as the starting model for the hackathon demo.
The [hackathon resources](https://hackapertus.devpost.com/resources) list CSCS inference
access for all teams. The [CSCS documentation](https://docs.cscs.ch/services/inference/api/)
documents the OpenAI-compatible endpoint, the model below, and processing within
CSCS infrastructure in Switzerland without recording prompts or responses.

This is a starting choice, not a measured accuracy claim. After obtaining access,
compare the 70B and 8B models on the same problems for extraction accuracy and latency.
Pydantic checks structure and types; it does not prove that Apertus extracted the
user's numbers correctly. The demo checks the solution against the generated model.
The benchmark below also compares the extraction with hand-checked reference data.

To obtain access:

1. Open the hackathon resources page and follow its Getting Started Guide for CSCS access.
   If access is not provisioned, use the organizer Discord linked on that page.
2. Once your team has a CSCS project with an inference resource, sign in to the
   [Inference API UI](https://ui.inference.cscs.ch/), expand the resource, and select
   **Add Key**. Create a key with access to the chosen Apertus model.
3. Add the key to the local `.env` file. `.env` is ignored by Git; never add the key
   to `.env.example` or commit it.

```env
MOCK_APERTUS=false
APERTUS_API_URL=https://api.inference.cscs.ch/v1/chat/completions
APERTUS_API_KEY=your_cscs_inference_api_key
APERTUS_MODEL=swiss-ai/Apertus-v1.5-70B
```

Availability depends on your key's permissions. Check the API UI or the documented
`GET /v1/models` endpoint if the model is unavailable. To compare the smaller model,
change only `APERTUS_MODEL` to `swiss-ai/Apertus-v1.5-8B`.

From the repository directory, run without `--mock`:

```powershell
.\.venv\Scripts\python.exe main.py --file problems\camping_knapsack.txt
```

Use `python` instead if dependencies are installed outside this virtual environment.
Ensure `MOCK_APERTUS` is not still `true` in your shell: shell environment variables
take precedence over `.env`. In PowerShell, clear an old override with
`Remove-Item Env:MOCK_APERTUS -ErrorAction SilentlyContinue`.

With a correct extraction, the camping example selects tent, stove, and camera for
weight 12 and value 32. The budget example selects Search, Analytics, and Export for
cost 15 and value 33. These are expected results for checking the live pipeline;
they are not evidence of a successful API call. Mock mode always returns A + B,
value 24, regardless of the input file.

### Alternative Provider: Public AI

Public AI uses a separate API key. Its [quick start](https://platform.publicai.co/docs)
documents this endpoint and model:

```env
MOCK_APERTUS=false
APERTUS_API_URL=https://api.publicai.co/v1/chat/completions
APERTUS_API_KEY=your_public_ai_api_key
APERTUS_MODEL=swiss-ai/apertus-v1.5-8b
```

Then run:

```bash
cd ApertusOpt
python main.py
```

You can pass a custom natural-language problem directly:

```bash
python main.py --text "I have a backpack with capacity 10 kg. Item A weighs 4 kg and is worth 10. Item B weighs 6 kg and is worth 14. Item C weighs 3 kg and is worth 7. Select the items that maximize total value."
```

Or read the problem from a text file:

```bash
python main.py --file problems/camping_knapsack.txt
```

Use either `--text` or `--file`, not both.

If your Apertus endpoint does not use OpenAI-compatible chat completions, update `ApertusClient.generate()` and `_extract_text()` in `src/apertus_client.py`.

## Run Tests

```bash
cd ApertusOpt
python -m unittest discover -s tests
```

## Reference Cases and Live Evaluation

`problems/knapsack_cases.json` contains natural-language inputs, expected JSON, and
expected solutions. Reference answers are never sent to Apertus.

| Case | Expected result |
| --- | --- |
| `base` | A + B, weight 10, value 24 |
| `capacity_7` | A + C, weight 7, value 17 |
| `italian` | Same problem in Italian: A + B, value 24 |
| `camping` | tent + stove + camera, weight 12, value 32 |
| `budget` | Search + Analytics + Export, cost 15, value 33 |
| `decimals` | A + B, weight 2.5, value 7.5 |
| `none_fit` | No selected items, value 0 (still OPTIMAL) |
| `missing_weight` | Explicit JSON error identifying the missing weight of B |

Run from the repository directory:

```bash
python evaluate.py
```

This offline check feeds reference JSON to the validator and solver. It makes no
API calls and does **not** measure Apertus: `apertus_tested` is false. Seven reference
cases should pass; `missing_weight` is skipped because it needs a model response.
Unit tests also verify the reference optima by enumerating every possible subset.

Once the API key is configured and `MOCK_APERTUS=false`, test a single case first:

```bash
python evaluate.py --live --case capacity_7
python evaluate.py --live
```

The full live run makes eight API calls. The JSON report distinguishes schema
validity, exact formulation matching, and solution matching, and includes raw
responses and elapsed time. Item order is ignored; item names and all numerical
data must match. A correct objective alone is not enough to pass. The current
complete cases have unique optimal selections. A new case with tied optima would
need the solution comparison adapted to accept all valid optimal selections.

For missing data, the response must be an object containing only a nonempty
`error` string mentioning B and weight (or Italian `peso`). This is a simple
keyword check, not a semantic assessment of the explanation. Malformed JSON,
invented data, unrelated refusals, and API failures do not pass. The solver is
never called for this case. Exit codes: 0 for no failures, 1 for failed cases,
2 for configuration or CLI errors. `--live` refuses mock mode.

## Demo Output

In mock mode, the example problem should produce:

```text
Mathematical formulation:
maximize
  10*A + 14*B + 7*C

subject to
  4*A + 6*B + 3*C <= 10

binary variables
  A, B, C in {0, 1}

Solution:
{
  "status": "OPTIMAL",
  "selected_items": ["A", "B"],
  "total_weight": 10,
  "total_value": 24
}
```

## Expected JSON

```json
{
  "problem_type": "knapsack",
  "sense": "maximize",
  "items": [
    {
      "name": "A",
      "weight": 4,
      "value": 10
    }
  ],
  "capacity": 10
}
```
