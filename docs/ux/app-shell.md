# App Shell and Navigation

## Permanent three-panel layout
```text
LEFT              CENTER                         RIGHT
Navigation        Current exploration            AI Copilot
~220-260px        flexible                       ~360-480px, resizable
```

React shell concept:
```text
AppShell
  ├── NavigationSidebar
  ├── WorkspaceOutlet
  └── CopilotPanel
```

The Copilot remains mounted to preserve context and conversation while the center changes.

## Top context bar
Always make current Client / SAP System / Assessment visible. Provide a persistent view selector:
- Executive
- Architecture & Clean Core
- Business & Rules
- Engineering & Code

## Global interaction principle
Any relevant entity should support `Ask AI` / `Add to Copilot` actions. Source code selection should be transferable to Copilot without copy/paste.
