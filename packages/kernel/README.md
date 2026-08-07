# packages/kernel

Reserved for the future deRek Kernel implementation.

The Kernel is the common core that every deRek AI OS capability (AI
providers, tasks, events, agents, memory, plugins, and beyond) plugs
into. This package is intentionally empty in v0.0.1 — the current
release ships the project foundation only (API skeleton + dashboard
skeleton); no kernel code is implemented yet. Keeping this directory
in the repo now fixes the workspace layout so future work lands in
the right place without a restructure.

> Formerly `packages/core`. Renamed to `packages/kernel` in Sprint 001
> to match the project's Kernel-centric architecture — every future
> capability plugs into this package.
