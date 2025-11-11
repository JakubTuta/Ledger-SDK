## Important Project Notes

- My operating system is Windows 11. Use Windows-compatible commands where possible.
- The project uses Python 3.12 with `venv` for virtual environments.
- For development details, see `sdk_overview/` directory.
- For server implementation details see `server_overview/` directory.
- Don't create documentation in markdown files unless explicitly asked.

## Important Coding Guidelines

### Code Style

- Don't write inline comments in code, instead use descriptive function/class/variable names.
- Use type hints for all functions and methods.
- Never put emojis in code or comments.
- Write clean, single responsibility functions and classes.
- Create file and directory structures that are easy to navigate and understand, scalable and maintainable.

### Import Strategy

- Import modules (files) instead of individual classes/functions where possible.
- Example: Use `import module` then `module.Class` instead of `from module import Class`.
- This improves readability and prevents circular import issues.

### Architecture Patterns (Implemented Across Services)

- **Async/await everywhere** - All I/O operations use async (database, Redis, gRPC, HTTP)
- **Pydantic for config** - All services use Pydantic Settings for type-safe configuration
- **Structured logging** - JSON logs with correlation IDs for distributed tracing
- **Error handling** - Try-except blocks with specific exceptions, never bare except
