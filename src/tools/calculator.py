"""
Calculator Tool - PRIORITY 3

IMPLEMENTATION STATUS: ✅ IMPLEMENTED

A tool for performing mathematical calculations safely.
Uses Python's ast.literal_eval for safe expression evaluation.

Usage:
    from src.tools.calculator import CalculatorTool
    
    calc = CalculatorTool()
    result = calc.execute(expression="2 + 2 * 3")
    print(result.data)  # "8"
"""

import ast
import operator
import math
from typing import Optional, Union
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from src.tools.base import BaseTool, ToolResult
from src.services.logging_service import LoggingService


class CalculatorInput(BaseModel):
    """Input schema for calculator tool."""
    expression: str = Field(
        description=(
            "A mathematical expression to evaluate. "
            "Supports: basic operations (+, -, *, /, **, %), "
            "functions (sqrt, sin, cos, tan, log, exp, ceil, floor), "
            "and constants (pi, e). "
            "Examples: '2 + 2 * 3', 'sqrt(16)', 'pi * 2', 'sin(pi/2)'"
        )
    )


class CalculatorTool(BaseTool):
    """
    Calculator tool for safe mathematical evaluations.
    
    Supports:
    - Basic operations: +, -, *, /, //, %, **
    - Math functions: sin, cos, tan, sqrt, log, etc.
    - Constants: pi, e
    - Parentheses for grouping
    """
    
    # Allowed operations for safe evaluation
    ALLOWED_OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }
    
    # Allowed math functions
    ALLOWED_FUNCTIONS = {
        'abs': abs,
        'round': round,
        'min': min,
        'max': max,
        'sum': sum,
        'sqrt': math.sqrt,
        'sin': math.sin,
        'cos': math.cos,
        'tan': math.tan,
        'log': math.log,
        'log10': math.log10,
        'exp': math.exp,
        'ceil': math.ceil,
        'floor': math.floor,
    }
    
    # Allowed constants
    ALLOWED_CONSTANTS = {
        'pi': math.pi,
        'e': math.e,
    }
    
    def __init__(self, logger: Optional[LoggingService] = None):
        """
        Initialize the calculator tool.
        
        Args:
            logger: Optional logging service
        """
        super().__init__(logger)
    
    @property
    def name(self) -> str:
        """Tool name for LangChain."""
        return "calculator"
    
    @property
    def description(self) -> str:
        """Tool description for LLM."""
        return """Performs mathematical calculations safely.
        
        Use this when you need to:
        - Calculate mathematical expressions
        - Evaluate formulas
        - Perform arithmetic operations
        - Use mathematical functions
        
        Supported operations:
        - Basic: + (add), - (subtract), * (multiply), / (divide), ** (power), % (modulo), // (floor divide)
        - Functions: sqrt, sin, cos, tan, log, log10, exp, ceil, floor, abs, round, min, max, sum
        - Constants: pi, e
        
        Input: A mathematical expression as a string
        Output: The calculated result
        
        Examples:
        - calculator(expression="2 + 2 * 3")  # Returns 8
        - calculator(expression="sqrt(16)")   # Returns 4.0
        - calculator(expression="pi * 2")     # Returns 6.283185307179586
        - calculator(expression="sin(pi/2)")  # Returns 1.0
        - calculator(expression="(10 + 5) / 3")  # Returns 5.0
        """
    
    def validate_params(self, **kwargs) -> bool:
        """
        Validate calculator parameters.
        
        Args:
            **kwargs: Should contain 'expression' parameter
            
        Returns:
            bool: True if valid, False otherwise
        """
        # Handle nested kwargs from LangChain
        if "kwargs" in kwargs and isinstance(kwargs["kwargs"], dict):
            kwargs = kwargs["kwargs"]
        
        # Check for expression parameter
        if "expression" not in kwargs:
            return False
        
        expression = kwargs.get("expression")
        
        # Must be a non-empty string
        if not isinstance(expression, str) or not expression.strip():
            return False
        
        return True
    
    def _safe_eval(self, node: ast.AST) -> Union[int, float]:
        """
        Safely evaluate an AST node.
        
        Args:
            node: AST node to evaluate
            
        Returns:
            The evaluated result
            
        Raises:
            ValueError: If the expression contains disallowed operations
        """
        if isinstance(node, ast.Constant):  # Python 3.8+
            value = node.value
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return value
            raise ValueError(f"Constant type {type(value).__name__} is not allowed")
        elif isinstance(node, ast.Num):  # Legacy support
            value = node.n
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return value
            raise ValueError(f"Number type {type(value).__name__} is not allowed")
        elif isinstance(node, ast.Name):
            # Check for allowed constants
            if node.id in self.ALLOWED_CONSTANTS:
                return self.ALLOWED_CONSTANTS[node.id]
            raise ValueError(f"Name '{node.id}' is not allowed")
        elif isinstance(node, ast.BinOp):
            # Binary operation (e.g., 2 + 3)
            if type(node.op) not in self.ALLOWED_OPERATORS:
                raise ValueError(f"Operator {type(node.op).__name__} is not allowed")
            left = self._safe_eval(node.left)
            right = self._safe_eval(node.right)
            return self.ALLOWED_OPERATORS[type(node.op)](left, right)
        elif isinstance(node, ast.UnaryOp):
            # Unary operation (e.g., -5)
            if type(node.op) not in self.ALLOWED_OPERATORS:
                raise ValueError(f"Operator {type(node.op).__name__} is not allowed")
            operand = self._safe_eval(node.operand)
            return self.ALLOWED_OPERATORS[type(node.op)](operand)
        elif isinstance(node, ast.Call):
            # Function call (e.g., sqrt(4))
            if not isinstance(node.func, ast.Name):
                raise ValueError("Only simple function calls are allowed")
            func_name = node.func.id
            if func_name not in self.ALLOWED_FUNCTIONS:
                raise ValueError(f"Function '{func_name}' is not allowed")
            args = [self._safe_eval(arg) for arg in node.args]
            return self.ALLOWED_FUNCTIONS[func_name](*args)
        else:
            raise ValueError(f"Node type {type(node).__name__} is not allowed")
    
    def _execute_impl(self, **kwargs) -> ToolResult:
        """
        Execute the calculator.
        
        Args:
            **kwargs: Must contain 'expression' parameter
            
        Returns:
            ToolResult with calculation result or error
        """
        # Handle nested kwargs
        if "kwargs" in kwargs and isinstance(kwargs["kwargs"], dict):
            kwargs = kwargs["kwargs"]
        
        expression = kwargs.get("expression", "").strip()
        
        if self.logger:
            self.logger.status(f"Calculating: {expression}")
        
        try:
            # Parse the expression into an AST
            tree = ast.parse(expression, mode='eval')
            
            # Safely evaluate the AST
            result = self._safe_eval(tree.body)
            
            # Format the result
            if isinstance(result, float):
                # Round to reasonable precision
                if result == int(result):
                    result = int(result)
                else:
                    result = round(result, 10)
            
            if self.logger:
                self.logger.status(f"Result: {result}")
            
            return ToolResult(
                success=True,
                data=str(result),
                metadata={
                    "expression": expression,
                    "result": result,
                }
            )
            
        except SyntaxError as e:
            error_msg = f"Invalid expression syntax: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            return ToolResult(
                success=False,
                error=error_msg,
                metadata={"expression": expression}
            )
        except ValueError as e:
            error_msg = f"Invalid operation: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            return ToolResult(
                success=False,
                error=error_msg,
                metadata={"expression": expression}
            )
        except ZeroDivisionError:
            error_msg = "Division by zero"
            if self.logger:
                self.logger.error(error_msg)
            return ToolResult(
                success=False,
                error=error_msg,
                metadata={"expression": expression}
            )
        except Exception as e:
            error_msg = f"Calculation error: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            return ToolResult(
                success=False,
                error=error_msg,
                metadata={"expression": expression}
            )
    
    def as_langchain_tool(self):
        """
        Convert to LangChain tool with proper schema.
        
        Returns:
            LangChain tool with input schema
        """
        tool_instance = self
        
        @tool(args_schema=CalculatorInput)
        def calculator(expression: str) -> str:
            """Performs mathematical calculations. Provide a mathematical expression as a string."""
            result = tool_instance.execute(expression=expression)
            return tool_instance.format_result(result)
        
        return calculator
