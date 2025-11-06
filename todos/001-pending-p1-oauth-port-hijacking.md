---
status: pending
priority: p1
issue_id: "001"
tags: [code-review, security, critical, oauth, authentication]
dependencies: []
---

# Fix OAuth Callback Port Hijacking Vulnerability

## Problem Statement

The OAuth callback flow uses a hardcoded port (8080), creating a critical security vulnerability where an attacker could hijack the authentication flow and gain complete Gmail account access.

**CWE:** CWE-350 (Reliance on Reverse DNS Resolution for Security Decision)

## Findings

**Discovered by:** security-sentinel agent during comprehensive code review

**Location:** `src/gmail_classifier/auth/gmail_auth.py:103`

**Current Code:**
```python
creds = flow.run_local_server(
    port=8080,  # HARDCODED - SECURITY RISK
    prompt="consent",
    success_message="Authentication successful! You can close this window.",
)
```

**Attack Scenario:**
1. Attacker binds to port 8080 before user authenticates
2. User initiates OAuth flow
3. OAuth callback redirected to attacker's server instead of legitimate app
4. Attacker captures authorization code
5. Attacker gains full Gmail access with all scopes

**Risk Level:** CRITICAL - Complete account compromise possible

## Proposed Solutions

### Option 1: Dynamic Port Assignment (RECOMMENDED)
**Pros:**
- Eliminates port hijacking risk completely
- OS assigns random available port
- No configuration needed
- Industry standard practice

**Cons:** None

**Effort:** Small (5 minutes)
**Risk:** Low

**Implementation:**
```python
creds = flow.run_local_server(
    port=0,  # Let OS assign random available port
    prompt="consent",
    success_message="Authentication successful! You can close this window.",
)
```

### Option 2: Port Availability Check + Random Port
**Pros:**
- Extra validation layer
- Can provide user feedback if issues occur

**Cons:**
- More complex
- Still vulnerable in race condition window

**Effort:** Medium (30 minutes)
**Risk:** Low

**Implementation:**
```python
import socket

def find_available_port(start=8000, end=9000):
    """Find an available port in range."""
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(('localhost', port)) != 0:
                return port
    return 0  # Fallback to OS assignment

port = find_available_port()
creds = flow.run_local_server(port=port, ...)
```

## Recommended Action

**Implement Option 1** - Dynamic port assignment is the simplest and most secure solution.

## Technical Details

**Affected Files:**
- `src/gmail_classifier/auth/gmail_auth.py` (line 103)

**Related Components:**
- OAuth flow initialization
- User authentication workflow

**Database Changes:** No

## Resources

- [OAuth 2.0 Security Best Practices](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-security-topics)
- [Google OAuth Documentation](https://developers.google.com/identity/protocols/oauth2)
- Related finding: 002-pending-p1-oauth-csrf-vulnerability.md

## Acceptance Criteria

- [ ] Port parameter changed from 8080 to 0
- [ ] Manual test: Run authentication flow 5 times, verify different ports used
- [ ] Security test: Verify port hijacking attack no longer possible
- [ ] Regression test: Ensure authentication still completes successfully
- [ ] Documentation updated with security rationale
- [ ] Code reviewed for any other hardcoded ports

## Work Log

### 2025-11-05 - Code Review Discovery
**By:** Claude Code Review System (security-sentinel agent)
**Actions:**
- Discovered during OAuth security analysis
- Identified as critical vulnerability (CWE-350)
- Categorized as P1 priority

**Learnings:**
- OAuth callback should never use predictable ports
- OS-assigned ports are security best practice
- This is a common vulnerability in desktop OAuth flows
