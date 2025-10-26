# KaryaKarta Agent - System Architecture

**Version**: 1.0.0  
**Last Updated**: 2025-10-25

## Table of Contents

1. [Overview](#overview)
2. [System Design Principles](#system-design-principles)
3. [Project Structure](#project-structure)
4. [Core Components](#core-components)
5. [Tool Architecture](#tool-architecture)
6. [Data Flow](#data-flow)
7. [Technology Stack](#technology-stack)
8. [Future Enhancements](#future-enhancements)

---

## Overview

KaryaKarta Agent is an AI-powered research assistant that uses LangGraph and Gemini to perform multi-step reasoning tasks. The system is designed with modularity, scalability, and maintainability in mind, following SOLID principles.

### Key Features

- **Multi-step Reasoning**: Agent breaks down complex queries into actionable steps
- **Generalist Tools**: Flexible tools that work across any domain (restaurants, events, dentists, etc.)
- **Conversation Memory**: Maintains context across multiple messages
- **Real-time Updates**: WebSocket-based communication for live progress updates
- **Message Deduplication**: Robust tracking to prevent duplicate responses

---

## System Design Principles

### SOLID Principles

#### 1. Single Responsibility Principle (SRP)
Each module has one clear responsibility:
- `agent.py` → Agent orchestration only
- `search.py` → Search tools only
- `logging_service.py` → Logging only
- `memory.py` → Memory management only

#### 2. Open/Closed Principle (OCP)
- Base tool class open for extension, closed for modification
- New tools extend `BaseTool` without changing existing code
- Plugin architecture for adding capabilities

#### 3. Liskov Substitution Principle (LSP)
- All tools implement the same interface
- Any tool can be swapped without breaking the agent
- Consistent tool signature: `execute(params) -> ToolResult`

#### 4. Interface Segregation Principle (ISP)
- Small, focused interfaces
- Tools only implement what they need
- No "fat" interfaces with unused methods

#### 5. Dependency Inversion Principle (DIP)
- Depend on abstractions, not concretions
- Agent depends on `BaseTool` interface, not specific tools
- LLM service abstraction allows switching providers

---

## Project Structure

```
karyakarta-agent/
├── docs/                           # Documentation
│   ├── ARCHITECTURE.md            # This file
│   ├── API_CONTRACT.md            # API contract with frontend
│   └── TYPESCRIPT_TYPES.md        # TypeScript definitions
│
├── src/                           # Source code
│   ├── core/                      # Core functionality
│   │   ├── __init__.py
│   │   ├── agent.py              # Agent orchestration
│   │   ├── graph.py              # LangGraph workflow
│   │   ├── memory.py             # Conversation memory
│   │   └── config.py             # Configuration
│   │
│   ├── tools/                     # Tool implementations
│   │   ├── __init__.py
│   │   ├── base.py               # Base tool class
│   │   ├── search.py             # Web search tools
│   │   ├── scraper.py            # Web scraping tools
│   │   ├── extractor.py          # Data extraction tools
│   │   ├── calculator.py         # Calculation tools
│   │   ├── places.py             # Location-based tools
│   │   └── events.py             # Event search tools
│   │
│   ├── prompts/                   # Prompt management
│   │   ├── __init__.py
│   │   ├── system_prompt.py      # Main system prompt
│   │   └── templates.py          # Prompt templates
│   │
│   ├── models/                    # Data models
│   │   ├── __init__.py
│   │   ├── message.py            # Message models
│   │   ├── session.py            # Session models
│   │   └── tool_result.py        # Tool result models
│   │
│   ├── services/                  # Services
│   │   ├── __init__.py
│   │   ├── logging_service.py    # Logging to UI
│   │   ├── llm_service.py        # LLM provider abstraction
│   │   └── cache_service.py      # Caching (future)
│   │
│   └── utils/                     # Utilities
│       ├── __init__.py
│       ├── validators.py         # Input validation
│       ├── formatters.py         # Output formatting
│       └── helpers.py            # Helper functions
│
├── api/                           # FastAPI application
│   ├── __init__.py
│   ├── main.py                   # FastAPI entry point
│   ├── routes.py                 # API routes
│   └── middleware.py             # Middleware
│
├── tests/                         # Tests
│   ├── unit/                     # Unit tests
│   ├── integration/              # Integration tests
│   └── e2e/                      # End-to-end tests
│
├── .env                          # Environment variables
├── requirements.txt              # Python dependencies
├── pyproject.toml               # Project metadata
└── README.md                     # Project overview
```

---

## Core Components

### 1. Agent Manager (`src/core/agent.py`)

**Responsibility**: Orchestrates agent lifecycle and execution

```python
class AgentManager:
    """Manages agent instances and sessions."""
    
    def __init__(
        self,
        llm_service: LLMService,
        memory_service: MemoryService,
        logging_service: LoggingService,
        tools: List[BaseTool]
    ):
        """Initialize with dependency injection."""
        
    def create_session(self, session_id: str) -> AgentSession:
        """Create a new agent session with memory."""
        
    def execute_task(
        self, 
        session_id: str,
        message_id: str,
        prompt: str
    ) -> TaskResult:
        """Execute a task within a session."""
```

**Key Features**:
- Session-based agent management
- Conversation memory integration
- Tool coordination
- Error handling and recovery

### 2. LangGraph Workflow (`src/core/graph.py`)

**Responsibility**: Defines the agent's reasoning loop

```python
def create_workflow(tools: List[BaseTool]) -> CompiledGraph:
    """Create the LangGraph workflow."""
    
    workflow = StateGraph(MessagesState)
    
    # Add nodes
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", tool_node)
    
    # Add edges
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue)
    workflow.add_edge("tools", "agent")
    
    return workflow.compile(checkpointer=memory)
```

**Flow**:
1. Agent receives user message
2. Agent decides to use a tool or respond
3. If tool: Execute tool → Return to agent
4. If respond: Generate final answer
5. Loop continues until agent decides to finish

### 3. Base Tool (`src/tools/base.py`)

**Responsibility**: Abstract base class for all tools

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel

class ToolResult(BaseModel):
    """Standardized tool result."""
    success: bool
    data: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}

class BaseTool(ABC):
    """Abstract base class for all tools."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name for LLM."""
        
    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description for LLM."""
        
    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Execute the tool."""
```

**Benefits**:
- Consistent interface across all tools
- Easy to add new tools
- Type-safe execution
- Standardized error handling

### 4. Memory Service (`src/core/memory.py`)

**Responsibility**: Manages conversation history

```python
class MemoryService:
    """Manages conversation memory across sessions."""
    
    def __init__(self):
        self.checkpointer = MemorySaver()
        self.sessions: Dict[str, SessionState] = {}
        
    def get_session(self, session_id: str) -> SessionState:
        """Get or create a session."""
        
    def save_message(self, session_id: str, message: Message):
        """Save a message to session history."""
        
    def get_history(self, session_id: str) -> List[Message]:
        """Retrieve conversation history."""
```

**Features**:
- Per-session conversation history
- LangGraph checkpointing integration
- Automatic cleanup of old sessions

### 5. Logging Service (`src/services/logging_service.py`)

**Responsibility**: Real-time communication with UI

```python
class LoggingService:
    """Handles logging to UI via WebSocket."""
    
    def log_status(self, message: str, message_id: str = None):
        """Log status message."""
        
    def log_thinking(self, message: str, message_id: str = None):
        """Log agent thinking."""
        
    def log_response(self, message: str, message_id: str):
        """Log final response."""
        
    def log_error(self, error: str, message_id: str = None):
        """Log error."""
```

**Message Types**:
- **Status**: "Searching...", "Processing..."
- **Thinking**: Agent's reasoning process
- **Response**: Final answer
- **Error**: Error messages

---

## Tool Architecture

### Generalist Tool Design

Tools are designed to be **domain-agnostic** and **composable**.

#### Example: Search Tool

Instead of:
- ❌ `restaurant_search()`
- ❌ `dentist_search()`
- ❌ `concert_search()`

We have:
- ✅ `search_web(query)` - Works for anything
- ✅ `search_places(query, location, filters)` - Generic places search
- ✅ `extract_webpage_content(url, extract_type)` - Flexible extraction

#### Tool Categories

1. **Search Tools** (`src/tools/search.py`)
   - `search_web()` - General web search
   - `search_places()` - Location-based search with filters
   - `search_events()` - Event discovery

2. **Scraping Tools** (`src/tools/scraper.py`)
   - `extract_webpage_content()` - Smart web scraping
   - `extract_multiple_pages()` - Batch scraping

3. **Extraction Tools** (`src/tools/extractor.py`)
   - `extract_structured_info()` - AI-powered extraction
   - `extract_prices()` - Price extraction
   - `extract_ratings()` - Rating extraction

4. **Analysis Tools** (`src/tools/calculator.py`)
   - `calculate()` - Mathematical operations
   - `filter_data()` - Data filtering
   - `sort_data()` - Data sorting
   - `compare()` - Comparison operations

### Tool Composition

The agent **combines tools creatively** to accomplish tasks:

**Example: "Find dentists with 4+ rating under $200"**

```
1. search_places("dentist", location, filters={"rating": "4+"})
2. For each dentist:
   - extract_webpage_content(dentist_url, "prices")
3. calculate("filter prices under 200")
4. Present results
```

---

## Data Flow

### Request Flow

```
1. User sends message via UI
   ↓
2. Frontend generates messageId & sessionId
   ↓
3. POST /execute-task → Backend
   ↓
4. AgentManager.execute_task()
   ↓
5. LangGraph workflow starts
   ↓
6. Agent analyzes task (calls LLM)
   ↓
7. Agent decides: Use tool or respond?
   ↓
8a. If tool: Execute tool → Log to UI → Return to agent
8b. If respond: Generate answer → Log to UI → End
   ↓
9. Response sent to UI via WebSocket
```

### Message Tracking Flow

```
Frontend                    Backend
   |                          |
   |-- Generate messageId ---->|
   |                          |
   |-- Send request ---------->|
   |                          |
   |                          |-- Check duplicate
   |                          |-- Mark as active
   |                          |-- Process task
   |                          |
   |<- Status updates ---------|
   |<- Thinking updates -------|
   |<- Final response ---------|
   |                          |
   |                          |-- Mark as completed
   |                          |-- Cleanup
```

---

## Technology Stack

### Backend

- **Language**: Python 3.10+
- **Framework**: FastAPI
- **AI Framework**: LangGraph + LangChain
- **LLM**: Google Gemini 2.5 Flash Lite
- **Web Scraping**: Playwright
- **APIs**: Google Serper, Browserless

### Frontend

- **Framework**: Next.js 14+
- **Language**: TypeScript
- **Real-time**: Socket.IO
- **State Management**: React Hooks

### Infrastructure

- **API**: RESTful + WebSocket
- **Data Models**: Pydantic
- **Validation**: Pydantic validators
- **Testing**: Pytest (backend), Jest (frontend)

---

## Future Enhancements

### Phase 1 (Current)
- ✅ Basic agent with Google Search
- ✅ WebSocket communication
- ⏳ Message ID tracking
- ⏳ Session management

### Phase 2 (Next Sprint)
- [ ] Enhanced generalist tools
- [ ] Persistent memory with database
- [ ] Rate limiting
- [ ] Caching layer

### Phase 3 (Future)
- [ ] Google Docs integration
- [ ] Office 365 integration
- [ ] Multi-user support
- [ ] Analytics and monitoring

### Phase 4 (Long-term)
- [ ] Voice interface
- [ ] Image analysis
- [ ] Custom tool creation
- [ ] Agent-to-agent communication

---

## Performance Considerations

### Optimization Strategies

1. **Caching**: Cache search results and scraped content
2. **Rate Limiting**: Prevent API abuse
3. **Connection Pooling**: Reuse database connections
4. **Lazy Loading**: Load tools on-demand
5. **Streaming**: Stream LLM responses in real-time

### Scalability

- **Horizontal Scaling**: Stateless API design allows horizontal scaling
- **Session Management**: Redis for distributed sessions
- **Load Balancing**: Nginx/ALB for load distribution
- **Database**: PostgreSQL for persistent storage

---

## Security Considerations

1. **API Keys**: Stored in environment variables
2. **Input Validation**: Pydantic validation on all inputs
3. **Rate Limiting**: Prevent abuse
4. **CORS**: Configured for frontend domain only
5. **Error Handling**: No sensitive data in error messages

---

## Monitoring & Observability

### Logging

- **Application Logs**: Python logging module
- **Access Logs**: FastAPI access logs
- **Error Tracking**: Sentry (future)

### Metrics

- **Request Count**: Track API usage
- **Response Time**: Monitor latency
- **Tool Usage**: Track which tools are used most
- **Error Rate**: Monitor error frequency

---

## Development Workflow

1. **Feature Development**
   - Create feature branch
   - Implement changes
   - Write tests
   - Update documentation

2. **Testing**
   - Unit tests (pytest)
   - Integration tests
   - E2E tests
   - Manual testing

3. **Deployment**
   - Review code
   - Merge to main
   - Deploy to staging
   - Test in staging
   - Deploy to production

---

## Contact & Resources

- **Documentation**: See `/docs` folder
- **API Contract**: See `docs/API_CONTRACT.md`
- **Issues**: Create GitHub issue
- **Questions**: Contact development team
