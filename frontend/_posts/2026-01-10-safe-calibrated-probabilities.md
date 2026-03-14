---
layout: post
title: "SAFE Update - Better Calibrated Probabilities"
date: 2026-01-10
author: BTC Pulse
description: "SAFE now models regime dynamics for better calibrated touch probabilities."
---

We have made a major upgrade to the SAFE engine.

Until now, price touch probabilities (+2%, +5%, +/-10% in N days) were calculated assuming an "average" distribution of returns.

Now, SAFE explicitly models market regimes and the transitions between them.

### What this means in practice

- The market is no longer treated as "the same every day".
- A regime (range, down fast, low vol, etc.) can persist or change with a certain probability.
- Simulations respect this dynamic, not just raw statistics.

### Validation

We validated the upgrade strictly statistically, using Brier score on events (touch / no-touch), not PnL.

**Result:** better calibrated probabilities, especially for rare events and longer horizons.

### What stays the same

- The daily output looks the same.
- The interpretation remains the same.

But what is behind it is now a process model, not just a distribution.

Small change in numbers. Big change in meaning.

Also, the model was retrained, therefore small adjustments will be visible in the chart.

Stay SAFE!
