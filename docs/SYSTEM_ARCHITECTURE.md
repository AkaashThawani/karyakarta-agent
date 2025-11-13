# KaryaKarta Agent System Architecture

## Overview
KaryaKarta is a multi-agent AI system designed for web automation and data extraction tasks. The system uses a modular architecture with specialized agents, tools, and services working together to accomplish complex tasks.

## System Entry Points

### FastAPI Application (`main.py`)
**Purpose:** FastAPI web server entry point with graceful shutdown handling.

**Key Components:**
```python
app = FastAPI(
    title="KaryaKarta Agent API",
    description="AI Agent with Google Search and Web Scraping capabilities",
    version="1.0.0"
)

# Routes
app.include_router(router)  # Task execution routes
app.include_router(session_router)  # Session management routes

# Middleware setup
setup_middleware(app, allowed_origins=["http://localhost:3000"])

# Shutdown handler
@app.on_event("shutdown")
async def shutdown_event():
    # Cleanup Playwright browser instances
    UniversalPlaywrightTool.stop_all_loops()
```

### Agent Logic (`agent_logic.py`)
**Purpose:** Central orchestration layer managing agent execution modes.

**Configuration:**
```python
USE_MULTI_AGENT_SYSTEM = True  # Toggle between MultiAgentManager and AgentManager
```

**Key Functions:**
```python
def get_agent_manager() -> AgentManager | MultiAgentManager:
    # Returns configured agent manager instance

def create_tools_for_session(session_id: str) -> List[BaseTool]:
    # Creates all available tools for a session

def run_agent_task(prompt: str, message_id: str, session_id: str) -> str:
    # Main task execution function with timeout and cancellation handling

def cancel_task(message_id: str) -> Dict[str, Any]:
    # Cancel running tasks
```

### API Routes (`api/routes.py`)
**Endpoints:**
```python
@router.get("/") → {"status": "KaryaKarta Python Agent is running."}

@router.get("/health") → {"status": "healthy", "service": "karyakarta-agent"}

@router.post("/execute-task") → TaskResponse
    # Accepts: TaskRequest(prompt, messageId, sessionId)
    # Returns: TaskResponse(status, messageId, sessionId, message)
    # Runs task in background via run_agent_task()

@router.post("/cancel-task") → CancellationResult
    # Accepts: CancelRequest(messageId)
    # Returns: {"status": "cancelled|not_found", "message": str}
```

### Session Routes (`api/session_routes.py`)
**Session Management Endpoints:**
```python
@router.post("/sessions/") → Created session data
@router.get("/sessions/{session_id}") → Session data
@router.get("/sessions/") → List of user sessions
@router.patch("/sessions/{session_id}") → Update session
@router.delete("/sessions/{session_id}") → Delete session

@router.post("/sessions/{session_id}/messages") → Add message
@router.get("/sessions/{session_id}/messages") → Get messages
@router.get("/sessions/{session_id}/buffer") → Memory buffer stats
@router.get("/sessions/{session_id}/context") → Formatted LLM context
```

### Middleware (`api/middleware.py`)
**Middleware Stack:**
```python
# 1. Error handling (catches all exceptions)
async def error_handling_middleware(request, call_next)

# 2. Request logging (logs method, path, timing)
async def request_logging_middleware(request, call_next)

# 3. CORS (cross-origin resource sharing)
setup_cors(app, allowed_origins=["http://localhost:3000"])

# 4. Rate limiting (100 requests/minute)
setup_rate_limiting(app)
```

## Core Data Models

### AgentMessage
**File:** `src/agents/base_agent.py`

```python
class AgentMessage(BaseModel):
    id: str = Field(default_factory=lambda: f"msg_{uuid4().hex[:8]}")
    from_agent: str = Field(..., description="ID of agent sending message")
    to_agent: str = Field(..., description="ID of agent receiving")
    message_type: MessageType = Field(..., description="Type of message")
    payload: Dict[str, Any] = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

**Message Types:**
- `REQUEST`: Agent asking another agent to perform task
- `RESPONSE`: Reply to REQUEST with result
- `STATUS`: Progress update on ongoing task
- `ERROR`: Something went wrong
- `BROADCAST`: Message to all other agents

**Methods:**
- `to_dict()` → `Dict[str, Any]`: Convert to dictionary
- `from_dict(data)` → `AgentMessage`: Create from dictionary
- `is_valid()` → `bool`: Validate message has required fields
- `create_response(payload, metadata)` → `AgentMessage`: Create response message

### AgentState
**File:** `src/agents/base_agent.py`

```python
class AgentState(BaseModel):
    status: AgentStatus = Field(default=AgentStatus.IDLE)
    current_task: Optional[Dict[str, Any]] = Field(default=None)
    task_history: List[Dict[str, Any]] = Field(default_factory=list)
    capabilities: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=lambda: {
        "task_completed": 0,
        "task_failed": 0,
        "total_execution_time": 0.0
    })
    error_message: Optional[str] = Field(default=None)
    last_updated: datetime = Field(default_factory=datetime.now)
```

**Agent Status Enum:**
- `IDLE`: Agent is ready for new task
- `THINKING`: Agent is analyzing/planning
- `EXECUTING`: Agent is performing a task
- `WAITING`: Agent is waiting for response/resource
- `ERROR`: Agent encountered error
- `COMPLETED`: Agent finished its work

**Methods:**
- `update_status(new_status, error_msg)`: Update agent status
- `start_task(task)`: Start a new task
- `complete_task(success, result)`: Complete current task
- `add_capability(capability)`: Add capability to agent
- `can_handle(task_type)` → `bool`: Check if agent can handle task type
- `get_metrics()` → `Dict[str, Any]`: Get current metrics

### AgentResult
**File:** `src/agents/base_agent.py`

```python
class AgentResult(BaseModel):
    success: bool = Field(..., description="Whether execution succeeded")
    data: Any = Field(default=None, description="Result data")
    agent_id: str = Field(..., description="ID of agent that produced result")
    execution_time: float = Field(default=0.0, description="Execution time in seconds")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    timestamp: datetime = Field(default_factory=datetime.now)
    validation: Optional[Dict[str, Any]] = Field(default=None, description="Validation results")
```

**Methods:**
- `to_dict()` → `Dict[str, Any]`: Convert to dictionary
- `from_dict(data)` → `AgentResult`: Create from dictionary
- `is_success()` → `bool`: Check if execution was successful
- `get_error()` → `Optional[str]`: Get error message if failed

**Class Methods:**
- `success_result(data, agent_id, execution_time, metadata)` → `AgentResult`
- `error_result(error, agent_id, execution_time, metadata)` → `AgentResult`

### AgentTask
**File:** `src/agents/base_agent.py`

```python
class AgentTask(BaseModel):
    task_id: str = Field(default_factory=lambda: f"task_{uuid4().hex[:8]}")
    task_type: str = Field(..., description="Type of task")
    description: str = Field(..., description="Human-readable task description")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Task parameters")
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM)
    dependencies: List[str] = Field(default_factory=list, description="Task IDs that must complete first")
    timeout: Optional[int] = Field(default=None, description="Timeout in seconds")
    created_at: datetime = Field(default_factory=datetime.now)
    assigned_to: Optional[str] = Field(default=None, description="Agent ID assigned to")
    status: str = Field(default="pending", description="Task status")
    completed_at: Optional[datetime] = Field(default=None)
    result: Optional[AgentResult] = Field(default=None)
```

**Task Priority Enum:**
- `LOW`: Can be done when resources available
- `MEDIUM`: Normal priority
- `HIGH`: Important, should be done soon
- `URGENT`: Critical, do immediately

**Methods:**
- `has_dependencies()` → `bool`: Check if task has dependencies
- `is_ready(completed_tasks)` → `bool`: Check if task is ready to execute
- `assign_to(agent_id)`: Assign task to an agent
- `mark_in_progress()`: Mark task as in progress
- `mark_completed(result)`: Mark task as completed
- `is_high_priority()` → `bool`: Check if task is high or urgent priority

### TaskRequest & TaskResponse
**File:** `src/models/message.py`

```python
class TaskRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=5000)
    messageId: str = Field(..., pattern=r'^msg_\d+_[a-z0-9]+$')
    sessionId: Optional[str] = Field(default="default", pattern=r'^[a-zA-Z0-9_-]+$')

class TaskResponse(BaseModel):
    status: Literal["success", "error", "already_processing"]
    messageId: str
    sessionId: str
    error: Optional[str] = None
    message: str = "Agent task has been initiated in the background."
```

### AgentSession & SessionMessage
**File:** `src/models/session.py`

```python
class SessionMessage(BaseModel):
    id: str
    role: str  # 'user' or 'agent'
    content: str
    timestamp: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AgentSession(BaseModel):
    session_id: str
    user_id: Optional[str] = None
    status: SessionStatus  # ACTIVE, IDLE, COMPLETED, ERROR
    created_at: str
    updated_at: str
    messages: List[SessionMessage] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(default_factory=dict)
```

### ToolResult (Critical for Data Flow)
**File:** `src/models/tool_result.py`

```python
class ToolResult(BaseModel):
    success: bool = Field(description="Whether the tool execution succeeded")
    data: Optional[Any] = Field(default=None, description="Tool output data (any type)")
    error: Optional[str] = Field(default=None, description="Error message if execution failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    tool_name: Optional[str] = Field(default=None, description="Name of the tool")
```

**Data Flow Issues:**
- **Inconsistent Data Types**: `data` field accepts any type (str, dict, list, etc.)
- **No Validation**: Raw tool outputs pass through without structure enforcement
- **Metadata Overload**: Important extraction results mixed with execution metadata
- **Error Handling**: Success/failure mixed with data extraction failures

**Example Problem Cases:**
```python
# Google Search returns string - no structure
ToolResult(success=True, data="Search results text with URLs...")

# Chart Extractor returns list - structured but inconsistent
ToolResult(success=True, data=[{"name": "item1", "price": "$10"}])

# Playwright returns dict - different structure again
ToolResult(success=True, data={"current_url": "https://example.com"})
```

**Impact on DataFlowResolver:**
- String outputs require regex extraction (unreliable)
- Dict outputs need field navigation (inconsistent paths)
- List outputs need indexing (context-dependent)
- **Result**: Parameter resolution fails → tools get `None` values

## Agent Classes

### BaseAgent (Abstract)
**File:** `src/agents/base_agent.py`

```python
class BaseAgent(ABC):
    def __init__(self, agent_id: str, agent_type: str, capabilities: List[str],
                 llm_service: Optional[Any] = None, logger: Optional[Any] = None)

    @abstractmethod
    def execute(self, task: AgentTask, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        pass

    @abstractmethod
    def can_handle(self, task: AgentTask) -> bool:
        pass

    def send_message(self, message: AgentMessage) -> None:
        pass

    def receive_message(self, message: AgentMessage) -> None:
        pass

    def process_messages(self) -> List[AgentMessage]:
        pass

    def get_status(self) -> AgentState:
        pass

    def reset(self) -> None:
        pass
```

### ReasonAgent
**File:** `src/agents/reason_agent.py`

**Purpose:** Plans task execution strategy and decomposes complex tasks into subtasks.

**Key Methods:**
```python
def execute(self, task: AgentTask, context: Optional[Dict[str, Any]] = None) -> AgentResult:
    # Input: AgentTask with user query
    # Output: AgentResult with execution plan (subtasks)
    # Uses LLM to analyze task and create execution plan

def _analyze_task(self, task: AgentTask, context: Dict[str, Any]) -> Dict[str, Any]:
    # Input: AgentTask, context (conversation history, previous results)
    # Output: Dict with task analysis (task_type, required_tools, task_structure)
    # Uses LLM with task_analysis_schema

def _create_execution_plan(self, analysis: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    # Input: Task analysis, context
    # Output: Dict with subtasks array
    # Uses LLM with subtask_schema or fallback logic
```

**LLM Calls:**
1. `task_analysis_schema` - Analyze task type and requirements
2. `subtask_schema` - Decompose into executable steps

### ExecutorAgent
**File:** `src/agents/executor_agent.py`

**Purpose:** Executes individual tools and manages tool lifecycle.

**Key Methods:**
```python
def execute(self, task: AgentTask, context: Optional[Dict[str, Any]] = None) -> AgentResult:
    # Input: AgentTask with tool name and parameters
    # Output: AgentResult with tool execution result
    # Finds appropriate tool and executes with retry logic

def _execute_with_retry(self, tool: BaseTool, parameters: Dict[str, Any]) -> ToolResult:
    # Input: Tool instance, parameters dict
    # Output: ToolResult (success, data/error, metadata)
    # Handles async tools, retries on failure

def _evaluate_completeness(self, task: AgentTask, tool_result: ToolResult, context) -> Dict[str, Any]:
    # Input: Original task, tool result, execution context
    # Output: Dict with completeness assessment
    # Returns: {"complete": bool, "reason": str, "next_action": str, "coverage": str}
```

**Tool Execution Flow:**
1. Find tool by task.task_type
2. Resolve parameters using DataFlowResolver
3. Execute tool (with async handling)
4. Evaluate result completeness
5. Classify errors for replanning
6. Return AgentResult with metadata

### ExecutionEngine
**File:** `src/agents/execution_engine.py`

**Purpose:** Orchestrates execution of subtask sequences with data flow resolution.

**Key Methods:**
```python
def execute_plan(self, plan: Optional[Dict[str, Any]], task: Any) -> List[Dict[str, Any]]:
    # Input: Execution plan from ReasonAgent, original task
    # Output: List of subtask execution results
    # Routes to sequential or adaptive execution

def _execute_sequential(self, subtasks: List[Dict[str, Any]], plan) -> List[Dict[str, Any]]:
    # Input: List of subtasks, execution plan
    # Output: List of execution results
    # Executes subtasks in order with validation and replanning

def _execute_single_subtask(self, subtask: Dict[str, Any], idx: int, accumulated_data: Dict[str, Any], resolver, plan) -> Dict[str, Any]:
    # Input: Single subtask dict, index, accumulated data, resolver, plan
    # Output: Dict with execution result
    # Resolves parameters, executes via executor, updates accumulated data
```

**Data Flow:**
- Uses DataFlowResolver to resolve parameter dependencies between steps
- Maintains `accumulated_data` dict with results from previous steps
- Supports parallel execution of independent subtasks
- Handles dynamic replanning on step failures

### ResultProcessor
**File:** `src/agents/result_processor.py`

**Purpose:** Processes execution results and synthesizes final answers.

**Key Methods:**
```python
def synthesize_results(self, task_description: str, subtask_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    # Input: Original task description, list of subtask results
    # Output: Dict with synthesized final result
    # Extracts structured data, generates final answer

def check_goal_achieved(self, results: List[Dict[str, Any]], goal: str, plan) -> bool:
    # Input: Execution results, goal string, plan context
    # Output: bool indicating if goal was achieved
    # Uses completeness validation and goal-specific checks

def _generate_answer(self, task_description: str, results: List[Dict[str, Any]]) -> str:
    # Input: Task description, successful results
    # Output: Formatted final answer string
    # Uses LLM synthesis or fallback formatting
```

**LLM Calls:**
1. Synthesis prompt for intelligent answer formatting
2. Structured data extraction from results

### TaskAnalyzer
**File:** `src/agents/task_analyzer.py`

**Purpose:** Analyzes tasks and determines execution requirements using LLM.

**Key Methods:**
```python
def analyze_task(self, task_description: str) -> TaskAnalysis:
    # Input: Task description string
    # Output: TaskAnalysis object with type, tools, complexity
    # Uses comprehensive LLM analysis for complete task understanding

def _analyze_task_comprehensive(self, task_description: str) -> Optional[Dict[str, Any]]:
    # Input: Task description
    # Output: Dict with task_type, required_tools, task_structure
    # Single LLM call with structured output for complete analysis

def extract_required_fields(self, query: str) -> List[str]:
    # Input: User query
    # Output: List of field names (user requested + suggested)
    # Uses LLM to identify useful data fields

def extract_query_params(self, description: str) -> Dict[str, Any]:
    # Input: Task description
    # Output: Dict of API query parameters
    # Extracts parameters like limit, sort, order from natural language

def detect_task_type(self, description: str) -> str:
    # Input: Task description
    # Output: Task type string (search, web_scraping, api_request, etc.)
    # Matches against available tool capabilities
```

**LLM Calls:**
1. Comprehensive task analysis with structured schema
2. Field extraction for data requirements
3. Query parameter extraction
4. Task type detection

### AdaptiveElementMatcher
**File:** `src/agents/adaptive_element_matcher.py`

**Purpose:** AI-powered element discovery using LLM + visual analysis.

**Key Methods:**
```python
async def find_element(self, page: Page, intent: str, url: str, context_hints) -> Optional[Dict[str, Any]]:
    # Input: Playwright page, semantic intent, URL, context hints
    # Output: Element info dict with selector and confidence
    # Multi-stage element discovery: cache → AI → heuristic

async def _ai_element_discovery(self, page: Page, intent: str, url: str, context_hints) -> Optional[Dict[str, Any]]:
    # Input: Page, intent, URL, hints
    # Output: Element match from AI analysis
    # Uses LLM to analyze page context and identify selectors

async def _get_page_context(self, page: Page, intent: str) -> Dict[str, Any]:
    # Input: Playwright page, intent
    # Output: Dict with title, visible text, interactive elements
    # Extracts comprehensive page context for LLM analysis

def _build_element_discovery_prompt(self, intent: str, page_context: Dict[str, Any], context_hints) -> str:
    # Input: Intent, page context, hints
    # Output: LLM prompt for element discovery
    # Creates detailed prompt with page analysis and intent mapping

async def _test_selectors(self, page: Page, candidates: List[Dict[str, Any]], intent: str) -> Optional[Dict[str, Any]]:
    # Input: Page, selector candidates, intent
    # Output: Best working selector match
    # Tests selectors for visibility and functionality
```

**Discovery Strategy:**
1. **Cache Check**: Fast lookup in existing selector map
2. **AI Analysis**: LLM analyzes page context to identify selectors
3. **Heuristic Fallback**: ElementParser-based pattern matching
4. **Caching**: Successful matches cached for future use

**LLM Integration:**
- Page context extraction (title, visible text, interactive elements)
- Intent-to-selector mapping with confidence scores
- Fallback selector generation
- Reasoning explanation for matches

## Service Layer

### LLMService
**File:** `src/services/llm_service.py`

**Purpose:** Abstraction layer for LLM providers with structured output support.

**Key Methods:**
```python
def get_model(self) -> ChatGoogleGenerativeAI:
    # Input: None
    # Output: Configured base LLM model
    # Returns Gemini model with temperature, tokens, etc.

def get_model_with_schema(self, schema: Dict[str, Any], schema_name: str = "response") -> Runnable:
    # Input: JSON schema dict, schema name for caching
    # Output: Runnable with structured output enabled
    # Uses LangChain's with_structured_output()

def invoke_with_schema(self, prompt: str, schema: Dict[str, Any], schema_name: str = "response", system_message: Optional[str] = None) -> Any:
    # Input: Prompt, schema, optional system message
    # Output: Validated response matching schema
    # Convenience method for schema validation
```

**Common Schemas:**
- `get_task_analysis_schema()` - For task analysis responses
- `get_subtask_schema()` - For subtask decomposition
- `get_field_extraction_schema()` - For field extraction

### SessionService
**File:** `src/services/session_service.py`

**Purpose:** Manages conversation persistence and session state.

**Key Methods:**
```python
def create_session(self, session_id: str, user_id: Optional[str] = None) -> AgentSession:
    # Input: Session ID, optional user ID
    # Output: New AgentSession instance
    # Creates and stores new session

def get_session_messages(self, session_id: str) -> List[Dict[str, Any]]:
    # Input: Session ID
    # Output: List of message dicts for session
    # Retrieves conversation history

def add_message_to_session(self, session_id: str, message_id: str, role: str, content: str, tokens: int) -> bool:
    # Input: Session ID, message details
    # Output: bool success indicator
    # Adds message to session and updates database
```

## Tool Layer

### BaseTool (Abstract)
**File:** `src/tools/base.py`

```python
class BaseTool(ABC):
    name: str
    description: str

    @abstractmethod
    def execute(self, **parameters) -> ToolResult:
        pass

    def as_langchain_tool(self) -> Tool:
        # Converts to LangChain tool format
        pass
```

### ToolResult
**File:** `src/models/tool_result.py`

```python
class ToolResult(BaseModel):
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    observation: Optional[str] = None  # For LLM feedback
```

### PlaywrightUniversal Tool
**File:** `src/tools/playwright_universal.py`

**Purpose:** Browser automation tool with multiple methods.

**Key Methods:**
```python
def execute(self, **parameters) -> ToolResult:
    # Input: Dict with method, selector, args, etc.
    # Output: ToolResult with browser interaction result
    # Routes to appropriate browser method

async def _execute_goto(self, url: str) -> ToolResult:
    # Input: URL string
    # Output: ToolResult with navigation result
    # Navigates browser to URL

async def _execute_fill(self, selector: str, value: str) -> ToolResult:
    # Input: CSS selector, value to fill
    # Output: ToolResult with fill operation result
    # Fills form field with value

async def _execute_click(self, selector: str) -> ToolResult:
    # Input: CSS selector
    # Output: ToolResult with click result
    # Clicks element matching selector
```

**Supported Methods:**
- `goto`: Navigate to URL
- `fill`: Fill form field
- `click`: Click element
- `press`: Press key
- `wait_for_timeout`: Wait for time
- `text_content`: Get element text
- `select_option`: Select dropdown option

### GoogleSearch Tool
**File:** `src/tools/search.py`

```python
def execute(self, **parameters) -> ToolResult:
    # Input: Dict with 'query' parameter
    # Output: ToolResult with search results string
    # Performs Google search and returns formatted results
```

**Data Flow Issues:**
- Returns raw string output
- DataFlowResolver tries to extract URLs using regex patterns
- Extraction often fails, causing `url: None` in subsequent steps
- **Root cause of flight search failures**

### ContentExtractor Tool
**File:** `src/tools/content_extractor_tool.py`

```python
def execute(self, **parameters) -> ToolResult:
    # Input: Dict with 'url' parameter
    # Output: ToolResult with clean text content
    # Removes HTML clutter, scripts, styles
```

**Features:**
- Fast HTML parsing with selectolax
- Content extraction without JavaScript execution
- Returns clean, readable text

### InteractiveElementExtractor Tool
**File:** `src/tools/interactive_element_extractor_tool.py`

```python
def execute(self, **parameters) -> ToolResult:
    # Input: Dict with 'url' and 'task_type' parameters
    # Output: ToolResult with categorized interactive elements
    # Returns: inputs, buttons, links, containers, actions, tabs, lists
```

**Task Types:**
- `search`: Elements for search functionality
- `navigate`: Navigation elements
- `form_fill`: Form input elements
- `extract`: Data extraction elements
- `click_action`: Clickable action elements

### Calculator Tool
**File:** `src/tools/calculator.py`

```python
def execute(self, **parameters) -> ToolResult:
    # Input: Dict with 'expression' parameter
    # Output: ToolResult with calculation result
    # Uses Python's eval() with safety restrictions
```

### API Call Tool
**File:** `src/tools/api_call.py`

```python
def execute(self, **parameters) -> ToolResult:
    # Input: Dict with url, method, params, headers, body
    # Output: ToolResult with API response data
    # Makes HTTP requests with full control
```

### Excel/CSV Export Tools
**File:** `src/tools/excel_export.py`, `src/tools/csv_export.py`

```python
def execute(self, **parameters) -> ToolResult:
    # Input: Dict with data array, filename
    # Output: ToolResult with file path
    # Exports structured data to spreadsheet formats
```

### Analysis Tools (`src/tools/analysis_tools.py`)

#### **Sentiment Analysis Tool:**
```python
class AnalyzeSentimentTool(BaseTool):
    # Uses LLM for sentiment analysis with fallback to basic heuristics
    # Supports detailed breakdown and confidence scores
```

#### **Content Summarization Tool:**
```python
class SummarizeContentTool(BaseTool):
    # LLM-powered content summarization
    # Supports concise, detailed, and bullet-point styles
    # Configurable length limits
```

#### **Data Comparison Tool:**
```python
class CompareDataTool(BaseTool):
    # Compares datasets (JSON, text, lists)
    # Supports differences, similarities, and full analysis
    # Handles nested data structures
```

#### **Data Validation Tool:**
```python
class ValidateDataTool(BaseTool):
    # Validates data quality and format
    # Supports JSON, email, URL, and general validation
    # Returns detailed error reports
```

### API Call Tool (`src/tools/api_call.py`)

#### **Lightweight HTTP Requests:**
```python
class APICallTool(BaseTool):
    # Fast HTTP requests without Playwright overhead
    # Supports GET/POST with query parameters and JSON
    # Includes completeness validation metadata
```

**Completeness Validation:**
```python
def _add_completeness_metadata(self, data, requested_count, requested_fields, task_description):
    # Validates if API response meets requirements
    # Checks field presence and data quality
    # Returns coverage percentage and missing fields
```

### Chunk Reader Tool (`src/tools/chunk_reader.py`)

#### **Content Chunking System:**
```python
class GetNextChunkTool(BaseTool):
    # Reads next chunk of scraped content
    # Integrates with memory service for long content
    # Handles streaming responses
```

**Memory Integration:**
```python
def _execute_impl(self, **kwargs) -> ToolResult:
    chunk_data = self.memory_service.get_next_chunk(self.session_id)
    # Returns formatted chunk with metadata
    # Tracks chunk number and total chunks
```

### Element Parser (`src/tools/element_parser.py`)

#### **Interactive Element Detection:**
```python
class ElementParser:
    # Fast heuristic-based element detection
    # 90%+ success rate without LLM calls
    # Extracts interactive elements (buttons, inputs, links)
```

**Heuristic Matching:**
```python
def find_element(self, elements: List[Dict[str, Any]], action_hint: str) -> Optional[Dict[str, Any]]:
    # Scores elements based on attributes and context
    # Uses keyword matching and semantic analysis
    # Returns best matching element
```

#### **Async Playwright Element Finder:**
```python
async def find_best_element(page: Page, selector_hint: str, tag_filter: Optional[str] = None):
    # Builds smart CSS selectors from hints
    # Ranks elements by position, size, and context
    # Uses LLM fallback for ambiguous cases
```

**Element Ranking Algorithm:**
```python
async def _rank_elements(page, locator, count, hint):
    # Visibility check (+5 points)
    # Position scoring (main content preferred)
    # Size analysis (larger elements preferred)
    # Context evaluation (header penalty, main bonus)
    # Attribute matching (hint keywords in attributes)
```

### Learning Manager (`src/tools/learning_manager.py`)

#### **Tool Performance Tracking:**
```python
class ToolPerformanceTracker:
    # Tracks success/failure rates per tool per site
    # Calculates reliability scores and response times
    # Maintains recent success patterns
```

**Reliability Scoring:**
```python
@property
def reliability_score(self) -> float:
    overall = self.success_rate * 0.3
    recent = self.recent_success_rate * 0.7
    return overall + recent  # Recent success weighted more
```

#### **Intelligent Tool Selection:**
```python
def get_best_tool_for_site(self, url: str, candidate_tools: List[str]) -> Tuple[str, float]:
    # Returns best tool based on historical performance
    # Considers minimum attempts for reliable data
    # Returns confidence score
```

**Fallback Chain Generation:**
```python
def get_fallback_chain(self, url: str, all_tools: List[str]) -> List[str]:
    # Orders tools: best historical performers first
    # Untried tools at end
    # Enables graceful degradation
```

### Universal Extractor (`src/tools/universal_extractor.py`)

#### **Multi-Source Data Extraction:**
```python
class UniversalExtractor:
    # Extracts data from any website structure
    # Uses multiple strategies: schema-based, pattern-based, LLM-assisted
    # Handles pagination and dynamic content
```

**Extraction Strategies:**
1. **Schema-Based**: Uses predefined schemas for known sites
2. **Pattern-Based**: Regex and CSS selector patterns
3. **LLM-Assisted**: Uses AI to identify data patterns
4. **Fallback**: Comprehensive text extraction

### Site Intelligence (`src/tools/site_intelligence.py`)

#### **AI-Powered Site Analysis:**
```python
class SiteIntelligenceTool:
    # Analyzes website structure and functionality
    # Learns element selectors through interaction
    # Builds site-specific automation strategies
```

**Learning Process:**
1. **Page Analysis**: Extracts interactive elements
2. **Action Recording**: Learns successful interactions
3. **Pattern Recognition**: Identifies common workflows
4. **Strategy Building**: Creates automation sequences

### Chart Extractor (`src/tools/chart_extractor.py`)

#### **Visual Data Extraction:**
```python
class PlaywrightChartExtractor:
    # Extracts data from charts, graphs, and visualizations
    # Uses Playwright for JavaScript execution
    # Handles Canvas, SVG, and image-based charts
```

**Chart Types Supported:**
- **Canvas Charts**: JavaScript data extraction
- **SVG Charts**: Direct element parsing
- **Table Charts**: HTML table extraction
- **Image Charts**: OCR fallback (limited)

### Calculator Tool (`src/tools/calculator.py`)

#### **Mathematical Computation:**
```python
class CalculatorTool(BaseTool):
    # Safe mathematical calculations
    # Uses Python eval with restricted environment
    # Supports basic arithmetic and functions
```

**Safety Features:**
- Restricted built-ins (no file operations, imports)
- Timeout protection
- Error handling for invalid expressions
- Result validation

### Tool Registry Integration

#### **Dynamic Tool Loading:**
```python
# tools/__init__.py
TOOL_CATEGORIES = {
    'analysis': [AnalyzeSentimentTool, SummarizeContentTool],
    'extraction': [ContentExtractorTool, InteractiveElementExtractorTool],
    'automation': [UniversalPlaywrightTool, ChartExtractorTool],
    'data_processing': [ExcelExportTool, CalculatorTool],
    'api': [APICallTool],
    'utility': [GetNextChunkTool]
}
```

#### **Tool Capabilities Mapping:**
```python
TOOL_CAPABILITIES = {
    'google_search': ['search', 'web', 'current_info'],
    'playwright_execute': ['browse', 'interact', 'scrape'],
    'content_extractor': ['extract', 'parse', 'clean'],
    'excel_export': ['export', 'format', 'save'],
    'calculator': ['compute', 'math', 'calculate']
}
```

### Tool Execution Pipeline

#### **Complete Tool Flow:**
```
User Request → Tool Selection (Router)
    ↓
Tool Instantiation (Registry)
    ↓
Parameter Resolution (DataFlowResolver)
    ↓
Tool Execution (BaseTool._execute_impl)
    ↓
Result Validation (Completeness Check)
    ↓
Performance Recording (LearningManager)
    ↓
Response Formatting (ToolResult)
```

#### **Error Recovery Chain:**
```
Tool Failure → Retry Logic (Tool-specific)
    ↓
Alternative Tool (Router.suggest_alternative)
    ↓
Parameter Re-resolution (DataFlowResolver)
    ↓
Fallback Strategy (Tool-specific fallbacks)
    ↓
LLM-Assisted Recovery (If available)
```

#### **Learning Integration:**
```
Every Tool Execution → LearningManager.record_tool_execution()
    ↓
Performance Metrics Updated
    ↓
Future Selections Improved
    ↓
Site-Specific Optimization
```

This comprehensive tool system provides the complete execution capabilities for the agent, with intelligent selection, learning, and error recovery mechanisms.

## Core Infrastructure Components

### Configuration System (`src/core/config.py`)
**Purpose:** Centralized environment variable management with Pydantic validation.

**Key Features:**
```python
class Settings(BaseSettings):
    # API Keys
    GEMINI_API_KEY: str
    serper_api_key: str
    browserless_api_key: Optional[str] = None

    # LLM Settings
    llm_model: str = "gemini-2.5-flash"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 8192

    # Server Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    logging_url: str = get_frontend_url()  # Auto-detects environment

def get_frontend_url() -> str:
    # Auto-detects frontend URL based on environment
    # Docker → host.docker.internal, Production → env var, Local → localhost
```

### Memory Service (`src/core/memory.py`)
**Purpose:** LangGraph-based conversation persistence using SQLite checkpoints.

**Key Components:**
```python
class MemoryService:
    def __init__(self, db_path: Optional[str] = None):
        # Initializes SqliteSaver for LangGraph checkpoints
        # Creates content_chunks table for chunked content storage

    def get_checkpointer(self) -> SqliteSaver:
        # Returns LangGraph checkpointer for agent workflows

    def get_session_config(self, session_id: str) -> Dict[str, Any]:
        # Returns config dict: {"configurable": {"thread_id": session_id}}

    def store_content_chunks(self, session_id: str, chunks: List[str]) -> bool:
        # Stores content chunks for long-form content handling

    def get_next_chunk(self, session_id: str) -> Optional[Dict[str, Any]]:
        # Retrieves next unread chunk for streaming responses
```

**Features:**
- **LangGraph Integration**: Uses SqliteSaver for conversation persistence
- **Chunk Storage**: Handles long content with chunked retrieval
- **Session Isolation**: Each session has isolated conversation memory

### Graph Workflow (`src/core/graph.py`)
**Purpose:** LangGraph workflow definition for agent reasoning loops.

**Key Functions:**
```python
def create_workflow(tools, model_with_tools, checkpointer, logger_callback) -> CompiledGraph:
    # Creates LangGraph workflow with agent → tools → agent loop
    # Includes conditional edges based on tool calls

def should_continue(state: MessagesState) -> str:
    # Decides whether to continue to tools or end workflow
    # Checks if last message has tool_calls

def call_model(state: MessagesState) -> Dict[str, Any]:
    # Agent node: invokes LLM to decide next action
    # Returns AIMessage with or without tool_calls
```

**Workflow Structure:**
```
Entry: agent
├── agent → should_continue()
│   ├── "continue" → tools
│   └── "end" → END
└── tools → agent (loop back)
```

### Agent Manager (`src/core/agent.py`)
**Purpose:** High-level agent lifecycle management with dependency injection.

**Two Manager Types:**

#### AgentManager (Classic)
```python
class AgentManager:
    def __init__(self, llm_service, memory_service, logging_service, tools):
        # Single-agent execution with LangGraph workflow
        # No intelligent routing or multi-agent coordination

    def execute_task(self, prompt, message_id, session_id) -> str:
        # Executes single workflow with tools
        # Streams results and saves to session
```

#### MultiAgentManager (Advanced)
```python
class MultiAgentManager(AgentManager):
    def __init__(self, llm_service, memory_service, logging_service, tools, enable_routing, routing_strategy):
        # Extends AgentManager with intelligent tool routing
        # Includes ReasonAgent + ExecutorAgent coordination

    def execute_task_multi_agent(self, prompt, message_id, session_id, use_reason_agent) -> str:
        # Routes to ReasonAgent for planning or direct ExecutorAgent execution
        # Uses ToolRouter for intelligent tool selection
        # Loads conversation history for context-aware responses
```

**Key Features:**
- **Dependency Injection**: Clean separation of concerns
- **Multi-Agent Coordination**: ReasonAgent plans, ExecutorAgent executes
- **Intelligent Routing**: ToolRouter selects optimal tools based on metadata
- **Session Persistence**: Automatic message saving to database

## Data Flow Components

### DataFlowResolver (`src/core/data_flow_resolver.py`)
**Purpose:** ZERO-hardcoding automatic parameter resolution using tool I/O schemas.

**Core Architecture:**
```python
class DataFlowResolver:
    def __init__(self, schema_file: str = "tool_io_schema.json"):
        # Loads declarative schemas for all tools
        # Maps tool outputs to tool inputs automatically

    def resolve_inputs(self, tool_name, provided_params, accumulated_data, subtask_context) -> Dict[str, Any]:
        # Resolves missing required inputs from previous tool outputs
        # Uses accepts_from patterns like "google_search.urls[0]"

    def extract_outputs(self, tool_name, raw_result) -> Dict[str, Any]:
        # Extracts structured outputs using schema-defined extractors
        # Supports dynamic fields and preserves raw data
```

**Resolution Strategies:**

#### 1. Schema-Based Resolution
```json
{
  "playwright_execute": {
    "inputs": {
      "url": {
        "accepts_from": ["google_search.urls[0]"],
        "required": true
      }
    }
  }
}
```

#### 2. Template Resolution
```python
# Supports {{variable.field}} and {{variable.field[0]}} syntax
def _resolve_template(self, template: str, accumulated_data) -> Any:
    # Parses template expressions and navigates accumulated data
    # Handles nested field access and array indexing
```

#### 3. Dynamic Field Support
```python
def extract_outputs(self, tool_name, raw_result) -> Dict[str, Any]:
    # Extracts schema-defined fields + preserves dynamic fields
    # Zero data loss while providing structured access
    # metadata.get("supports_dynamic_outputs", True)  # Default: True!
```

**Critical Issue - Flight Search Failure:**
```
google_search returns: "Search results text with URLs..."
DataFlowResolver tries: extract_urls_from_text("text...")
❌ Regex extraction fails → url: None → playwright_execute.goto(None)
```

### Data Extractors (`src/core/data_extractors.py`)
**Purpose:** Pure functions for extracting structured data from raw tool outputs.

**Available Extractors:**
```python
EXTRACTORS = {
    "identity": identity,                                    # Return as-is
    "extract_urls_from_text": extract_urls_from_text,       # Regex URL extraction
    "extract_snippets_from_text": extract_snippets_from_text, # Text snippets
    "count_records": count_records,                         # Count list items
    "extract_field_names": extract_field_names,             # Get dict keys
    "get_current_url": get_current_url,                     # Extract URL from data
    "extract_text_from_html": extract_text_from_html,       # HTML → plain text
    "extract_links_from_html": extract_links_from_html,     # Extract all links
    "extract_status_code": extract_status_code,             # HTTP status
    "extract_response_headers": extract_response_headers,   # Response headers
    "extract_file_path": extract_file_path,                 # File path extraction
}
```

**Key Features:**
- **Pure Functions**: No side effects, stateless
- **Zero Dependencies**: Work with any tool output format
- **Composable**: Can be chained for complex extractions

## Routing System - Intelligent Tool Selection & Management

### Overview
The routing system provides intelligent tool selection, source management, and result validation with self-learning capabilities.

### Tool Registry System (`src/routing/tool_registry.py`)

#### **ToolMetadata Architecture:**
```python
@dataclass
class ToolMetadata:
    name: str
    description: str
    capabilities: Set[str] = field(default_factory=set)
    category: ToolCategory = ToolCategory.OTHER
    cost: CostLevel = CostLevel.FREE
    avg_latency: float = 0.0
    reliability: float = 100.0
    max_concurrent: int = 1
    requires_auth: bool = False
    rate_limit: Optional[int] = None
    tags: Set[str] = field(default_factory=set)
    version: str = "1.0.0"
    enabled: bool = True
```

#### **Tool Categories:**
- `SEARCH`: google_search, web scraping
- `SCRAPING`: playwright_execute, content_extractor
- `DATA_PROCESSING`: chart_extractor, excel_export
- `CALCULATION`: calculator
- `API`: api_call
- `FILE_OPERATION`: excel_export, csv_export

#### **Cost Levels:**
- `FREE`: No cost (google_search, calculator)
- `LOW`: Minimal cost (basic API calls)
- `MEDIUM`: Moderate cost (premium APIs)
- `HIGH`: High cost (advanced services)
- `PREMIUM`: Enterprise services

#### **Tool Registry Features:**
- **Capability Indexing**: O(1) lookup by capability
- **Category Indexing**: Group tools by function
- **Statistics Tracking**: Usage, success rate, latency
- **Dynamic Updates**: Real-time performance metrics

### Tool Router (`src/routing/tool_router.py`)

#### **Routing Strategies:**
```python
class RoutingStrategy(Enum):
    CAPABILITY = "capability"        # Match by capability only
    BEST_PERFORMANCE = "best_performance"  # Optimize for speed/reliability
    LOWEST_COST = "lowest_cost"      # Minimize cost
    BALANCED = "balanced"           # Balance all factors
    ROUND_ROBIN = "round_robin"     # Distribute load evenly
    LEAST_USED = "least_used"       # Use least utilized tool
```

#### **Intelligent Selection Algorithm:**
```python
def _calculate_score(self, tool: ToolMetadata) -> float:
    """Calculate balanced score for a tool."""
    cost_score = {
        CostLevel.FREE: 1.0,
        CostLevel.LOW: 0.8,
        CostLevel.MEDIUM: 0.6,
        CostLevel.HIGH: 0.4,
        CostLevel.PREMIUM: 0.2
    }[tool.cost]
    
    reliability_score = tool.reliability / 100.0
    latency_score = max(0, 1.0 - (tool.avg_latency / 10.0))
    
    return (
        reliability_score * 0.5 +
        latency_score * 0.3 +
        cost_score * 0.2
    )
```

#### **Routing with Fallbacks:**
```python
def route_with_fallback(
    self,
    task: AgentTask,
    max_options: int = 3,
    strategy: RoutingStrategy = None,
    constraints: Dict[str, Any] = None
) -> List[ToolMetadata]:
    # Returns prioritized list of tools with fallbacks
    # Handles failures gracefully with alternatives
```

### Dynamic Source Registry (`src/routing/source_registry.py`)

#### **Self-Learning Architecture:**
- **Category Normalization**: Converts queries to canonical categories
- **Alias Learning**: Learns new query patterns from user input
- **Keyword Discovery**: Extracts keywords from successful extractions
- **Reliability Tracking**: Updates source success rates
- **Automatic Deduplication**: Prevents duplicate sources

#### **Category Management:**
```python
def normalize_category(self, user_query: str) -> str:
    """Convert user query to canonical category."""
    # Examples:
    # "top songs" → "music_charts"
    # "best books" → "books"
    # "flight prices" → "travel"
```

#### **Learning from Success:**
```python
def process_successful_extraction(
    self,
    user_query: str,
    category: str,
    domain: str,
    url: str,
    extracted_fields: List[str]
):
    # 1. Learn alias from query
    # 2. Learn keywords from fields
    # 3. Update source fields
    # 4. Update reliability score
```

### Selector Map (`src/routing/selector_map.py`)

#### **Site-Based Caching Architecture:**
- **Domain Isolation**: Separate cache files per website
- **Lazy Loading**: Load only needed site caches
- **O(1) Lookups**: Direct selector retrieval
- **Automatic Promotion**: Learn from successful interactions
- **Tree-Based Navigation**: Track page relationships

#### **Selector Learning Process:**
```python
def promote_selector(
    self,
    url: str,
    tool: str,
    hint: str,
    selector: str,
    success: bool = True,
    response_time: float = None
):
    # Criteria for promotion to "best":
    # - >= 3 successes
    # - >90% success rate
    # - Fastest response time (if tie)
```

#### **Page Tree Structure:**
```python
# domain.json structure:
{
  "pages": {
    "/": {
      "url": "https://example.com",
      "interactive_elements": [...],
      "action_map": {"search_input": "#search"},
      "children": ["/search", "/products"]
    }
  }
}
```

### Result Validator (`src/routing/result_validator.py`)

#### **Validation Pipeline:**
1. **Completeness Check**: Required fields present
2. **Quality Assessment**: Non-empty, consistent data
3. **Confidence Scoring**: Weighted metrics
4. **Suggestion Generation**: Next steps for missing data

#### **Completeness Evaluation:**
```python
def validate(
    self,
    results: List[Dict[str, Any]],
    required_fields: List[str]
) -> Dict[str, Any]:
    # Returns:
    # - valid: bool
    # - complete: bool
    # - coverage: float (0.0-1.0)
    # - confidence: float (0.0-1.0)
    # - suggested_actions: List[Dict]
```

#### **Smart Suggestions:**
```python
def suggest_next_steps(
    self,
    missing_fields: List[str],
    context: Dict[str, Any]
) -> List[Dict[str, Any]]:
    # Examples:
    # Missing "price" → click_through to detail page
    # Missing "phone" → navigate to contact page
    # Missing "description" → extract from metadata
```

### Task Decomposer (`src/routing/task_decomposer.py`)

#### **LLM-Powered Decomposition:**
```python
def decompose_task(self, user_query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    # Input: Natural language query
    # Output: Structured subtask array
    # Uses LLM with JSON schema validation
```

#### **Recursive JSON Parsing:**
```python
def _parse_json_response(self, response: str) -> Dict[str, Any]:
    # Handles malformed JSON from LLM
    # Multiple parsing strategies:
    # 1. Direct JSON.parse()
    # 2. Extract JSON from markdown
    # 3. Fix common JSON errors
    # 4. Recursive cleanup
```

**LLM Schema:**
```json
{
  "type": "object",
  "properties": {
    "subtasks": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "tool": {"type": "string"},
          "parameters": {"type": "object"},
          "description": {"type": "string"}
        }
      }
    }
  }
}
```

### Tool Capabilities (`src/routing/tool_capabilities.py`)

#### **Dynamic Registry Loading:**
```python
def load_tool_registry() -> Dict[str, Dict[str, Any]]:
    """Load from generated tool_registry.json"""
    # Filters disabled tools
    # Returns enabled tools only
```

#### **LLM-Optimized Formatting:**
```python
def format_registry_for_llm() -> str:
    """Format registry for LLM consumption."""
    # Returns clean markdown with:
    # - Tool descriptions
    # - Capabilities
    # - Parameters
    # - Examples
```

### Routing System Integration

#### **Complete Tool Selection Flow:**
```
User Query → TaskDecomposer (LLM breakdown)
    ↓
Subtasks → ToolRouter (strategy-based selection)
    ↓
ToolMetadata → Tool Execution
    ↓
ToolResult → ResultValidator (quality check)
    ↓
Validation Results → DynamicSourceRegistry (learning)
    ↓
SelectorMap (cache successful selectors)
```

#### **Self-Learning Cycle:**
```
1. ToolRouter selects tool based on strategy
2. Tool executes with parameters
3. ResultValidator checks completeness
4. DynamicSourceRegistry learns from success
5. SelectorMap caches successful selectors
6. ToolRegistry updates performance metrics
7. Next request uses improved selection
```

#### **Fallback Hierarchy:**
```
Primary Tool Failure → ToolRouter.suggest_alternative()
    ↓
Different tool with same capability
    ↓
ResultValidator.suggest_next_steps()
    ↓
Click-through or navigation actions
    ↓
Dynamic replanning with LLM
```

This routing system provides intelligent, self-improving tool selection with comprehensive learning and fallback mechanisms.

## Workflow States

### Agent Manager Workflow
**File:** `src/core/agent.py`

1. **Task Reception**: `execute_task(prompt, message_id, session_id)`
2. **Workflow Creation**: Initialize LangGraph workflow with tools
3. **Streaming Execution**: Stream workflow steps with logging
4. **Result Extraction**: Extract final answer from workflow output
5. **Session Persistence**: Save messages to session database

### Multi-Agent Execution Flow
**File:** `src/core/agent.py` (MultiAgentManager)

1. **Task Analysis**: ReasonAgent analyzes task and creates plan
2. **Subtask Execution**: ExecutionEngine executes subtasks sequentially/adaptively
3. **Result Processing**: ResultProcessor synthesizes final answer
4. **Session Updates**: Save conversation to database

### Adaptive Execution States
**File:** `src/agents/execution_engine.py`

1. **Navigation**: Initial browser navigation
2. **Observation**: Extract page content/state
3. **Planning**: LLM plans next interaction based on current state
4. **Interaction**: Execute planned action (fill, click, etc.)
5. **Validation**: Check if goal achieved
6. **Iteration**: Repeat until goal achieved or max iterations reached

## LLM Prompt System & Call Patterns

### Prompt Architecture Overview

The system uses a hierarchical prompt system with specialized prompts for different agent roles:

#### **System Prompt (`src/prompts/system_prompt.py`)**
**Purpose:** Core agent identity and behavior guidelines

```python
SYSTEM_PROMPT = """
You are KaryaKarta, a highly capable AI agent designed to help users with various tasks.

Your capabilities include:
- Searching the web for current information using Google
- Browsing websites to extract detailed information
- Performing mathematical calculations
- Extracting and parsing data from various formats
- Analyzing and synthesizing information from multiple sources

IMPORTANT - Tool Usage Guidelines:
1. Before calling any tool, ensure you use the correct parameter names and types
2. Each tool has specific parameters - check the tool's schema if unsure
3. If a tool call fails with a parameter error:
   - Read the error message carefully
   - Check the tool's parameter requirements
   - Retry with correct parameters
   - Or use list_available_tools() to see all tool schemas

CRITICAL: After using any tool to gather information, you MUST:
- Analyze the tool's results carefully
- Formulate a clear, comprehensive, and helpful response based on those results
- ALWAYS provide a response with actual content - never return empty responses
"""
```

**Key Features:**
- **Tool Error Recovery:** Specific guidance for handling parameter errors
- **Response Requirements:** Mandatory synthesis after tool usage
- **Conversation Context:** Awareness of multi-turn conversations

#### **Reason Agent Prompt (`src/prompts/reason_agent_prompt.py`)**
**Purpose:** Planning and coordination for complex multi-step tasks

**Core Responsibilities:**
1. **Task Analysis:** Break down complex requests into components
2. **Tool Selection:** Match requirements to available capabilities
3. **Execution Planning:** Create ordered subtask sequences
4. **Coordination:** Delegate to executor agents and synthesize results

**Key Guidelines:**
```python
# Multi-step planning emphasis
✓ Break complex tasks into manageable subtasks
✓ Consider dependencies (Task B needs Task A's results)
✓ Choose most efficient tools for each subtask
✓ Use chart_extractor for lists/tables, playwright_execute for interactions
✓ Plan for potential failures with fallbacks
✓ Synthesize results into unified answers

# Iterative tool usage (CRITICAL)
✓ Use same tool multiple times if needed for complete results
✓ If first search finds 7/10 items, search again with different query
✓ Compare results from multiple sources
```

**Conversation Awareness:**
```python
# Multi-turn conversation handling
✓ ALWAYS check conversation_history before planning
✓ Reference earlier findings: "Based on the data I found earlier..."
✓ Don't repeat work if data exists in history
✓ Build upon previous_results for follow-up requests
```

#### **Executor Agent Prompt (`src/prompts/executor_agent_prompt.py`)**
**Purpose:** Precise tool execution with error handling and result formatting

**Execution Methodology:**
1. **Parameter Extraction:** Parse and validate task parameters
2. **Pre-execution Validation:** Verify tool availability and parameter completeness
3. **Execution:** Call tool with exact parameters and monitor progress
4. **Error Handling:** Classify errors and implement retry strategies
5. **Result Formatting:** Structure results consistently with metadata
6. **Completeness Evaluation:** Assess if task requirements were fully met

**Error Classification:**
```python
# Transient errors (retry appropriate)
TRANSIENT ERRORS:
- Network timeouts
- Temporary service unavailable
- Rate limit exceeded (with backoff)
- Connection errors
→ Retry with exponential backoff

# Permanent errors (don't retry)
PERMANENT ERRORS:
- Invalid parameters
- Missing required fields
- Type mismatches
- Permission denied
- Tool not found
→ Return error immediately
```

**Completeness Evaluation:**
```python
# Task completeness assessment
Task is INCOMPLETE if:
- Requested N items but found < N (e.g., "top 10" but only 7 found)
- Missing required fields (e.g., asked for "price and specs" but no price)
- Result is too brief for a search query (< 50 chars)
- Data quality is poor or minimal

Examples:
1. Request: "Find top 10 songs" → Found: 7 songs
   → complete: false, reason: "Found 7/10 items", coverage: "70%"

2. Request: "Get product with price" → Found: Product info but no price
   → complete: false, reason: "Missing required field: price"
```

### LLM Call Patterns

#### **1. Task Analysis (ReasonAgent)**
**Input Schema:**
```json
{
  "task_type": "string",
  "query_params": "object",
  "required_tools": "array",
  "required_fields": "array",
  "task_structure": {
    "type": "string",
    "steps": "array"
  }
}
```

**Prompt Structure:**
- System: Task analysis instructions
- User: Task description + context
- Output: Structured task analysis

#### **2. Subtask Decomposition (ReasonAgent)**
**Input Schema:**
```json
{
  "subtasks": [
    {
      "tool": "string",
      "parameters": "object",
      "description": "string"
    }
  ]
}
```

**Prompt Structure:**
- System: Decomposition instructions
- User: Task analysis + requirements
- Output: Executable subtask array

#### **3. Comprehensive Task Analysis (TaskAnalyzer)**
**Single LLM Call Approach:**
```python
def _analyze_task_comprehensive(self, task_description: str) -> Optional[Dict[str, Any]]:
    # Uses Gemini 2.5 structured output for reliable JSON
    # Returns complete analysis in one call (vs 4 separate calls)
    # Includes task_type, required_tools, task_structure, query_params, required_fields
```

**Advantages:**
- **Consistency:** Single schema for all task analysis
- **Reliability:** Structured output validation
- **Efficiency:** One LLM call instead of multiple
- **Completeness:** All analysis aspects in one response

#### **4. Result Synthesis (ResultProcessor)**
**Input:** Free-form prompt with results
**Output:** Natural language answer
**Context:** Previous structured memory

#### **5. Adaptive Planning (ExecutionEngine)**
**Input Schema:** Next step planning
**Output:** Single next subtask
**Context:** Current state + accumulated data

#### **6. Element Discovery (AdaptiveElementMatcher)**
**AI-Powered Element Finding:**
```python
async def _ai_element_discovery(self, page: Page, intent: str, url: str, context_hints) -> Optional[Dict[str, Any]]:
    # Uses LLM to analyze page context and identify selectors
    # Builds detailed prompts with page analysis
    # Tests LLM suggestions for visibility and functionality
```

**Prompt Engineering:**
- Page context extraction (title, visible text, interactive elements)
- Intent-to-selector mapping with confidence scores
- Fallback selector generation
- Reasoning explanation for matches

### Prompt Template System

#### **Template Functions:**
```python
# System prompt with context
get_system_prompt_with_context(context: str) → str

# Reason agent with tools and context
get_reason_agent_prompt(available_tools: list) → str
get_reason_agent_prompt_with_context(available_tools: list, context: str) → str

# Executor agent with tool info
get_executor_agent_prompt(tool_name: str, tool_description: str) → str
get_executor_agent_general_prompt() → str
get_executor_agent_prompt_with_context(tool_name: str, tool_description: str, context: str) → str
```

#### **Context Integration:**
- **Conversation History:** Previous messages for continuity
- **Previous Results:** Earlier task outputs for follow-ups
- **Tool Information:** Available tools and their capabilities
- **Session Context:** Current session state and metadata

### Prompt Evolution Strategy

#### **Current Issues:**
- **Inconsistent Schemas:** Different LLM calls use different output formats
- **Multiple Calls:** Some analyses require 2-4 separate LLM calls
- **Error Recovery:** Limited structured error handling in prompts

#### **Future Improvements:**
- **Unified Schema:** Single LLM schema for all agent interactions
- **Structured Outputs:** All prompts use JSON schema validation
- **Context Awareness:** Better integration of conversation history
- **Error Recovery:** Structured error classification and recovery prompts

## Data Flow Between Components

### User Query → Agent System
```
User Query (string)
    ↓
TaskRequest (validated pydantic model)
    ↓
AgentManager.execute_task()
    ↓
MultiAgentManager.execute_task_multi_agent()
    ↓
ReasonAgent.execute() → AgentResult with plan
    ↓
ExecutionEngine.execute_plan() → List[execution results]
    ↓
ResultProcessor.synthesize_results() → final answer
    ↓
TaskResponse (to frontend)
```

### Parameter Resolution Flow
```
Subtask Parameters (with placeholders)
    ↓
DataFlowResolver.resolve_inputs()
    ↓
Extract from accumulated_data using schema patterns
    ↓
Merge resolved + provided parameters
    ↓
Tool.execute(resolved_parameters)
```

### Session Persistence Flow
```
AgentMessage (thinking/status/response)
    ↓
LoggingService.send_*()
    ↓
WebSocket to frontend
    ↓
SessionService.add_message_to_session()
    ↓
Database storage (conversations.db)
```

## Error Handling & Recovery

### Tool Execution Errors
- **Classification**: `selector_not_found`, `timeout`, `network`, `validation`
- **Recovery**: Automatic retry for recoverable errors
- **Replanning**: Trigger new plan generation for persistent failures

### Data Flow Errors
- **Missing Dependencies**: Fallback to provided parameters
- **Extraction Failures**: Continue with raw data
- **Schema Mismatches**: Log warnings, use defaults

### LLM Response Errors
- **Invalid JSON**: Recursive parsing attempts
- **Empty Responses**: Fallback to simple formatting
- **Token Limits**: Truncate inputs, use summaries

## Performance & Monitoring

### Metrics Tracked
- **Agent Metrics**: Tasks completed/failed, execution time
- **Tool Metrics**: Success rate, usage count, latency
- **Session Metrics**: Message count, conversation length
- **LLM Metrics**: Token usage, response times

### Logging Levels
- **Status**: Progress updates, normal operations
- **Thinking**: Agent reasoning, planning steps
- **Error**: Failures, exceptions, warnings
- **Response**: Final answers to user

## Configuration & Settings

### LLM Configuration
```python
# src/core/config.py
class Settings:
    llm_model: str = "gemini-1.5-flash"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 8192
    gemini_api_key: str
```

### Tool Registry
**File:** `tool_registry.json`
- Tool capabilities and metadata
- Cost levels and latency estimates
- Reliability scores and categories

### Schema Definitions
**File:** `tool_io_schema.json`
- Input/output schemas for all tools
- Parameter validation rules
- Data flow dependency mappings

## Dependencies & Libraries

### Core Dependencies (`requirements.txt`)
```txt
# Web Framework
fastapi==0.120.0          # Async web framework
uvicorn==0.38.0           # ASGI server
slowapi==0.1.9           # Rate limiting

# AI & LangChain
langchain==1.0.2          # LLM framework
langchain-google-genai==3.0.0  # Gemini integration
langgraph==1.0.1         # Agent workflows
chromadb==0.4.24         # Vector database

# Browser Automation
playwright==1.44.0        # Browser control

# Data Processing
pandas==2.1.4            # Data manipulation
openpyxl==3.1.2          # Excel support
lxml==5.1.0              # XML/HTML parsing
beautifulsoup4==4.12.3   # HTML parsing
selectolax==0.3.27       # Fast HTML parser

# Utilities
pydantic==2.10.3         # Data validation
python-dotenv==1.1.1     # Environment variables
requests==2.32.5         # HTTP client
tenacity==8.2.3          # Retry logic
cachetools==5.3.2        # Caching
```

### Key Architecture Insights

#### 1. **Data Flow Bottlenecks**
- **Google Search → Playwright Navigation**: String output extraction fails
- **LLM Schema Inconsistency**: Different tools use different output formats
- **Parameter Resolution Complexity**: Regex-based extraction unreliable

#### 2. **Async Execution Challenges**
- **Playwright Browser Management**: Complex session lifecycle
- **Threading Issues**: asyncio + ThreadPoolExecutor conflicts
- **Resource Cleanup**: Browser instances persist across requests

#### 3. **LLM Integration Patterns**
- **Structured Output**: Gemini 2.5 native JSON schema validation
- **Fallback Handling**: Multiple parsing attempts for malformed JSON
- **Context Management**: Conversation history + structured memory

#### 4. **Error Recovery Mechanisms**
- **Tool Retry Logic**: Exponential backoff with error classification
- **Dynamic Replanning**: LLM generates alternative execution paths
- **Completeness Evaluation**: Assesses result quality for follow-up actions

#### 5. **Session Management Complexity**
- **Multi-Format Storage**: SQLite for persistence, in-memory for speed
- **Context Window Limits**: Memory buffer management with summarization
- **Cross-Session Learning**: Element cache shared across sessions

## Critical System Flows

### Flight Search Failure Analysis
```
User: "search flights NYC to Chicago"
    ↓
ReasonAgent: Creates plan with google_search → playwright_execute
    ↓
google_search: Returns formatted string with URLs
    ↓
DataFlowResolver: Tries regex extraction on string
    ↓
❌ Extraction fails → url: None passed to playwright_execute
    ↓
playwright_execute: goto(None) → Navigation fails
    ↓
ExecutionEngine: Dynamic replanning triggered
    ↓
🔄 Cycle repeats with same failure pattern
```

### Successful Task Flow
```
User Query → TaskRequest validation → AgentManager routing
    ↓
MultiAgentManager → ReasonAgent planning → Execution plan
    ↓
ExecutionEngine → Sequential execution with DataFlowResolver
    ↓
Tool execution → Result evaluation → Completeness assessment
    ↓
ResultProcessor synthesis → LLM answer formatting
    ↓
Session persistence → WebSocket updates → Frontend response
```

### Error Classification & Recovery
```
Tool Failure → Error classification (selector_not_found, timeout, etc.)
    ↓
Recoverable? → Retry with backoff
    ↓
Non-recoverable → Dynamic replanning with LLM
    ↓
New execution plan → Alternative tool selection
    ↓
Success monitoring → Goal achievement validation
```

## Performance Characteristics

### Latency Breakdown
- **LLM Calls**: 2-5 seconds (task analysis, synthesis)
- **Browser Actions**: 1-3 seconds (navigation, interaction)
- **Data Extraction**: 0.5-2 seconds (HTML parsing)
- **Database Operations**: <0.1 seconds (SQLite)

### Memory Usage
- **Per Session**: ~50MB (conversation history, element cache)
- **Browser Instances**: ~100MB each (Playwright)
- **Vector Database**: ~200MB (ChromaDB with embeddings)

### Scalability Limits
- **Concurrent Sessions**: Limited by browser instances
- **LLM Token Limits**: 8192 tokens per request
- **Database Connections**: SQLite single-writer limitation

## Utility System - Data Processing & Compression

### Overview
The utility system provides essential data processing, validation, compression, and helper functions used throughout the agent system.

### Helper Utilities (`src/utils/helpers.py`)

#### **Smart Content Compression:**
```python
def smart_compress(html: str, max_tokens: int = 1500) -> str:
    """
    Universal content compression with exact token control.
    Works for ANY content type with priority-based extraction.
    """
```

**Compression Strategy:**
1. **Remove Bloat**: Scripts, styles, navigation, inline handlers
2. **Find Main Content**: Main, article, or content containers
3. **Priority Extraction**:
   - Headings (structure and topics)
   - Paragraphs (main content)
   - Lists (features, specs)
   - Tables (data, pricing)
4. **Token Truncation**: Exact token limits using tiktoken
5. **Fallback Recovery**: Comprehensive extraction if structured parsing fails

**Performance Impact:**
- **80% Cost Savings**: 1500 tokens vs 8000+ for full page
- **Context Preservation**: Maintains readability and key information
- **Universal Compatibility**: Works with any website structure

#### **Validation & Formatting:**
```python
# URL validation with HTTPS requirement
def validate_url(url: str, require_https: bool = False) -> bool

# Human-readable formatting
def format_file_size(bytes_count: int) -> str  # "1.5 MB"
def format_timestamp(dt: datetime, relative: bool = False) -> str
def format_number(num: int, short: bool = False) -> str  # "1.5M"
```

#### **Retry & Caching:**
```python
# Exponential backoff retry decorator
@retry_on_failure(max_attempts=3, min_wait=1, max_wait=10)
def fetch_data():
    return requests.get(url)

# TTL caches for API responses and search results
_api_cache = TTLCache(maxsize=100, ttl=300)  # 5 minutes
_search_cache = TTLCache(maxsize=50, ttl=600)  # 10 minutes
```

### Data Merger (`src/utils/data_merger.py`)

#### **Multi-Source Data Merging:**
```python
def merge_data(sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merge data from multiple sources into single record.
    First non-empty value wins for each field.
    """
```

**Merging Strategies:**
- **Simple Merge**: Combine fields from multiple sources
- **List Merge**: Match records by ID across sources
- **Confidence-Based**: Use highest confidence values
- **Priority Ordering**: Respect source priority rankings

#### **Completeness Validation:**
```python
def check_field_completeness(data: Dict[str, Any], required_fields: List[str]) -> Dict[str, Any]:
    """
    Returns: {
        "complete": bool,
        "missing": List[str],
        "coverage": float (0-100%)
    }
    """
```

### Schema Builder (`src/utils/schema_builder.py`)

#### **Automatic JSON Schema Generation:**
```python
class SchemaBuilder:
    """
    Builds JSON schemas from extracted data automatically.
    Zero hardcoding - adapts to any data structure.
    """
```

**Schema Generation Process:**
1. **Type Inference**: Analyze sample records to infer field types
2. **Required Field Detection**: Fields present in >80% of records
3. **Example Collection**: Up to 3 examples per field
4. **Constraint Addition**: Min/max for numbers, formats for strings

#### **Schema Validation:**
```python
def validate_record(record: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns: {
        "valid": bool,
        "errors": List[str],
        "warnings": List[str]
    }
    """
```

### Utility System Integration

#### **Content Processing Pipeline:**
```
Raw HTML → smart_compress() → Compressed Text (1500 tokens)
    ↓
Compressed Text → chunk_content() → List[chunks]
    ↓
Chunks → LLM Processing → Structured Data
    ↓
Structured Data → merge_data() → Unified Record
    ↓
Unified Record → SchemaBuilder → JSON Schema
```

#### **Data Quality Assurance:**
```
Extracted Data → check_field_completeness() → Completeness Report
    ↓
Completeness Report → ResultValidator → Validation Results
    ↓
Validation Results → DynamicSourceRegistry → Learning Update
```

#### **Caching Strategy:**
```
API Calls → TTLCache (5 min) → Cached Responses
    ↓
Search Results → TTLCache (10 min) → Cached Queries
    ↓
Selector Maps → File Cache → Persistent Selectors
```

### Utility System Performance

#### **Compression Benchmarks:**
- **Input**: 200KB HTML page
- **Output**: 1500 tokens (~6KB text)
- **Compression Ratio**: 97% reduction
- **Processing Time**: <100ms
- **Context Retention**: 95% of key information preserved

#### **Memory Usage:**
- **TTLCache**: 50-100MB for API/search caching
- **Schema Cache**: <1MB for generated schemas
- **Content Chunks**: Variable based on chunk_size parameter

#### **Error Handling:**
- **Compression Fallbacks**: Multiple extraction strategies
- **Validation Recovery**: Graceful handling of malformed data
- **Cache Failures**: Continue without caching if unavailable

This utility system provides the essential data processing capabilities that enable the agent system to handle complex web content efficiently and reliably.

## System Architecture Summary

### Complete Component Hierarchy

#### **Entry Points:**
- **FastAPI Server** (`main.py`) - HTTP API endpoints
- **Agent Logic** (`agent_logic.py`) - Execution mode management
- **Frontend Integration** - WebSocket streaming and session management

#### **Core Processing:**
- **MultiAgentManager** - Intelligent routing between ReasonAgent/ExecutorAgent
- **ReasonAgent** - Task planning and decomposition
- **ExecutorAgent** - Tool execution with retry logic
- **ExecutionEngine** - Orchestration with data flow resolution
- **ResultProcessor** - Answer synthesis and formatting

#### **Data Flow:**
- **DataFlowResolver** - ZERO-hardcoding parameter resolution
- **ToolResult** - Standardized tool outputs (critical issue source)
- **TaskDecomposer** - LLM-powered task breakdown
- **ResultValidator** - Completeness evaluation and suggestions

#### **Intelligent Routing:**
- **ToolRouter** - Strategy-based tool selection
- **ToolRegistry** - Metadata management and performance tracking
- **DynamicSourceRegistry** - Self-learning category management
- **SelectorMap** - Site-based caching with automatic learning

#### **Content Processing:**
- **smart_compress()** - Universal content compression (80% cost savings)
- **Data Merger** - Multi-source data integration
- **Schema Builder** - Automatic JSON schema generation
- **Validation Helpers** - URL, email, formatting utilities

#### **LLM Integration:**
- **System Prompts** - Core agent behavior guidelines
- **Reason Agent Prompts** - Planning and coordination
- **Executor Agent Prompts** - Precise tool execution
- **LLM Service** - Gemini integration with structured outputs

### Critical Architecture Issues Identified

#### **1. ToolResult Type Inconsistency (PRIMARY ISSUE)**
**Problem:** `data: Optional[Any] = None` allows any type, no validation
**Impact:** DataFlowResolver can't predict or validate output formats
**Result:** Parameter resolution fails → tools get `None` values

#### **2. DataFlowResolver Regex Limitations**
**Problem:** Complex HTML/formatted text breaks simple URL extraction
**Impact:** Google search results can't be parsed reliably
**Result:** `url: None` passed to playwright_execute

#### **3. LLM Schema Inconsistency**
**Problem:** Different LLM calls use different output formats
**Impact:** Complex integration, error-prone parsing
**Result:** Multiple parsing attempts, unreliable responses

#### **4. Parameter Resolution Complexity**
**Problem:** Multiple resolution strategies (schema, template, regex)
**Impact:** Unreliable parameter passing between tools
**Result:** Tool execution failures cascade through the system

### Performance Characteristics

#### **Latency Breakdown:**
- **LLM Calls**: 2-5s (task analysis, synthesis, element discovery)
- **Browser Actions**: 1-3s (navigation, interaction, extraction)
- **Data Processing**: 0.5-2s (HTML parsing, regex extraction)
- **Database**: <0.1s (SQLite operations)
- **API Overhead**: <0.5s (FastAPI, validation)

#### **Memory Usage:**
- **Per Session**: 10-50MB (conversation + element cache)
- **Browser Instances**: 80-150MB each (Playwright + DOM)
- **Vector Database**: 200MB (ChromaDB embeddings)

#### **Scalability Limits:**
- **Concurrent Sessions**: Limited by browser instances (~3-5 max)
- **LLM Token Limits**: 8192 tokens per request
- **Database**: SQLite single-writer limitation

### System Data Flow

#### **User Query → Final Response:**
```
User Input → TaskRequest validation → API routes
    ↓
AgentManager.execute_task() → MultiAgentManager coordination
    ↓
ReasonAgent planning (LLM analysis) → Execution plan
    ↓
ExecutionEngine orchestration → DataFlowResolver parameter resolution
    ↓
Tool execution → ToolResult (inconsistent formats) → Extraction failures
    ↓
ResultProcessor synthesis → LLM answer formatting
    ↓
Session persistence → WebSocket updates → Frontend response
```

#### **Parameter Resolution Failures:**
```
Subtask parameters (with placeholders) → DataFlowResolver.resolve_inputs()
    ↓
Schema matching: accepts_from patterns → Template resolution: {{variable.field}}
    ↓
Accumulated data search → Extractor functions → Resolved parameters
    ↓
❌ Regex extraction fails → url: None → Tool execution fails
```

## 🔍 **CRITICAL DISCOVERY: "Dead Code" Analysis & Solutions**

### **🎯 Unused Helpful Code Found (Can Fix Data Flow Issues)**

Code analysis revealed **7 key pieces of unused code** that contain the exact solutions needed:

#### **1. RESULT_VALIDATOR** → `agents/result_processor.py`
**Purpose:** Validates extraction results and suggests next steps for missing data
**Files:** `agents/result_processor.py`, `tools/chart_extractor.py`, `tools/chart_extractor_tool.py`

**Key Functions:**
```python
def validate(results, required_fields, context) -> Dict[str, Any]:
    # Returns: valid, complete, coverage, confidence, suggested_actions
```

**Solution:** Add completeness validation before data processing to prevent `None` values from propagating.

#### **2. CHECK_COMPLETENESS** → `routing/task_decomposer.py`
**Purpose:** Checks if extracted data meets requirements
**Files:** `routing/task_decomposer.py`

**Solution:** Validate data quality before passing to DataFlowResolver.

#### **3. STRUCTURED_OUTPUT** → `services/llm_service.py`
**Purpose:** Consistent LLM responses with JSON schema validation
**Files:** `services/llm_service.py`

**Key Functions:**
```python
def invoke_with_schema(prompt, schema, schema_name) -> Any:
    # Returns validated JSON matching schema
```

**Solution:** Replace inconsistent LLM parsing with structured output validation.

#### **4. LEARNING_MANAGER** → `tools/learning_manager.py`
**Purpose:** Tool performance tracking and intelligent selection
**Files:** `tools/learning_manager.py`, `tools/chart_extractor.py`, `tools/chart_extractor_tool.py`

**Key Functions:**
```python
def record_tool_execution(url, tool_name, success, response_time):
def get_best_tool_for_site(url, candidate_tools) -> Tuple[str, float]:
```

**Solution:** Track tool performance and automatically route to better tools.

#### **5. MERGE_DATA** → `utils/data_merger.py`
**Purpose:** Merges data from multiple sources with conflict resolution
**Files:** `utils/data_merger.py`

**Key Functions:**
```python
def merge_data(sources: List[Dict]) -> Dict:
    # First non-empty value wins for each field
```

**Solution:** Standardize inconsistent tool outputs to consistent format.

#### **6. SMART_COMPRESS** → `utils/helpers.py`
**Purpose:** Universal content compression with token control (80% cost savings)
**Files:** `utils/helpers.py`, `utils/__init__.py`

**Key Features:**
- Priority-based extraction (headings → paragraphs → lists → tables)
- Exact token limits using tiktoken
- Fallback recovery for unusual page structures
- 97% size reduction while preserving context

**Solution:** Replace fragile regex extraction with reliable content parsing.

#### **7. VALIDATE_RECORD** → `utils/schema_builder.py`
**Purpose:** Automatic JSON schema generation and validation
**Files:** `utils/schema_builder.py`

**Key Functions:**
```python
def validate_record(record, schema) -> Dict[str, Any]:
    # Returns: valid, errors, warnings
```

**Solution:** Add schema validation to ToolResult to prevent type inconsistencies.

### **🚨 Root Cause & Solution Mapping**

#### **PRIMARY ISSUE: ToolResult.data: Optional[Any]**
**Problem:** Allows any data type, causing inconsistent formats
**Impact:** DataFlowResolver can't predict or validate output formats

**SOLUTION: Activate "Dead Code" Pipeline**
```
1. Use VALIDATE_RECORD → Schema validation on tool outputs
2. Use MERGE_DATA → Standardize to consistent format  
3. Use RESULT_VALIDATOR → Check completeness before processing
4. Use STRUCTURED_OUTPUT → Consistent LLM responses
5. Use SMART_COMPRESS → Reliable content extraction
6. Use LEARNING_MANAGER → Performance-based tool selection
```

#### **Data Flow Issue Resolution:**
```
BEFORE (Broken):
Tool.execute() → ToolResult(data=Any) → DataFlowResolver → Regex Fail → url=None

AFTER (Fixed):
Tool.execute() → VALIDATE_RECORD → MERGE_DATA → RESULT_VALIDATOR → Structured Data
```

### **📋 Implementation Roadmap Using "Dead Code"**

#### **PHASE 1: Data Validation Pipeline**
- [ ] Import `validate_record` from `utils.schema_builder`
- [ ] Add schema validation to ToolResult creation
- [ ] Use `check_completeness` from task decomposer

#### **PHASE 2: Structured LLM Integration**
- [ ] Import `invoke_with_schema` from `services.llm_service`
- [ ] Replace regex parsing with structured output validation
- [ ] Update all LLM calls to use consistent schemas

#### **PHASE 3: Smart Data Processing**
- [ ] Import `merge_data` from `utils.data_merger`
- [ ] Standardize tool outputs to consistent format
- [ ] Handle different data types (string, dict, list) uniformly

#### **PHASE 4: Content Extraction Upgrade**
- [ ] Import `smart_compress` from `utils.helpers`
- [ ] Replace fragile regex with structured content parsing
- [ ] Enable 80% cost savings on LLM calls

#### **PHASE 5: Performance Learning**
- [ ] Import `LearningManager` from `tools.learning_manager`
- [ ] Track tool performance metrics
- [ ] Route to better-performing tools automatically

### **🎯 Expected Impact**

#### **Before Fixes:**
- ❌ Flight search fails due to regex extraction
- ❌ Inconsistent data types cause parameter resolution failures
- ❌ No validation allows bad data to propagate
- ❌ High LLM costs due to full HTML processing

#### **After Fixes:**
- ✅ Structured data validation prevents type issues
- ✅ Smart compression reduces costs by 80%
- ✅ Consistent LLM outputs eliminate parsing failures
- ✅ Performance learning improves tool selection
- ✅ Data merging standardizes tool outputs

### **🔧 Quick Wins (Low Effort, High Impact)**

1. **Add Schema Validation** (5 min)
   ```python
   # In ToolResult creation
   from utils.schema_builder import validate_record
   validated = validate_record(data, tool_schema)
   ```

2. **Use Structured LLM** (10 min)
   ```python
   # Replace regex parsing
   result = llm_service.invoke_with_schema(prompt, schema)
   ```

3. **Add Completeness Check** (5 min)
   ```python
   # Before DataFlowResolver
   from routing.result_validator import ResultValidator
   validator = ResultValidator()
   validation = validator.validate(results, required_fields)
   ```

This "dead code" contains **complete solutions** to your data flow problems! 🚀

---

This architecture provides a robust, scalable multi-agent system with clean separation of concerns, comprehensive error handling, and efficient data flow between components. The utility system enables efficient content processing, while the routing system provides intelligent tool selection and self-learning capabilities.
