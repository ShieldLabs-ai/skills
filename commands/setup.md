---
description: Integrate ShieldLabs into this project (browser identification, server-side verdict, optional webhook) and verify it
argument-hint: "[protected actions or notes, for example: signup and checkout]"
---

Use the shieldlabs-setup skill to integrate ShieldLabs into this project.

Notes from the user: $ARGUMENTS

1. Detect the stack with the skill's `scripts/detect_stack.py` (or by reading the manifests).
2. Agree on the protected actions and their sensitivity, present the integration plan from the
   skill's template, and wait for the user to confirm it before changing files. When the notes
   above already name the protected actions and what should happen, or nobody can answer (an
   automated or delegated run), print the plan with the defaults you chose for open points and
   continue.
3. Implement the steps with the matching ShieldLabs skills: browser identification, server-side
   verdict with the replay and freshness guards, the decision policy, User HIDs for signed-in
   users, and a webhook only when there is asynchronous work for it. Keep every key in environment
   variables and add placeholders to `.env.example`.
4. Finish with the skill's verification checklist. Report what passed, and what still needs a
   registered domain, keys or a deployment to check.
