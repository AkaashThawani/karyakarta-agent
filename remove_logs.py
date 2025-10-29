"""
Script to remove verbose [REASON] and [EXECUTOR] logs
"""
import re

# Read files
with open('src/agents/reason_agent.py', 'r', encoding='utf-8') as f:
    reason_content = f.read()

with open('src/agents/executor_agent.py', 'r', encoding='utf-8') as f:
    executor_content = f.read()

# Remove all print statements with [REASON] or [EXECUTOR]
reason_content = re.sub(r'\s*print\(f?"?\[REASON\][^)]*\)\n?', '', reason_content)
executor_content = re.sub(r'\s*print\(f?"?\[EXECUTOR\][^)]*\)\n?', '', executor_content)

# Write back
with open('src/agents/reason_agent.py', 'w', encoding='utf-8') as f:
    f.write(reason_content)

with open('src/agents/executor_agent.py', 'w', encoding='utf-8') as f:
    f.write(executor_content)

print("✅ Removed all verbose logs from both files!")
