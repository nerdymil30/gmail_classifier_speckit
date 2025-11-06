# Compounding Engineering Plugin - Installation Summary

**Status:** ✅ Successfully Installed
**Source:** https://github.com/EveryInc/every-marketplace
**Installation Date:** 2025-11-06

## Overview

The Compounding Engineering plugin embodies a development philosophy where **each unit of engineering work should make subsequent units of work easier—not harder.** This plugin provides AI-powered development tools that get smarter with every use.

## What Was Installed

### 📋 Commands (6)

Commands are invoked with slash syntax in Claude Code. For example: `/plan` or `/review`

1. **`/plan`** - Transform feature descriptions into detailed GitHub issues
   - Creates comprehensive specifications
   - Includes research and acceptance criteria
   - Generates structured implementation plans

2. **`/work`** - Execute plans systematically
   - Uses isolated git worktrees
   - Continuous validation
   - Systematic implementation approach

3. **`/review`** - Perform exhaustive multi-agent code reviews
   - Security analysis
   - Performance evaluation
   - Architecture assessment
   - Uses specialized review agents

4. **`/triage`** - Present findings for review
   - Converts approved items into actionable todos
   - Prioritizes issues
   - Creates structured action items

5. **`/resolve_todo_parallel`** - Handle multiple todos concurrently
   - Parallel processing
   - Quality checks
   - Efficient task resolution

6. **`/generate_command`** - Create new Claude Code commands
   - Generate commands from descriptions
   - Extend the system dynamically
   - Custom workflow automation

### 🤖 Agents (17)

Agents are specialized AI assistants that can be invoked for specific tasks. They work in the background to provide expert analysis.

#### Code Review Specialists
- **dhh-rails-reviewer** - Rails review following DHH's principles
- **kieran-python-reviewer** - Python code review
- **kieran-typescript-reviewer** - TypeScript code review
- **kieran-rails-reviewer** - Rails code review
- **code-simplicity-reviewer** - Code simplification analysis

#### Quality Assurance
- **security-sentinel** - Security vulnerability detection
- **performance-oracle** - Performance optimization analysis
- **data-integrity-guardian** - Data consistency and integrity checks

#### Architecture & Design
- **architecture-strategist** - High-level architecture analysis
- **pattern-recognition-specialist** - Design pattern identification
- **best-practices-researcher** - Best practices research

#### Research & Analysis
- **framework-docs-researcher** - Framework documentation research
- **repo-research-analyst** - Repository analysis and insights
- **git-history-analyzer** - Git history and pattern analysis

#### Workflow & Style
- **every-style-editor** - Every.to style guide enforcement
- **feedback-codifier** - Convert feedback into actionable items
- **pr-comment-resolver** - Resolve PR comments efficiently

## Usage Examples

### Basic Command Usage

```bash
# Plan a new feature
/plan Implement user authentication with OAuth2

# Review the current codebase
/review

# Work on a planned feature
/work

# Triage issues and create todos
/triage

# Resolve todos in parallel
/resolve_todo_parallel

# Generate a custom command
/generate_command Create a command that analyzes API endpoints
```

### Using with Agents

The agents work automatically when you use commands like `/review`, but you can also invoke them explicitly in your prompts. For example:

```
"Use the security-sentinel agent to analyze this authentication code"
"Have the performance-oracle review this database query"
"Ask the architecture-strategist to evaluate this system design"
```

## Command Locations

- **Commands:** `.claude/commands/`
- **Agents:** `.claude/agents/`

## Philosophy

The Compounding Engineering approach focuses on:

1. **Incremental Improvement** - Each change makes future changes easier
2. **Knowledge Accumulation** - Learning compounds over time
3. **Systematic Approach** - Structured workflows reduce cognitive load
4. **Quality First** - Automated reviews catch issues early
5. **Efficiency Multiplier** - Tools that make you faster every time you use them

## Integration with Existing Commands

This plugin works alongside your existing Speckit commands:
- `/speckit.specify`
- `/speckit.plan`
- `/speckit.tasks`
- `/speckit.implement`
- `/speckit.analyze`
- `/speckit.clarify`
- `/speckit.checklist`
- `/speckit.constitution`

You can use both toolsets together for maximum productivity.

## Next Steps

1. **Try a command:** Start with `/plan` to see how it transforms feature ideas
2. **Run a review:** Use `/review` to analyze your current codebase
3. **Explore agents:** Read the agent files in `.claude/agents/` to understand their specialties
4. **Customize:** Modify the commands in `.claude/commands/` to fit your workflow

## Learn More

- **Homepage:** https://every.to/source-code/my-ai-had-already-fixed-the-code-before-i-saw-it
- **Repository:** https://github.com/EveryInc/every-marketplace
- **Documentation:** See individual command files in `.claude/commands/`

---

**Plugin Version:** 1.0.0
**Author:** Kieran Klaassen (kieran@every.to)
**License:** MIT
