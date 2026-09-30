---
description: Audit the ShieldLabs integration in this project and report problems by severity
argument-hint: "[folder or files to focus on]"
---

Use the shieldlabs-setup skill in audit mode on this project.

Focus from the user: $ARGUMENTS

1. Run the skill's `scripts/audit_scan.py` on the project root (or the focus folder), or use the
   search patterns in the skill's `references/audit.md` when Python is not available.
2. Read the code around every finding and drop false positives.
3. Check by hand what the scan cannot see, from the list in `references/audit.md`.
4. Report the findings grouped as high, medium and low, each with file and line, why it matters
   and the fix. Change no files until the user asks; then fix the high findings first.
