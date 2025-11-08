---
status: resolved
priority: p3
issue_id: "031"
tags: [code-quality, pep8, imports, imap]
dependencies: []
---

# Import Organization Violations

## Problem Statement

Importing modules inside methods (`import re`, `from time import sleep`) violates PEP 8 and is inefficient.

**Locations:** `auth/imap.py:125, 331, 592`

## Solution

Move all imports to module top:

```python
# At top of file:
import re
from time import sleep
from datetime import timedelta

# Remove all inline imports
```

**Effort:** 15 minutes
