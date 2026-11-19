# U9 keyboard and motion (2026-11-06)
- Tab order from History select: Live checkbox → Ethernet/Wi-Fi Data table → Tailscale Data table → sda Data table → System details summary → workload Filter → Service state → CPU cores → Memory (matches visual order).
- Enter on "Memory" sets aria-pressed=true; Space on "CPU cores" sets aria-pressed=true; Enter on a Data table summary opens it.
- Focus ring on summary: solid 2px.
- prefers-reduced-motion: reduce → ranked bar transition "all 0s"; no-preference → "transform 0.4s". Bars scale via transform: scaleX, never width.
