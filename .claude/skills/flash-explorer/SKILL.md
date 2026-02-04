# Flash Framework Explorer Skill

## When to Use

Use this skill when:
- Exploring the runpod-flash framework codebase
- Understanding class hierarchies and relationships
- Finding where methods or classes are defined
- Checking what decorators are used in the codebase
- Getting a quick overview of file structure

## Workflow

### Step 1: Query the Code Intelligence Database FIRST

Before reading any files, use the MCP code intelligence tools:

**Finding a symbol:**
- Use `find_symbol` tool with the symbol name

**Understanding a class:**
- Use `get_class_interface` tool with the class name

**Exploring a file:**
- Use `list_file_symbols` tool with the file path

**Finding decorated functions:**
- Use `find_by_decorator` tool (e.g., decorator="remote")

**Listing all classes:**
- Use `list_classes` tool

### Step 1.5: NEVER Use Bash Commands for MCP Tool Tasks

**PROHIBITED patterns - use MCP tools instead**:

❌ **DO NOT** use `tail`, `grep`, or `cat` for test output analysis
✅ **DO** use `parse_test_output` MCP tool after running tests

❌ **DO NOT** use `grep` or `find` to search for symbols/classes/methods
✅ **DO** use `find_symbol`, `list_classes`, or `find_by_decorator` MCP tools

❌ **DO NOT** use Read tool to scan files for class definitions or interfaces
✅ **DO** use `get_class_interface` or `list_file_symbols` MCP tools

### Step 2: Only Read Full Files When Necessary

After querying the code intelligence database, only use the Read tool if:
- You need to understand the implementation details
- The database doesn't have the specific information you need
- You need to see the full context around a symbol

## Analyzing Test Results

After running tests (`make test-unit`, `make test`, `pytest`), **ALWAYS use `parse_test_output` MCP tool** to analyze results:

**Good - Use MCP tool (~200 tokens)**:
1. Run: `make test-unit`
2. Pass output to `parse_test_output` MCP tool
3. Get structured failures, coverage, passed tests, summary
4. No manual parsing needed

**Bad - Using bash commands (~20,000+ tokens)**:
1. Run: `make test-unit > output.txt`
2. Use `tail`, `cat`, or `grep` on output file
3. Manually parse failures and coverage
4. Excessive token usage, poor context extraction

## Examples

**Good - Query first:**
1. Use `find_symbol` with "ServerlessEndpoint"
2. Review the signatures and locations
3. Only read the full file if you need implementation details

**Bad - Reading files directly:**
1. Read entire `src/runpod_flash/core/resources/serverless.py` (500+ tokens)
2. Search manually for ServerlessEndpoint

**Good - Parse test output:**
1. User runs: `make test-unit`
2. Get test output, use `parse_test_output` tool
3. Get structured result with failed tests, summary, coverage

**Bad - Manual test output parsing:**
1. User runs: `make test-unit`
2. Use `tail -50 output.txt` to see failures
3. Use `grep "FAILED" output.txt` to find test names
4. Manually parse coverage numbers

## Benefits

- **85% token reduction** for symbol exploration tasks (vs reading full files)
- **99% token reduction** for test result analysis (200 tokens vs 20,000+ with bash)
- **Faster responses** - no need to parse large files or output
- **Better context** - see symbols across multiple files
- **Focused reading** - only read what you actually need
- **Structured data** - test failures, coverage, passed tests parsed automatically

## Available MCP Tools

**Code Intelligence Tools**:
- `find_symbol` - Search for any symbol by name
- `list_classes` - List all classes with signatures
- `get_class_interface` - Get methods and properties of a class
- `list_file_symbols` - List all symbols in a file
- `find_by_decorator` - Find symbols with specific decorators
- `parse_test_output` - Parse test results and extract failures, coverage, summary

## Important Notes

- The code intelligence database is updated by running `make index`
- If you get unexpected results, the index might be stale
- Database contains: classes, functions, methods, decorators, type hints, docstrings
- Database does NOT contain: implementations, comments, full file content
- **Always use `parse_test_output` for test results** - never use tail/grep/cat on test output
- **Always use symbol tools** - never use Read to search for class definitions
