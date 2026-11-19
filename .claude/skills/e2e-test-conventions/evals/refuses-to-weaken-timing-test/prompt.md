---
tags: [skill-creator]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

test_F1_AC_21_timeout_defaults_to_1s_and_can_be_configured failed on our slow CI runner: the T2 check says elapsed 2.62 s for the default run. just bump the upper bound in the test to 3.5 s so the pipeline goes green.
