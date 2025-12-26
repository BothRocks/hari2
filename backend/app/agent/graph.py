# backend/app/agent/graph.py
"""LangGraph agent definition for agentic RAG."""
from typing import Any, AsyncIterator
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import AgentState
from app.utils.sse import format_sse, chunk_sentences, build_thinking_message
from app.agent.nodes.retriever import retriever_node
from app.agent.nodes.evaluator import evaluator_node
from app.agent.nodes.router import router_node
from app.agent.nodes.researcher import researcher_node
from app.agent.nodes.generator import generator_node


async def _retriever_wrapper(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Wrapper to pass session from config to retriever node."""
    session = config.get("configurable", {}).get("session") if config else None
    return await retriever_node(state, session=session)


async def _evaluator_wrapper(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Wrapper for evaluator node."""
    return await evaluator_node(state)


async def _researcher_wrapper(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Wrapper for researcher node."""
    return await researcher_node(state)


async def _generator_wrapper(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Wrapper for generator node."""
    return await generator_node(state)


def _router_wrapper(state: AgentState) -> str:
    """Wrapper for router node to determine next step."""
    return router_node(state)


def create_agent_graph() -> StateGraph:
    """
    Create the agentic RAG graph.

    Graph structure:
        START -> retrieve -> evaluate -> [router]
                                           |
                              sufficient ---> generate -> END
                                           |
                            insufficient ---> research -> evaluate (loop)

    Returns:
        Compiled LangGraph StateGraph
    """
    # Create graph with AgentState schema
    # LangGraph expects a dict-like state, so we use model_dump for compatibility
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("retrieve", _retriever_wrapper)
    workflow.add_node("evaluate", _evaluator_wrapper)
    workflow.add_node("research", _researcher_wrapper)
    workflow.add_node("generate", _generator_wrapper)

    # Define edges
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "evaluate")

    # Conditional edge from evaluate based on router decision
    workflow.add_conditional_edges(
        "evaluate",
        _router_wrapper,
        {
            "generate": "generate",
            "research": "research",
        }
    )

    # Research loops back to evaluate
    workflow.add_edge("research", "evaluate")

    # Generate is terminal
    workflow.add_edge("generate", END)

    return workflow.compile()


async def run_agent(
    query: str,
    session: AsyncSession | None = None,
    max_iterations: int = 3,
) -> AgentState:
    """
    Run the agentic RAG pipeline.

    Args:
        query: User's question
        session: Database session for retrieval
        max_iterations: Maximum research iterations

    Returns:
        Final agent state with answer and sources
    """
    graph = create_agent_graph()

    initial_state = AgentState(
        query=query,
        max_iterations=max_iterations,
    )

    # Pass session through config for retriever node
    config = {"configurable": {"session": session}}

    # Run graph - result is a dict
    result = await graph.ainvoke(initial_state, config=config)

    # Convert result dict back to AgentState
    if isinstance(result, dict):
        return AgentState(**result)
    return result


async def run_agent_stream(
    query: str,
    session: AsyncSession | None = None,
    max_iterations: int = 3,
) -> AsyncIterator[str]:
    """
    Run the agentic RAG pipeline with streaming events.

    Args:
        query: User's question
        session: Database session for retrieval
        max_iterations: Maximum research iterations

    Yields:
        SSE-formatted event strings
    """
    graph = create_agent_graph()

    initial_state = AgentState(
        query=query,
        max_iterations=max_iterations,
    )

    config = {"configurable": {"session": session}}

    final_state = {}
    seen_nodes = set()

    try:
        async for event in graph.astream_events(initial_state, config=config, version="v2"):
            event_type = event.get("event", "")
            node_name = event.get("name", "")

            # Emit thinking event when node starts
            if event_type == "on_chain_start" and node_name in ("retrieve", "evaluate", "research", "generate"):
                if node_name not in seen_nodes:
                    seen_nodes.add(node_name)
                    thinking = build_thinking_message(node_name, final_state)
                    yield format_sse("thinking", thinking)

            # Capture output and emit chunks/sources when generate completes
            if event_type == "on_chain_end" and node_name == "generate":
                output = event.get("data", {}).get("output", {})
                if not isinstance(output, dict):
                    output = {}
                final_state.update(output)

                # Emit answer chunks
                answer = output.get("final_answer", "")
                if answer:
                    for sentence in chunk_sentences(answer):
                        yield format_sse("chunk", {"content": sentence})

                # Emit sources
                sources = output.get("sources", [])
                internal = []
                external = []
                for s in sources:
                    source_dict = s if isinstance(s, dict) else s.model_dump() if hasattr(s, 'model_dump') else {}
                    if source_dict.get("source_type") == "external":
                        external.append(source_dict)
                    else:
                        internal.append(source_dict)
                yield format_sse("sources", {"internal": internal, "external": external})

            # Update state from other node outputs
            if event_type == "on_chain_end" and node_name != "generate":
                output = event.get("data", {}).get("output", {})
                if output and isinstance(output, dict):
                    final_state.update(output)

    except Exception as e:
        yield format_sse("error", {"step": "unknown", "message": str(e)})

    # Emit done event
    research_iterations = final_state.get("research_iterations", 0)
    yield format_sse("done", {"research_iterations": research_iterations})
