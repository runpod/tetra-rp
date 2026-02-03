# runpod-flash Project Configuration

## Claude Code Configuration

When using Claude Code on this project, always prefer the tetra-code-intel MCP tools for code exploration instead of using Explore agents or generic search:

- `mcp__tetra-code-intel__find_symbol` - Search for classes, functions, methods by name
- `mcp__tetra-code-intel__get_class_interface` - Inspect class methods and properties
- `mcp__tetra-code-intel__list_file_symbols` - View file structure without reading full content
- `mcp__tetra-code-intel__list_classes` - Explore the class hierarchy
- `mcp__tetra-code-intel__find_by_decorator` - Find decorated items (e.g., `@property`, `@remote`)

**Do NOT** use the Task tool with the "Explore" subagent for codebase exploration. Use the MCP tools directly instead.
