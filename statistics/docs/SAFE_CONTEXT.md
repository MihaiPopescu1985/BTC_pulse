# SAFE_CONTEXT.md (NEVER DELETE OR MODIFY THIS FILE)

## Design Memory — Canon

---

## 0) Invarianta SAFE

SAFE este un sistem pentru BTC construit pe **probabilități + regimuri + managementul expunerii**, nu pe predicții punctuale sau semnale rigide.

Întrebarea centrală:
> „Cât risc are sens să îmi asum ACUM, condiționat de starea pieței?”

Dacă SAFE devine un generator de semnale BUY/SELL discrete, **nu mai este SAFE**.

---

## 1) Scop și adevăr canonic

- Codul + output-urile pipeline-ului sunt *source of truth*.
- Acest fișier păstrează **deciziile ireversibile** din spatele codului.
- SAFE este construit pentru **controlul riscului**, nu pentru maximizarea profitului punctual.

---

## 2) Filosofie de modelare

### 2.1 Piața ca sistem viu
BTC este tratat ca un sistem cu comportament variabil în timp.
Optimizările locale agresive sunt suspecte.

### 2.2 Regimuri > Indicatori
Regimurile sunt **stări latente probabilistice**, nu etichete absolute.
HMM este un instrument, nu un scop.

### 2.3 Probabilități calibrate > scoruri frumoase
Calibrarea și stabilitatea sunt prioritare față de accuracy brut.

---

## 3) Pipeline conceptual

1. Feature engineering (returns, vol, trend, stress)
2. Regime detection (HMM, probabilități)
3. Hazard / touch probabilities (event-based)
4. Exposure engine (capital-aware)
5. Scores (citire rapidă)

Output-ul final operațional este **target exposure**, nu prețul viitor.

---

## 4) Exposure ca obiectiv final

SAFE produce:
- expunere țintă ∈ [0,1]
- ajustări graduale
- acțiuni explicabile (NO ACTION / INCREASE / DECREASE)

Bias curent: **long-only**, cu throttling de risc.

---

## 5) Vizualizare

- Un singur dashboard HTML (ECharts)
- Preț + regimuri + scoruri
- Explicații scurte, non-emoționale

UI-ul este pentru *înțelegere*, nu pentru stimularea acțiunii impulsive.

---

## 6) Principii SAFE-grade

1. No look-ahead leakage
2. Stabilitate temporală
3. Calibrare > accuracy
4. Auditabilitate
5. Conservatorism implicit
6. Regime-awareness

---

## 7) Ce este esențial și nu trebuie pierdut

- SAFE ≠ signal generator
- SAFE ≠ predicție punctuală
- SAFE = distribuții condiționate + risc controlat
- Expunerea este continuă, nu binară

---

## 8) Decizii RESPINSE (canonice)

Aceste decizii au fost evaluate și **respinse intenționat**.
Reintroducerea lor ar schimba identitatea SAFE.

### 8.1 Predicție punctuală de preț
- Motiv respingere: fragilitate, overfitting, false certainty.

### 8.2 Clasificare hard (regim unic activ)
- Motiv: pierdere de informație probabilistică.
- SAFE operează pe distribuții, nu pe etichete.

### 8.3 Optimizare agresivă pe backtest
- Motiv: instabilitate out-of-sample.
- Preferință: robustețe cross-regime.

### 8.4 Indicatori tehnici clasici ca semnale
- Motiv: redundanță informațională.
- Indicatorii pot exista doar ca features, nu ca decizie finală.

### 8.5 Automatizare opacă (black-box ML)
- Motiv: lipsă auditabilitate.
- SAFE trebuie explicat pas cu pas.

### 8.6 Short implicit sau simetric long/short
- Motiv: BTC are drift structural pozitiv.
- Short-ul este o extensie separată, nu nucleu.

---

## 9) Lecții operaționale

- UI-ul poate fi ușor degradat de explicații prost plasate.
- Pipeline-ul trebuie rulat complet pentru consistență.
- Modelele pre-antrenate pot masca lipsa de date dacă nu sunt verificate explicit.

---

## 10) Definition of Done pentru schimbări majore

O schimbare este acceptată dacă:
- poate fi explicată simplu
- respectă invarianta SAFE
- nu introduce leakage
- îmbunătățește calibrarea sau claritatea
- nu este justificată exclusiv prin profit istoric

---

Acest fișier este destinat **continuității conceptuale**.
Codul poate evolua; aceste decizii definesc identitatea SAFE.
