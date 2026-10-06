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

For mock mode, keep:

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

Public AI 8B example:

```env
MOCK_APERTUS=false
APERTUS_API_URL=https://api.publicai.co/v1/chat/completions
APERTUS_API_KEY=your_public_ai_api_key
APERTUS_MODEL=swiss-ai/apertus-v1.5-8b
```

Swisscom Apertus 1.5 70B example:

```env
MOCK_APERTUS=false
APERTUS_API_URL=https://api.swisscom.com/products/swiss-ai-platform/apertus-1.5-70b/v1/chat/completions
APERTUS_API_KEY=your_swisscom_api_key
APERTUS_MODEL=swiss-ai/Apertus-v1.5-70B
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

If your Apertus endpoint does not use OpenAI-compatible chat completions, update `ApertusClient.generate()` and `_extract_text()` in `src/apertus_client.py`.

## Run Tests

```bash
cd ApertusOpt
python -m unittest discover -s tests
```

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
