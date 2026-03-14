
# Candlestick Research Toolkit — Manual de interpretare

Acest manual descrie complet pipeline‑ul curent:

1. Generatorul de features + outcomes din OHLC  
2. Motorul de similarity search pe intervale (v4)  
3. Cum se interpretează numeric rezultatele  
4. Cum se folosesc practic în research și live

---

# 1. Pipeline conceptual

## Etapa 1 — Feature Engineering din OHLC
Script: candles_btc_features.py  
→ transformă OHLC în vectori matematici comparabili între epoci.

## Etapa 2 — Interval Similarity Search
Script: candlestick_research_tool_v4.py  
→ caută în istoric intervale cu formă matematic similară.

---

# 2. Candlestick Features — Ce înseamnă fiecare componentă

## Componente brute

### range_size
H − L  
Cât spațiu total a explorat prețul.

### net_move
C − O  
Rezultatul net al luptei.

### upper_shadow_size
H − max(O, C)  
Respingeri sus.

### lower_shadow_size
min(O, C) − L  
Respingeri jos.

---

# 3. Normalizări — Elimină dependența de nivelul prețului

## pct_*  (normalizare la close anterior)

pct_range_size  
pct_net_move  
pct_upper_shadow_size  
pct_lower_shadow_size  

Interpretare:
- 0.01 ≈ 1% din preț
- comparabil între 2017 și 2026

---

# 4. Shape fractions — Forma lumânării

## frac_body
|C − O| / (H − L)

Interpretare:
0 → doji  
1 → marubozu  

## frac_upper_shadow
Shadow sus / Range  

## frac_lower_shadow
Shadow jos / Range  

## direction_sign
-1 → bearish  
+1 → bullish  

---

# 5. Outcomes — Ce s-a întâmplat după

## fwd_logret_k
ln(C[t+k] / C[t])

## mfe_k
Max upside în următoarele k zile

## mae_k
Max downside în următoarele k zile

---

# 6. Similarity Engine — Ce compară efectiv

Compară vectorul:

[pct_range, pct_move, pct_wicks, frac_shape, direction]  
× fiecare zi din interval

---

# 7. Similarity — Definiție actuală

similarity = exp( − distance / τ )

τ = mediană distanțe istorice (default)

Important:
Similarity NU este procent vizual.  
Este scor probabilistic de proximitate.

Regulă aproximativă:

> 0.70 → aproape identic  
0.50 → foarte similar  
0.30 → similar general  
< 0.20 → slab relevant  

---

# 8. interval_matches.csv — Interpretare câmpuri

cand_start_index — start interval istoric  
cand_end_index — end interval istoric  
start_ts — start date istoric  
end_ts — end date istoric  

time_gap_days — distanță în timp față de query  

distance — distanță matematică brută  
similarity — scor convertit (0 → 1)

Outcome columns:
fwd_logret_k  
mfe_k  
mae_k  

---

# 9. meta.json — Interpretare

seq_len — lungime interval analizat  
metric — tip distanță (euclidean/cosine/mahalanobis)  
tau_value — scala similarității  
candidate_count — câte intervale au fost analizate  
match_count — câte au trecut filtrul similarity  

---

# 10. report.html — Ce vezi vizual

1. Meta parameters  
2. Outcome summary statistic  
3. Interval query  
4. Matches table filtrabil  
5. Overlay charts normalizate la 1.0  

---

# 11. Cum interpretezi practic

## Similarity mare + multe matchuri
→ pattern stabil

## Similarity mare + puține matchuri
→ pattern rar dar valid

## Similarity mic
→ pattern nou / regim nou

---

# 12. Parametri practici

min_sim:
0.5 → strict  
0.35 → research  
0.25 → exploratory  

---

# 13. Live usage logic

Dacă:
Similarity > 0.5  
și  
Outcomes skew pozitiv  

→ probabilitate bună de repeat behaviour.

---

# 14. Limitări

Nu prezice.  
Nu vede macro.  
Nu vede news.  

Este pattern statistics engine.

---

# 15. Mental model corect

Nu întrebi:
“Ce se va întâmpla?”

Întrebi:
“Când piața a arătat așa — ce s-a întâmplat de obicei?”

---

# 16. Interpretare rapidă în 5 secunde

Vezi:
Similarity  
Match count  
Outcome median  
MFE vs MAE  

---

# 17. Dacă nu există matchuri

Înseamnă:
Pattern nou  
sau  
Prag similarity prea strict  

---

# Final

Acest sistem este un motor de analogie statistică pe comportament de piață,
nu un predictor determinist.

