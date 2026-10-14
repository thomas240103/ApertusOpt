# ApertusOpt

## Local Web Interface

The English load planner runs on the existing Python dependencies:

```powershell
& ".\.venv\Scripts\python.exe" web_app.py
```

Open http://127.0.0.1:8765. If the port is occupied, use `--port 8766`.
An alternative environment file can be selected with `--env-file PATH`.

1. Load the example, or select **Apertus API** and enter a description (English or Italian).
2. Choose **Extract data**. Demo mode always returns the fixed example, even for different text.
3. Review and edit pallet names, weights (kg), volumes (m3), margins (EUR), and both truck capacities.
4. Confirm the data and choose **Optimize load**.
5. Inspect selected/excluded pallets, capacity allocation, a deterministic English summary,
   elapsed solver time, and margin change versus the previous run. Download the verified JSON report.

Editing data invalidates the displayed solution and requires confirmation again. Changing the
description or extraction mode requires a new extraction. Comparisons are session-local, compare
the two reported objective values only, and do not establish why a pallet was excluded.
No history is persisted. Reloading clears the comparison.

API keys stay on the Python server in `.env`; they are never sent to the browser.
Live extraction requires the existing Apertus configuration and `MOCK_APERTUS=false`.
The text is sent only when **Extract data** is clicked in API mode. Editing and solving do not
call the LLM. Extracted data must be checked against the description: schema validation alone
cannot establish semantic correctness. API/parse failures show a sanitized error.

This is a loopback-only development server, not a public deployment. It rejects cross-origin
requests and unexpected Host headers, serves only allowlisted assets, limits request size and
allows only one API/solver job at a time. Do not expose it through a tunnel or proxy.
The UI accepts at most 500 pallets. OR-Tools has a 10-second solve limit in the web app;
**FEASIBLE** is explicitly distinguished from **OPTIMAL**. There is still no 3D packing,
stacking, axle-load or load-safety model. The original command-line workflow is unchanged.

Run all tests and a reproducible solver-only performance sample:

```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests
& ".\.venv\Scripts\python.exe" benchmark_solver.py
```

The benchmark uses seeded synthetic sets of 50, 100 and 500 pallets. Timings depend on hardware
and instance difficulty; these are not worst-case guarantees or Apertus extraction measurements.

ApertusOpt is a starter project for converting a natural-language optimization problem into a structured mathematical optimization model, validating it, solving it with a mathematical solver, and evaluating the result.

The MVP supports 0/1 knapsack selection: the original one-capacity examples and
whole-pallet selection with both weight and volume limits. It does not support
general optimization, multiple trucks, divisible goods or product quantities.

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

1. Natural-language problem text is inserted into `prompts/knapsack_prompt.txt`,
   or `prompts/pallet_prompt.txt` when `--pallets` is selected.
2. `src/apertus_client.py` sends the prompt to an Apertus-compatible API, or returns a deterministic response in mock mode.
3. `src/parser.py` extracts JSON, removes accidental markdown fences, parses it, and validates it with Pydantic.
4. `src/formatter.py` renders the validated problem as a readable mathematical formulation.
5. `src/solver.py` solves the validated 0/1 knapsack problem with Google OR-Tools.
6. `src/evaluator.py` checks solution feasibility and reported totals.

The command-line demo prints every major step: generated JSON, readable mathematical formulation, solver result, and evaluation.

## Truck Pallet Selection

Choose optional, indivisible pallets for a single journey to one destination.
Each row identifies one physical pallet, available once. If two pallets contain
the same product, give them different identifiers. The objective is to maximize
the sum of the supplied profit margins, not to maximize weight or sales revenue.
Margins are input data: Apertus must not estimate them.

The JSON keeps the original `knapsack` structure and adds a second constraint:

```json
{
  "problem_type": "knapsack",
  "sense": "maximize",
  "capacity": 1000,
  "volume_capacity": 5,
  "items": [
    {"name": "A", "weight": 400, "volume": 1.2, "value": 80}
  ]
}
```

In pallet mode, `weight` and `capacity` are kg, `volume` and `volume_capacity`
are m3, and `value` is the total margin for that pallet in EUR. Both available
capacities and every pallet's weight, volume and margin are required. Explicit
units can be converted by the prompt; missing or ambiguous data must produce
an error instead of assumptions. Validate the extracted numbers before relying
on a result: Pydantic validates the model, not its fidelity to the original text.

For every pallet i, the solver chooses x_i in {0, 1}:

```text
maximize sum(margin_i * x_i)
subject to sum(weight_i * x_i) <= available_weight
           sum(volume_i * x_i) <= available_volume
```

The two constraints use independently scaled integers for
[OR-Tools CP-SAT](https://developers.google.com/optimization/cp/cp_solver).
Numbers requiring more than 10 decimal places or exceeding the safe scaled
integer range are rejected rather than silently rounded. Negative margins
are allowed, and loading nothing is a valid choice.

From the repository folder, after installing dependencies:

```powershell
# Offline demonstration, no API call:
& ".\.venv\Scripts\python.exe" main.py --pallets --mock

# Real Apertus extraction (configure .env and MOCK_APERTUS=false):
& ".\.venv\Scripts\python.exe" main.py --pallets

# Your own description, including both available truck capacities:
& ".\.venv\Scripts\python.exe" main.py --pallets --file problems\pallet_loading.txt

# Pallet reference checks, then the real-model benchmark:
& ".\.venv\Scripts\python.exe" evaluate.py --pallets
& ".\.venv\Scripts\python.exe" evaluate.py --pallets --live
```

Use `python` instead of the Windows executable path when appropriate. `--text`
also works with `--pallets`. The pallet mock always returns the fixed truck
example, even for custom text; it tests the pipeline, not language understanding.

The supplied demo has 10000 kg and 25 m3 available:

| Pallet | Weight (kg) | Volume (m3) | Margin (EUR) |
| --- | ---: | ---: | ---: |
| A | 4000 | 12 | 300 |
| B | 3500 | 10 | 280 |
| C | 3000 | 8 | 220 |
| D | 2500 | 6 | 200 |
| E | 2000 | 5 | 120 |

Expected optimum: **B + C + D**, weight **9000 kg**, volume **24 m3**, margin
**700 EUR**. Available capacity left: 1000 kg and 1 m3. Weight alone would select
A + B + D for 780 EUR, but that load needs 28 m3 and violates the volume limit.
The original solution keys are retained: `selected_items`, `total_weight`,
`total_value`, plus `total_volume`. The CLI also prints a pallet summary with
units, `total_profit_eur` and remaining capacities.

`problems/pallet_cases.json` is a separate development suite: 5 complete cases
(demo, weight-limited, volume-limited, decimals/quoted names, nothing fits) and
2 missing-data cases. Offline evaluation expects 5 passes and 2 skips; a full
live run makes 7 API calls and must explicitly identify missing data. These are
development checks, not a held-out estimate of real-world accuracy. Unit tests
also compare small generated problems against exhaustive enumeration.

**Scope:** all pallets are compatible and optional. This is selection under
aggregate limits, not a physical loading plan. Total volume alone does not
guarantee geometric fit, stackability, axle balance or safe loading. No routes,
delivery deadlines, multiple trucks or loading certification are calculated.
The prompt rejects unsupported constraints, but a valid JSON response cannot
prove that an LLM noticed every constraint. Do not use this prototype as an
operational loading or safety decision system.

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

Without `--pallets`, mock mode always returns the original backpack JSON.
With `--pallets`, it returns the fixed truck example above.

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
they are not evidence of a successful API call. Without `--pallets`, mock mode always returns A + B,
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
| `compound_names` | Advanced Search + Feature Search, cost 7, value 18; quoted names preserved |
| `decimals` | A + B, weight 2.5, value 7.5 |
| `none_fit` | No selected items, value 0 (still OPTIMAL) |
| `missing_weight` | Explicit JSON error identifying the missing weight of B |

Run from the repository directory:

```bash
python evaluate.py
```

This offline check feeds reference JSON to the validator and solver. It makes no
API calls and does **not** measure Apertus: `apertus_tested` is false. Eight reference
cases should pass; `missing_weight` is skipped because it needs a model response.
Unit tests also verify the reference optima by enumerating every possible subset.

Once the API key is configured and `MOCK_APERTUS=false`, test a single case first:

```bash
python evaluate.py --live --case capacity_7
python evaluate.py --live
```

The full live run makes nine API calls. The JSON report distinguishes schema
validity, exact formulation matching, and solution matching, and includes raw
responses and elapsed time. Item order is ignored; item names and all numerical
data must match. A correct objective alone is not enough to pass. The current
complete cases have unique optimal selections. A new case with tied optima would
need the solution comparison adapted to accept all valid optimal selections.

The prompt distinguishes category labels from explicit names: `Feature Search`
in the original budget case should yield `Search`, while a feature explicitly
named `"Feature Search"` must retain the complete name. The `budget` input and its
expected answer are unchanged; `compound_names` checks preservation of multiword
names, including a name that begins with `Feature`. The evaluator still compares
names exactly and does not strip prefixes after generation.

To check just these two cases with Apertus:

```bash
python evaluate.py --live --case budget
python evaluate.py --live --case compound_names
```

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
