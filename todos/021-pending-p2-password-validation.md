---
status: pending
priority: p2
issue_id: "021"
tags: [security, password-policy, imap, validation]
dependencies: []
---

# Insufficient Password Validation

## Problem Statement

Password validation only checks length (8-64 characters) without validating Gmail app password format or enforcing complexity requirements. This allows weak passwords and doesn't guide users toward using secure app passwords.

**CWE:** CWE-521 (Weak Password Requirements)
**Impact:** Increased brute-force risk, weak password acceptance

## Findings

**Location:** `src/gmail_classifier/auth/imap.py:132-134`

**Current Validation:**
```python
if not (8 <= len(self.password) <= 64):
    raise ValueError("Password must be between 8 and 64 characters")
```

**Missing Validations:**
- Gmail app password format (16 lowercase letters)
- Password complexity for non-app passwords
- Weak pattern detection (repeating chars, common passwords)

## Proposed Solution

```python
def _validate_password(self) -> None:
    password = self.password

    # Check for Gmail app password format (16 lowercase chars)
    clean_password = password.replace(' ', '')
    if len(clean_password) == 16 and clean_password.isalpha():
        if not clean_password.islower():
            raise ValueError("Gmail app passwords should be lowercase")
        return  # Valid app password

    # For non-app passwords, enforce stronger requirements
    if len(password) < 12:
        raise ValueError(
            "Regular passwords must be at least 12 characters. "
            "Consider using a Gmail app password instead: "
            "https://myaccount.google.com/apppasswords"
        )

    # Check complexity
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in string.punctuation for c in password)

    if sum([has_upper, has_lower, has_digit, has_special]) < 3:
        raise ValueError(
            "Password must contain at least 3 of: uppercase, lowercase, "
            "digits, special characters"
        )

    # Check for weak patterns
    if re.search(r'(.)\1{2,}', password):  # 3+ repeated chars
        raise ValueError("Password contains repeated characters")
```

## Acceptance Criteria

- [ ] Validate Gmail app password format (16 lowercase)
- [ ] Enforce 12-char minimum for non-app passwords
- [ ] Check complexity (3 of 4 character types)
- [ ] Detect weak patterns (repeated chars)
- [ ] Provide helpful error messages with app password link
- [ ] Update CLI to guide users toward app passwords
- [ ] Test: 16-char app passwords accepted
- [ ] Test: weak passwords rejected

**Effort:** 1 hour

