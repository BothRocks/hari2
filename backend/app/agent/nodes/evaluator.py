# backend/app/agent/nodes/evaluator.py
"""Evaluator node - assesses if retrieved context is sufficient."""
import json
import re
import time
from typing import Any

from app.agent.state import AgentState, EvaluationResult
from app.agent.pricing import calculate_cost
from app.agent.utils import get_date_context
from app.services.llm.client import LLMClient


EVALUATION_PROMPT = """You are evaluating whether the retrieved context is sufficient to answer the user's question.

{date_context}

USER QUESTION:
{query}

RETRIEVED CONTEXT:
{context}

Evaluate the context and respond with a JSON object:
{{
    "is_sufficient": true/false,
    "confidence": 0.0-1.0,
    "missing_information": ["list", "of", "missing", "info"],
    "reasoning": "Brief explanation"
}}

Consider:
- Does the context directly address the question?
- Is the information current/relevant?
- Are there gaps that external search could fill?

Respond ONLY with the JSON object, no other text."""


def parse_evaluation_response(response: str) -> EvaluationResult:
    """
    Parse LLM response into EvaluationResult.

    Handles both raw JSON and markdown-wrapped JSON.
    """
    # Try to extract JSON from markdown code block
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_str = response.strip()

    try:
        data = json.loads(json_str)
        return EvaluationResult(
            is_sufficient=data.get("is_sufficient", False),
            confidence=float(data.get("confidence", 0.5)),
            missing_information=data.get("missing_information", []),
            reasoning=data.get("reasoning", ""),
        )
    except (json.JSONDecodeError, KeyError, ValueError):
        # Default to insufficient if parsing fails
        return EvaluationResult(
            is_sufficient=False,
            confidence=0.5,
            missing_information=["Failed to parse evaluation"],
            reasoning=f"Parse error: {response[:200]}",
        )


def check_limits(state: AgentState) -> dict[str, Any] | None:
    """
    Check if any guardrail limits have been exceeded.

    Returns:
        State update dict with exceeded_limit set, or None if within limits
    """
    # Check timeout
    if state.start_time > 0:
        elapsed = time.time() - state.start_time
        if elapsed > state.timeout_seconds:
            return {"exceeded_limit": "timeout"}

    # Check cost
    if state.cost_spent_usd >= state.cost_ceiling_usd:
        return {"exceeded_limit": "cost"}

    return None


async def evaluator_node(
    state: AgentState,
    llm_client: LLMClient | None = None,
) -> dict[str, Any]:
    """
    Evaluate if retrieved context is sufficient to answer the query.

    Args:
        state: Current agent state with query and internal_results
        llm_client: Optional LLM client (creates new if not provided)

    Returns:
        State update with evaluation result and updated cost
    """
    # Check limits before processing
    limit_exceeded = check_limits(state)
    if limit_exceeded:
        return limit_exceeded

    client = llm_client or LLMClient()

    # Format context from results
    context_parts = []
    for doc in state.internal_results:
        title = doc.get("title", "Untitled")
        summary = doc.get("quick_summary", doc.get("summary", ""))
        context_parts.append(f"[{title}]\n{summary}")

    for doc in state.external_results:
        title = doc.get("title", "Web Result")
        content = doc.get("content", doc.get("snippet", ""))
        context_parts.append(f"[{title} (external)]\n{content}")

    context_text = "\n\n".join(context_parts) if context_parts else "No context retrieved."

    prompt = EVALUATION_PROMPT.format(
        date_context=get_date_context(),
        query=state.query,
        context=context_text,
    )

    try:
        response = await client.complete(
            prompt=prompt,
            system="You are a context evaluator. Respond only with JSON.",
            max_tokens=500,
            temperature=0.0,  # Deterministic for evaluation
        )

        # Calculate and track cost
        cost = calculate_cost(
            provider=response.get("provider", "anthropic"),
            model=response.get("model", ""),
            input_tokens=response.get("input_tokens", 0),
            output_tokens=response.get("output_tokens", 0),
        )
        new_cost = state.cost_spent_usd + cost

        evaluation = parse_evaluation_response(response["content"])
        return {
            "evaluation": evaluation,
            "cost_spent_usd": new_cost,
        }

    except Exception as e:
        # On error, default to sufficient to avoid infinite loops
        return {
            "evaluation": EvaluationResult(
                is_sufficient=True,
                confidence=0.5,
                missing_information=[],
                reasoning=f"Evaluation error: {str(e)}",
            )
        }
