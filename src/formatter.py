"""Human-readable mathematical formulations for supported problems."""

from __future__ import annotations

from src.schemas import KnapsackProblem


def format_knapsack_model(problem: KnapsackProblem) -> str:
    """Return a readable 0/1 knapsack mathematical model."""
    variable_names = [_safe_var_name(item.name) for item in problem.items]
    objective_terms = [
        (_clean_number(item.value), variable)
        for item, variable in zip(problem.items, variable_names)
    ]
    weight_terms = [
        (_clean_number(item.weight), variable)
        for item, variable in zip(problem.items, variable_names)
    ]

    return "\n".join(
        [
            "maximize",
            f"  {_format_linear_expression(objective_terms)}",
            "",
            "subject to",
            (
                f"  {_format_linear_expression(weight_terms)} "
                f"<= {_clean_number(problem.capacity)}"
            ),
            "",
            "binary variables",
            f"  {', '.join(variable_names)} in {{0, 1}}",
        ]
    )


def _format_linear_expression(terms: list[tuple[int | float, str]]) -> str:
    formatted_terms: list[str] = []
    for coefficient, variable in terms:
        sign = "-" if coefficient < 0 else "+"
        term = f"{abs(coefficient)}*{variable}"
        if not formatted_terms:
            formatted_terms.append(f"-{term}" if sign == "-" else term)
        else:
            formatted_terms.append(f" {sign} {term}")
    return "".join(formatted_terms)


def _safe_var_name(name: str) -> str:
    variable = "".join(char if char.isalnum() else "_" for char in name.strip())
    return variable or "item"


def _clean_number(value: float) -> int | float:
    return int(value) if float(value).is_integer() else value
