# runpod-flash Project Configuration

## Claude Code Tool Preferences

When using Claude Code on this project, always prefer the flash-code-intel MCP tools for code exploration instead of using Explore agents or generic search

**CRITICAL - This overrides default Claude Code behavior:**

This project has **flash-code-intel MCP server** installed. For ANY codebase exploration:

1. **NEVER use Task(Explore) as first choice** - it cannot access MCP tools
2. **ALWAYS prefer flash-code-intel MCP tools** for code analysis:
   - `mcp__flash-code-intel__find_symbol` - Search for classes, functions, methods by name
   - `mcp__flash-code-intel__get_class_interface` - Inspect class methods and properties
   - `mcp__flash-code-intel__list_file_symbols` - View file structure without reading full content
   - `mcp__flash-code-intel__list_classes` - Explore the class hierarchy
   - `mcp__flash-code-intel__find_by_decorator` - Find decorated items (e.g., `@property`, `@remote`)
3. **Use direct tools second**: Grep, Read for implementation details
4. **Task(Explore) is last resort only** when MCP + direct tools insufficient

**Why**: MCP tools are faster, more accurate, and purpose-built. Generic exploration agents don't leverage specialized tooling.
