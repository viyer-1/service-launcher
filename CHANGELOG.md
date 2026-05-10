# Changelog

All notable changes to this project will be documented in this file.

## [1.1.0] - 2026-05-10

### Added
- **Environment Variable Support**: Integrated `python-dotenv` to allow configuration via `.env` files.
- **Configurable Paths**: `ALLOWED_BROWSE_PATHS` and `DEFAULT_BROWSE_PATH` can now be set via environment variables, allowing for easier deployment across different systems.
- **Port Configuration**: The server port can now be configured using the `SERVICE_LAUNCHER_PORT` environment variable.
- **Configuration Template**: Added `.env.example` to guide users through the setup process.

### Changed
- **Documentation Refactor**: Moved technical bug fix details to `docs/INTERNAL_FIXES.md` and established this high-level changelog for better readability.

## [1.0.0] - 2024-12-20

### Added
- **FastAPI Rewrite**: Completely rebuilt the backend using FastAPI and native asyncio for improved stability and performance.
- **WebSocket Streaming**: Implemented real-time output streaming from scripts to the browser.
- **Memory Management**: Added server-side and client-side handling for very large script outputs to prevent memory overflow.
- **Graceful Shutdown**: Added signal handlers to ensure all sub-processes are terminated when the server stops.
- **File Browser**: Integrated a server-side file and folder picker for script parameters.

### Fixed
- **Command Parsing**: Resolved issues with spaces and quotes in script commands using proper shell-like parsing.
- **Positional Arguments**: Fixed handling of parameters without flags.
- **Process Race Conditions**: Implemented async locks to prevent concurrent access issues during process cleanup.
- **Security**: Hardened command injection protection by blacklisting dangerous shell characters.
- **Validation**: Added frontend validation for required script parameters.
- **WebSocket Reliability**: Fixed namespace issues that previously prevented output from streaming in certain environments.
