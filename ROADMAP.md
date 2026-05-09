# Project Roadmap

This document outlines the planned features and improvements for Service Launcher.

## Upcoming Features (Next Version)

### 🔐 Enhanced Authentication & Security
- **Role-Based Access Control (RBAC)**: Define groups (e.g., 'IT-Admin', 'Support', 'Finance') and restrict script visibility and execution to specific groups.
- **OIDC / LDAP Integration**: Support for enterprise identity providers to allow single sign-on (SSO).
- **Session Management**: Secure login page with cookie-based sessions.

### 📝 Audit Logging
- **Execution History**: Persistent database tracking who ran which script, with what parameters, at what time, and the resulting exit code.
- **Output Archiving**: Option to save and view the output of past script executions.

### 🛠️ Developer Experience
- **Script Scheduling**: Built-in cron-like functionality to run scripts on a schedule.
- **Webhook Notifications**: Send alerts to Slack, Microsoft Teams, or custom webhooks when a script completes or fails.
- **Input Validation**: Add regex-based validation patterns for script parameters in the UI.

## Future Vision (Long-term)

### 📊 Dashboard Enhancements
- **Widget Support**: Create custom dashboard widgets to display script-generated metrics (e.g., charts, status indicators).
- **Mobile App**: Native mobile applications for easier remote management.

### ☁️ Multi-Node Management
- **Centralized Dashboard**: Manage scripts across multiple servers from a single dashboard.
- **Agent Architecture**: Lightweight agents running on remote servers that communicate back to the central controller.

---

*Note: This roadmap is subject to change based on community feedback and contributions.*
