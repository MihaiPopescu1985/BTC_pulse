
# Candlestick Similarity Engine — Cheat Sheet

---

## What It Answers
"When market looked like THIS before → what happened NEXT?"

---

## Core Signals

Similarity ↑ = better analog
Match Count ↑ = stronger statistical confidence

---

## Quick Interpretation

Similarity > 0.70 → near clone
0.50 – 0.70 → strong analog
0.30 – 0.50 → usable analog
< 0.30 → weak analog

---

## Outcome Reading

Check:
Median forward return
Winrate
MFE vs MAE

---

## Fast Decision Flow

1️⃣ Enough matches?  
2️⃣ Positive outcome skew?  
3️⃣ MFE > MAE?  

→ If YES → strong historical bias

---

## Parameter Tuning

Too few matches → lower min_sim  
Too many matches → raise min_sim  

---

## Danger Signs

Few matches + high variance  
Mixed outcome distribution  
Regime shift periods  

---

## Mental Model

NOT prediction
IS statistical precedent search

---

## 5-Second Scan

Similarity
Match Count
Median Return
MFE / MAE

---

