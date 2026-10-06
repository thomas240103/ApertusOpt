# ApertusOpt

ApertusOpt is a starter project for converting a natural-language optimization problem into a structured mathematical optimization model, validating it, solving it with a mathematical solver, and evaluating the result.

The first MVP supports only the 0/1 Knapsack Problem.

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
4. `src/solver.py` solves the validated 0/1 knapsack problem with Google OR-Tools.
5. `src/evaluator.py` checks solution feasibility and reported totals.

## Installation

Use Python 3.11 or newer.

```bash
cd ApertusOpt
python -m pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file in the `ApertusOpt` directory when you are ready to use the real API:

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

```bash
cd ApertusOpt
$env:MOCK_APERTUS="true"
python main.py
```

On macOS or Linux:

```bash
cd ApertusOpt
MOCK_APERTUS=true python main.py
```

## Run With Apertus API

Set these variables in `.env` or in your shell:

```env
APERTUS_API_URL=https://your-apertus-endpoint.example/v1/chat/completions
APERTUS_API_KEY=your_api_key
APERTUS_MODEL=your_model_name
```

Then run:

```bash
cd ApertusOpt
python main.py
```

If your Apertus endpoint does not use OpenAI-compatible chat completions, update `ApertusClient.generate()` and `_extract_text()` in `src/apertus_client.py`.

## Run Tests

```bash
cd ApertusOpt
python -m unittest discover -s tests
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
