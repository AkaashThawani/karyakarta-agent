# Fix Target - What Do We Want?

**Date**: 2025-11-13  
**Purpose**: Define clear goals before implementing any fixes

---

## 🎯 PRIMARY GOAL

**Enable follow-up questions to work correctly.**

### Current Behavior ❌
```
User: "Search for flights from NYC to Chicago"
Agent: [Returns flight data]

User: "Show that as a table"  
Agent: "I don't have any data to show" ❌
```

### Desired Behavior ✅
```
User: "Search for flights from NYC to Chicago"
Agent: [Returns flight data + stores in state]

User: "Show that as a table"
Agent: [Accesses previous data from state]
Agent: [Formats as markdown table] ✅
```

---

## 🔍 SPECIFIC ISSUES TO FIX

### Issue #1: Conversation History Not Used
**What's broken**: MultiAgentManager loads conversation_history but never passes it to LLM calls

**Where**: 
- `src/agents/reason_agent.py` - execute() doesn't pass context
- `src/agents/task_analyzer.py` - analyze_task() doesn't accept history
- `src/agents/execution_engine.py` - execute_plan() doesn't use history
- `src/agents/result_processor.py` - synthesize_results() doesn't see history

**Success criteria**:
- [ ] All LLM prompts include previous 3-5 messages as context
- [ ] Agent can reference "it", "that", "them" from previous responses
- [ ] Follow-up questions about previous data work

### Issue #2: Accumulated Data Lost Between Requests
**What's broken**: ExecutionContext.accumulated_data is temporary, disappears after task

**Where**: `src/agents/execution_engine.py` - ExecutionContext is recreated each time

**Success criteria**:
- [ ] Data from step 1 available in step 2 (within same task) ✅ Already works
- [ ] Data from task 1 available in task 2 (follow-up questions) ❌ Currently broken
- [ ] Multi-turn conversations maintain data context

### Issue #3: Previous Results Not Propagated
**What's broken**: previous_results loaded but not passed to components

**Where**: All agent components don't receive previous_results

**Success criteria**:
- [ ] Agent knows what data it previously extracted
- [ ] Can format/transform previous data without re-extracting
- [ ] Can answer "how many" questions about previous results

---

## ✅ MUST HAVES (Non-Negotiable)

### 1. Conversation Continuity
- [ ] **Follow-up questions work** - Primary requirement
- [ ] Agent remembers previous 5 messages minimum
- [ ] Can reference previous data without re-querying

### 2. Multi-Step Task Reliability  
- [ ] **Data flows between steps** - Already works, don't break
- [ ] Parameter resolution works (DataFlowResolver)
- [ ] Validation/replanning works (already implemented)

### 3. No Breaking Changes
- [ ] **USE_MULTI_AGENT_SYSTEM = True still works**
- [ ] All existing tools continue to function
- [ ] API contract unchanged
- [ ] No frontend changes required

---

## 🎁 NICE TO HAVES (If Easy)

### 1. Unified State Management
- [ ] Both Path A and Path B use same state system
- [ ] MessagesState integrated into MultiAgentManager
- [ ] Proper LangGraph checkpointing

### 2. Performance Optimization
- [ ] Reduce unnecessary LLM calls
- [ ] Cache frequently used data
- [ ] Smart context window management

### 3. Better Error Recovery
- [ ] Graceful handling when history unavailable
- [ ] Fallback to stateless mode if needed

---

## 🚫 EXPLICITLY DON'T WANT

### 1. Don't Change Core Architecture
- ❌ **NO** replacing multi-agent system
- ❌ **NO** removing ReasonAgent/ExecutorAgent
- ❌ **NO** switching back to Path A permanently
- ✅ Keep sophisticated planning capabilities

### 2. Don't Break Existing Functionality
- ❌ **NO** breaking Playwright automation
- ❌ **NO** breaking task decomposition
- ❌ **NO** breaking adaptive execution
- ✅ Everything that works today should still work

### 3. Don't Add Complexity
- ❌ **NO** adding new databases
- ❌ **NO** adding new services
- ❌ **NO** major refactoring
- ✅ Minimal changes to achieve goal

---

## 📊 SUCCESS METRICS

### Functional Tests
```python
# Test 1: Follow-up Question
user_msg_1 = "Find 5 restaurants in Seattle"
agent_response_1 = agent.execute(user_msg_1)
# Expected: Returns 5 restaurants

user_msg_2 = "Show that as a table"
agent_response_2 = agent.execute(user_msg_2)
# Expected: ✅ Formats previous restaurants as table
# Current:  ❌ Says "I don't have data"
```

```python
# Test 2: Reference Previous Data
user_msg_1 = "Search flights NYC to LA"
agent_response_1 = agent.execute(user_msg_1)

user_msg_2 = "How many results did you find?"
agent_response_2 = agent.execute(user_msg_2)
# Expected: ✅ "I found 7 flights"
# Current:  ❌ "I don't have that information"
```

```python
# Test 3: Transform Previous Data
user_msg_1 = "Get product prices from Amazon"
agent_response_1 = agent.execute(user_msg_1)

user_msg_2 = "Sort them by price"
agent_response_2 = agent.execute(user_msg_2)
# Expected: ✅ Sorts previous results
# Current:  ❌ Doesn't have previous data
```

### Technical Validation
- [ ] conversation_history passed to all agent components
- [ ] LLM prompts include history in all calls
- [ ] previous_results accessible in result processing
- [ ] No duplicate data fetching for follow-ups

---

## 🎯 ACCEPTANCE CRITERIA

**The fix is COMPLETE when:**

1. ✅ User can ask "show that as a table" and agent formats previous data
2. ✅ User can ask "how many?" and agent answers from previous results  
3. ✅ User can ask to filter/sort previous data without re-fetching
4. ✅ Existing multi-step tasks still work (don't break DataFlowResolver)
5. ✅ All current tools still function
6. ✅ No changes required to frontend

**Bonus points if:**
- Minimal code changes (prefer parameter passing over refactoring)
- No new dependencies
- No performance degradation

---

## 🚀 IMPLEMENTATION CONSTRAINTS

### Time Budget
- **Maximum**: 4 hours of coding
- **Target**: 2 hours (minimal fix)
- If taking longer → rethink approach

### Code Changes Budget  
- **Maximum**: 10 files modified
- **Target**: 6 files (ReasonAgent, TaskAnalyzer, ExecutionEngine, ResultProcessor, 2 others)
- Prefer small targeted changes over large refactors

### Testing Budget
- **Minimum**: 3 manual tests (follow-up question scenarios)
- **Target**: Add automated tests for conversation continuity
- Don't ship without testing follow-up questions

---

## 🛠️ PROPOSED APPROACH

### Option 1: Pass Context Through Chain (Recommended)
**Time**: ~90 minutes  
**Risk**: Low  
**Benefit**: Immediate fix

**Changes**:
1. ReasonAgent.execute() → Pass context to all sub-components
2. TaskAnalyzer.analyze_task() → Accept and use conversation_history  
3. ExecutionEngine.execute_plan() → Accept and use history
4. ResultProcessor.synthesize_results() → Accept and use history
5. Update all LLM prompts to include history

**Pros**:
- ✅ Quick to implement
- ✅ Low risk
- ✅ Works with current architecture

**Cons**:
- ⚠️ Not using MessagesState (proper solution)
- ⚠️ Manual history management

### Option 2: Integrate MessagesState (Proper Solution)
**Time**: ~8 hours  
**Risk**: Medium  
**Benefit**: Long-term clean architecture

**Changes**:
1. Create multi_agent_graph.py with LangGraph nodes
2. Convert MultiAgentManager to use MessagesState
3. All agents work with messages instead of dicts
4. Proper checkpointing integration

**Pros**:
- ✅ Proper LangGraph integration
- ✅ Automatic history management
- ✅ Better long-term architecture

**Cons**:
- ⚠️ Takes longer
- ⚠️ More complex changes
- ⚠️ Higher risk of breaking things

---

## 💡 RECOMMENDATION

**Start with Option 1** (Pass Context Through Chain)

**Why**:
- Gets us to working state quickly
- Low risk of breaking existing functionality
- Validates that this solves the problem
- Can do Option 2 later as proper refactor

**Then** (if time permits):
- Option 2 as "Phase 2" improvement
- Proper MessagesState integration
- Clean architecture

---

## 📝 QUESTIONS TO ANSWER BEFORE CODING

1. **Do we all agree follow-up questions are the primary goal?** → Yes/No
2. **Are we OK with Option 1 (band-aid) first?** → Yes/No  
3. **What's the absolute minimum fix we'd accept?** → Just follow-up questions working
4. **What existing functionality CANNOT break?** → Multi-step tasks, tools, Playwright
5. **How will we test this works?** → Manual follow-up question tests

---

## ✅ SIGN-OFF

Before implementing ANY code changes:

- [ ] Team agrees on primary goal (follow-up questions)
- [ ] Team agrees on approach (Option 1 vs Option 2)
- [ ] Team agrees on acceptance criteria
- [ ] Team agrees on what NOT to change
- [ ] Team reviewed this document

**Approved by**: _________________  
**Date**: _________________

---

**Now, what do we want to do?**
- A) Implement Option 1 (90 min quick fix)
- B) Implement Option 2 (8 hour proper solution)
- C) Revise the fix target (change goals/scope)
