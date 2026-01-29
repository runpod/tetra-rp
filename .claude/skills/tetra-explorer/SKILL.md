# Tetra-rp Framework Explorer Skill

## When to Use

Use this skill when:
- Exploring the tetra-rp framework codebase
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

### Step 2: Only Read Full Files When Necessary

After querying the code intelligence database, only use the Read tool if:
- You need to understand the implementation details
- The database doesn't have the specific information you need
- You need to see the full context around a symbol

## Examples

**Good - Query first:**
1. Use `find_symbol` with "ServerlessEndpoint"
2. Review the signatures and locations
3. Only read the full file if you need implementation details

**Bad - Reading files directly:**
1. Read entire `src/tetra_rp/core/resources/serverless.py` (500+ tokens)
2. Search manually for ServerlessEndpoint

## Benefits

- **85% token reduction** for exploration tasks
- **Faster responses** - no need to parse large files
- **Better context** - see symbols across multiple files
- **Focused reading** - only read what you actually need

## Important Notes

- The code intelligence database is updated by running `make index`
- If you get unexpected results, the index might be stale
- Database contains: classes, functions, methods, decorators, type hints, docstrings
- Database does NOT contain: implementations, comments, full file content
