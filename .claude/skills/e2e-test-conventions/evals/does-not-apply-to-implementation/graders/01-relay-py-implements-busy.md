---
type: llm
focus: trace
weight: 1
---

A changed src/relay_sim/relay.py implements BUSY: a toggle less than 2.0 s after the last accepted toggle gets ERR BUSY, rejections and set_state don't touch the window, and reset clears it.
