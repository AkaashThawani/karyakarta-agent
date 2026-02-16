"""
Enhanced LangGraph Workflow with Task Decomposition and Page Context

Adds:
1. Task planning phase using TaskDecomposer
2. Page state context for Playwright actions
3. Multi-step execution tracking
"""

from typing import List, Callable, Any, Optional, TypedDict, Annotated
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.base import BaseCheckpointSaver
from operator import add
import json


class EnhancedState(TypedDict):
    """Extended state with planning and context."""
    messages: Annotated[List, add]  # Conversation messages
    plan: Optional[dict]  # Task decomposition plan
    current_step_index: int  # Which step we're on
    page_context: Optional[dict]  # Browser page state (URL, title, etc.)
    element_registry: Optional[dict]  # Identified interactive elements with semantic labels
    task_completed: bool  # Track if we're done


def create_enhanced_workflow(
    tools: List[Any],
    model_with_tools: Any,
    checkpointer: BaseCheckpointSaver,
    llm_service: Any,
    logger_callback: Optional[Callable[[str, str], None]] = None
):
    """
    Create enhanced workflow with task decomposition and page context.

    Args:
        tools: List of LangChain tools
        model_with_tools: LLM model with tools bound
        checkpointer: Memory checkpointer
        llm_service: LLM service for planning
        logger_callback: Optional logging callback

    Returns:
        Compiled LangGraph workflow
    """

    def planning_node(state: EnhancedState):
        """
        Phase 1: Analyze task and create execution plan using TaskDecomposer.
        Creates a fresh plan for each new user query.
        """
        if logger_callback:
            logger_callback("📋 Creating execution plan...", "thinking")

        messages = state["messages"]
        last_user_message = None

        # Get the last user message
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                last_user_message = msg.content
                break

        if not last_user_message:
            print("[PLANNING] No user message found, skipping planning")
            return {}

        # Check if we have an existing plan
        existing_plan = state.get("plan")
        if existing_plan:
            # Compare with current query - if different, clear old plan
            if existing_plan.get("original_query") != last_user_message:
                print(f"[PLANNING] 🔄 New query detected, clearing old plan")
                print(f"  Old: {existing_plan.get('original_query', 'N/A')[:50]}...")
                print(f"  New: {last_user_message[:50]}...")
                # Will create fresh plan below
            else:
                # Same query, skip planning
                if logger_callback:
                    logger_callback("Using existing plan for same query", "thinking")
                return {}

        # Check if this is a complex task that needs planning
        # Simple heuristics: if it mentions specific actions or websites, plan it
        needs_planning = any(keyword in last_user_message.lower() for keyword in [
            # Navigation keywords
            'website', 'go to', 'navigate', 'browse', 'visit', 'open',
            # Action keywords
            'find', 'extract', 'get', 'search for', 'look up', 'check',
            # Theater/entertainment keywords
            'timing', 'schedule', 'showtime', 'theater', 'cinema', 'movie',
            'amc', 'regal', 'cinemark',  # Theater names
            # Multi-step indicators
            'and then', 'after that', 'also', 'select', 'choose', 'pick',
            # Data extraction
            'scrape', 'pull', 'fetch', 'download', 'grab'
        ])

        if not needs_planning:
            print("[PLANNING] Simple query, no planning needed")
            return {}

        # Use TaskDecomposer
        try:
            from src.routing.task_decomposer import create_decomposer

            decomposer = create_decomposer(llm_service)
            subtasks = decomposer.decompose(
                task_description=last_user_message,
                task_id="task_001"
            )

            if subtasks:
                plan = {
                    "subtasks": subtasks,
                    "total_steps": len(subtasks),
                    "original_query": last_user_message
                }

                print(f"[PLANNING] ✅ Created plan with {len(subtasks)} steps:")
                for i, subtask in enumerate(subtasks, 1):
                    print(f"  {i}. {subtask.get('tool')}: {subtask.get('description', 'N/A')}")

                return {
                    "plan": plan,
                    "current_step_index": 0,
                    "task_completed": False
                }
            else:
                print("[PLANNING] No subtasks generated, proceeding without plan")
                return {}

        except Exception as e:
            print(f"[PLANNING] Error during planning: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def should_continue(state: EnhancedState):
        """
        Decides whether to continue, plan, or end.
        """
        messages = state['messages']
        last_message = messages[-1]

        # If agent wants to use tools, continue
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "continue"

        # Check if we have a plan and haven't completed it
        plan = state.get("plan")
        if plan:
            current_step = state.get("current_step_index", 0)
            total_steps = plan.get("total_steps", 0)

            if current_step < total_steps:
                print(f"[WORKFLOW] Plan not complete ({current_step}/{total_steps}), continuing...")
                return "continue"
            else:
                print(f"[WORKFLOW] ✅ Plan completed ({current_step}/{total_steps})")

        # Otherwise, end
        return "end"

    def page_intelligence_node(state: EnhancedState):
        """
        After navigation, scan page and identify all interactive elements.
        Creates semantic registry for reliable element access.
        """
        page_context = state.get("page_context")

        # Only scan if we just navigated to a new page
        if not page_context or not page_context.get('url'):
            print("[PAGE_INTEL] No page context, skipping scan")
            return {}

        # Check if we already scanned this page
        existing_registry = state.get("element_registry")
        if existing_registry and existing_registry.get("url") == page_context.get("url"):
            print(f"[PAGE_INTEL] Already scanned {page_context.get('url')}, skipping")
            return {}

        print(f"[PAGE_INTEL] 🔍 Scanning page: {page_context.get('url')}")

        try:
            # Get playwright page instance
            from src.tools.playwright_universal import UniversalPlaywrightTool
            playwright_tool = UniversalPlaywrightTool(session_id="global")
            page = playwright_tool._page

            if not page:
                print("[PAGE_INTEL] ⚠️ No page instance available")
                return {}

            # Scan page and build registry
            from src.core.page_intelligence import get_page_intelligence_scanner
            scanner = get_page_intelligence_scanner()

            # Run async scan
            import asyncio
            loop = asyncio.get_event_loop()
            registry = loop.run_until_complete(scanner.scan_page(page))

            if registry:
                print(f"[PAGE_INTEL] ✅ Registry built: {len(registry.get('inputs', {}))} inputs, {len(registry.get('buttons', {}))} buttons")
                return {"element_registry": registry}
            else:
                print("[PAGE_INTEL] ⚠️ No elements found")
                return {}

        except Exception as e:
            print(f"[PAGE_INTEL] ❌ Scan failed: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def call_model(state: EnhancedState):
        """
        Enhanced agent node with FORCED PLAN EXECUTION.
        Uses element registry to find correct selectors.
        """
        if logger_callback:
            logger_callback("Agent is analyzing the task...", "thinking")

        messages = state['messages']
        plan = state.get("plan")
        page_context = state.get("page_context")
        element_registry = state.get("element_registry")
        current_step = state.get("current_step_index", 0)

        # 🔥 FORCED PLAN EXECUTION 🔥
        if plan:
            total_steps = plan.get("total_steps", 0)

            if current_step < total_steps:
                subtasks = plan.get("subtasks", [])
                current_subtask = subtasks[current_step]

                tool_name = current_subtask.get('tool')
                tool_params = current_subtask.get('parameters', {})

                print(f"[AGENT] 🎯 FORCING step {current_step + 1}/{total_steps}: {tool_name}")
                print(f"[AGENT] Parameters: {tool_params}")

                # 🧠 SMART PARAMETER ENHANCEMENT
                # If playwright action, use element registry to find correct selectors
                if tool_name == "playwright_execute" and element_registry:
                    method = tool_params.get("method")

                    # Enhance fill actions
                    if method == "fill":
                        # Find search input from registry
                        search_input = element_registry.get("inputs", {}).get("search_input")
                        if search_input:
                            tool_params["selector"] = search_input["selector"]
                            print(f"[AGENT] 📌 Using registry selector for fill: {search_input['selector']}")

                    # Enhance click actions - prefer press Enter over clicking
                    elif method == "click" or method == "press":
                        # Strategy: After filling search, just press Enter
                        # More reliable than finding/clicking button
                        if "enter" in current_subtask.get("description", "").lower():
                            tool_params["method"] = "press"
                            tool_params["args"] = {"key": "Enter"}
                            tool_params.pop("selector", None)
                            tool_params.pop("selector_hint", None)
                            print(f"[AGENT] ⌨️  Using press Enter instead of click")
                        else:
                            # Try to find button in registry
                            buttons = element_registry.get("buttons", {})
                            # Find first clickable search/submit button
                            for btn_name, btn_data in buttons.items():
                                if btn_data.get("clickable") and btn_data.get("purpose") in ["search", "submit"]:
                                    tool_params["selector"] = btn_data["selector"]
                                    print(f"[AGENT] 📌 Using registry selector for click: {btn_data['selector']}")
                                    break

                # Create forced tool call with proper metadata
                from langchain_core.messages import AIMessage
                forced_response = AIMessage(
                    content="",
                    tool_calls=[{
                        "name": tool_name,
                        "args": tool_params,
                        "id": f"forced_call_{current_step}"
                    }],
                    # Add metadata that streaming expects
                    usage_metadata={
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "total_tokens": 0
                    },
                    response_metadata={
                        "model_name": "forced_execution",
                        "finish_reason": "tool_calls"
                    }
                )

                # Update step counter
                return {
                    "messages": [forced_response],
                    "current_step_index": current_step + 1
                }

        # Fallback: Regular LLM execution if no plan
        context_additions = []

        # Add page context if browser is open
        if page_context:
            page_msg = f"""
[PAGE CONTEXT]
You have a browser page already open:
- URL: {page_context.get('url', 'Unknown')}
- Title: {page_context.get('title', 'Unknown')}

DO NOT navigate again. Use playwright_execute with method='evaluate' to get content.
"""
            context_additions.append(SystemMessage(content=page_msg))
            print(f"[AGENT] Page context available: {page_context.get('url', 'Unknown')}")

        # Add element registry info
        if element_registry:
            inputs = element_registry.get("inputs", {})
            buttons = element_registry.get("buttons", {})

            registry_msg = f"""
[ELEMENT REGISTRY]
Page has {len(inputs)} inputs and {len(buttons)} buttons identified.

Available inputs: {list(inputs.keys())}
Available buttons: {list(buttons.keys())}

Use these semantic names when referencing elements.
"""
            context_additions.append(SystemMessage(content=registry_msg))
            print(f"[AGENT] Element registry available: {len(inputs)} inputs, {len(buttons)} buttons")

        # Build enhanced message list
        enhanced_messages = messages.copy()
        if context_additions:
            enhanced_messages = messages[:-1] + context_additions + [messages[-1]]

        response = model_with_tools.invoke(enhanced_messages)

        return {"messages": [response]}

    def enhanced_tool_node(state: EnhancedState):
        """
        Enhanced tool execution that captures page context from playwright.
        """
        messages = state['messages']
        last_message = messages[-1]

        # Execute tools normally
        tool_node = ToolNode(tools)
        result = tool_node.invoke(state)

        # Check if playwright was executed
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            for tool_call in last_message.tool_calls:
                if tool_call['name'] == 'playwright_execute':
                    # Capture page context from the result
                    tool_messages = result.get('messages', [])
                    if tool_messages:
                        last_tool_result = tool_messages[-1]

                        # Try to parse the result
                        try:
                            if hasattr(last_tool_result, 'content'):
                                content = last_tool_result.content
                                result_data = None

                                # Handle different content types
                                if isinstance(content, dict):
                                    result_data = content
                                elif isinstance(content, str):
                                    # Try to parse as JSON
                                    try:
                                        result_data = json.loads(content)
                                    except json.JSONDecodeError:
                                        # Not valid JSON, skip page context
                                        print(f"[TOOLS] ⚠️ Playwright result is not valid JSON, skipping page context")
                                        result_data = None

                                if result_data and result_data.get('success'):
                                    # Only update page context if URL exists
                                    # (Some operations like fill don't return URL)
                                    page_url = result_data.get('url')
                                    if page_url:
                                        page_context = {
                                            'url': page_url,
                                            'status': result_data.get('status'),
                                            'ok': result_data.get('ok'),
                                            'title': result_data.get('title', 'Unknown'),
                                            'has_page': True
                                        }
                                        result['page_context'] = page_context
                                        print(f"[TOOLS] 📄 Captured page context: {page_context['url']}")
                                    # else: Keep existing page context (don't overwrite with None)
                                else:
                                    print(f"[TOOLS] ⚠️ Playwright result missing 'success' field or failed")
                        except Exception as e:
                            print(f"[TOOLS] ⚠️ Error processing playwright result: {e}")

        return result

    def should_run_page_intel(state: EnhancedState) -> str:
        """
        Decide if we should run page intelligence after tool execution.
        Only run if:
        1. Just navigated to a new page (playwright goto)
        2. Page context changed
        """
        messages = state['messages']
        if not messages:
            return "skip_intel"

        last_message = messages[-1]

        # Check if last tool call was a navigation
        if len(messages) >= 2:
            prev_message = messages[-2]
            if hasattr(prev_message, 'tool_calls') and prev_message.tool_calls:
                for tool_call in prev_message.tool_calls:
                    if tool_call.get('name') == 'playwright_execute':
                        args = tool_call.get('args', {})
                        if args.get('method') == 'goto':
                            return "run_intel"

        return "skip_intel"

    # Create the enhanced workflow graph
    workflow = StateGraph(EnhancedState)

    # Add nodes
    workflow.add_node("planning", planning_node)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", enhanced_tool_node)
    workflow.add_node("page_intelligence", page_intelligence_node)

    # Set entry point to planning
    workflow.set_entry_point("planning")

    # Planning always goes to agent
    workflow.add_edge("planning", "agent")

    # Agent decides what to do next
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "continue": "tools",
            "end": END,
        },
    )

    # After tools, decide if we should scan page
    workflow.add_conditional_edges(
        "tools",
        should_run_page_intel,
        {
            "run_intel": "page_intelligence",
            "skip_intel": "agent"
        }
    )

    # After page intelligence, go back to agent
    workflow.add_edge("page_intelligence", "agent")

    # Compile with checkpointer
    return workflow.compile(checkpointer=checkpointer)
