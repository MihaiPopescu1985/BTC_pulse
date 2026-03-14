
# Candlestick Similarity Research Engine — Technical Documentation

Version: v4 Stack  
Components:
- candles_btc_features.py
- candlestick_research_tool_v4.py

---

# 1. Problem Definition

We want to answer:

"When the market looked like this before, what statistically happened next?"

This is NOT prediction.
This is statistical analog search.

---

# 2. Data Model

## Raw Input
OHLC + timestamp

## Derived Feature Space
Per candle vector:

X = [
 pct_range_size,
 pct_net_move,
 pct_upper_shadow_size,
 pct_lower_shadow_size,
 frac_upper_shadow,
 frac_lower_shadow,
 frac_body,
 direction_sign
]

---

# 3. Interval Embedding

For interval length L:

S = concat( X_t … X_(t+L-1) )

Dimension = L × feature_count

---

# 4. Distance Metrics

## Euclidean
||x − y||₂

## Cosine
1 − cos(angle)

## Mahalanobis
Accounts for covariance structure.

---

# 5. Standardization

Z-score:
(X − mean) / std

Removes scale dominance.

---

# 6. Similarity Kernel

similarity = exp( − distance / τ )

τ = distance scale (median or p75)

---

# 7. Statistical Meaning of Similarity

Similarity ≠ visual similarity.

Similarity measures distance in multidimensional candle-behaviour space.

---

# 8. Candidate Filtering

Primary:
Similarity >= min_sim

Secondary:
Optional time_gap_days <= max_gap_days

---

# 9. Outcome Attachment

Forward evaluation anchored at interval END.

---

# 10. Statistical Interpretation

## Many high similarity matches
→ regime stable

## Few high similarity matches
→ regime rare

## No matches
→ new regime or too strict filter

---

# 11. Failure Modes

Macro shifts
Structural regime changes
Feature drift

---

# 12. Recommended Thresholds

Strict:
min_sim >= 0.5

Research:
0.35 – 0.5

Exploratory:
0.25 – 0.35

---

# 13. Practical Usage

1) Run similarity search
2) Validate outcome distribution
3) Compare MFE vs MAE skew
4) Assess sample size

---

# 14. Risk Notes

Small N → high variance
High similarity ≠ guaranteed outcome

---

# 15. Extensions

Possible future work:
Dynamic feature weighting
Regime conditional similarity
Volatility regime clustering

---

# Conclusion

This engine is a statistical behavioral analog finder, not a predictive model.

