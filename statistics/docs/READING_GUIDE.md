# READING GUIDE — Conversație ghidată

## SAFE pe scurt

SAFE nu este o „cristal ball” care prezice prețul. SAFE este un instrument de context: îți spune în ce fel de piață te afli și cât de mult risc e rezonabil să îți asumi.

### O analogie bună

Imaginează-ți că ești șofer și vrei să ajungi din A în B.

- Prețul BTC = drumul (urcări/coborâri, gropi, serpentine)
- SAFE = prognoza meteo + starea asfaltului, nu GPS-ul

SAFE nu îți spune exact:

> „mâine la ora 12:00 vei fi la km X”

Ci îți spune:

> „e ceață și polei” → mergi mai încet (reduci expunerea)  
> „cer senin și drum uscat” → poți merge normal (crești expunerea)

### Ce înseamnă „regimurile” în termeni simpli

SAFE împarte piața în 4 stări de comportament, nu în 4 predicții:

- **CORE:** piață relativ stabilă, „normală” pentru perioade lungi
- **DRIFT:** stabilă, dar cu o direcție ușoară (fără promisiuni)
- **SURGE:** mișcare puternică, volatilitate mare (poate fi în sus)
- **SHOCK:** stres, volatilitate mare (de obicei în jos)

**Important:**
- în realitate, piața poate arăta parțial ca mai multe stări în același timp
- SAFE arată aceste stări ca probabilități, nu ca „comutatoare”

### Ce face SAFE cu informația asta

SAFE nu îți spune „cumpără/vinde” ca un influencer.

SAFE îți spune:

> „În acest context, riscul e X. Expunerea recomandată e Y.”

Adică este un allocator de risc, nu un „trader de semnale”.

### Ce promite și ce NU promite (foarte important)

**✅ Promite:**
- o descriere coerentă a contextului
- reducerea riscului în perioade periculoase
- consistență și transparență (audit pe indicatori)

**❌ NU promite:**
- că bate mereu Buy&Hold
- că prinde minimele și maximele
- profit garantat

### Cum verifici că nu e „poveste frumoasă”

SAFE are două dovezi simple, explicabile:
- are validare internă (contract de date, consistență HMM)
- în backtest walk-forward, reduce drawdown și crește Sharpe, fără să „ghicească” viitorul

## Analiza indicatorilor

### Cadrul SAFE de analiză a unui indicator

Pentru fiecare indicator, răspundem disciplinat la aceleași întrebări, în această ordine:

1. **Ce încearcă să măsoare indicatorul? (intenția)**
   - Nu „cum se calculează”, ci: ce fenomen al pieței vrea să surprindă?
   - Este despre direcție, volatilitate, risc, timing, context?
   - Exemplu generic: „Indicatorul X încearcă să spună dacă piața este tensionată sau relaxată.”
   - Dacă nu putem formula asta într-o propoziție clară → indicatorul e suspect.

2. **Ce NU măsoară explicit? (limitările)**
   - Ce NU ar trebui să așteptăm de la el?
   - Ce întrebări nu poate răspunde?
   - Exemplu: „Acest indicator nu știe dacă prețul va crește mâine, doar dacă riscul e mare.”
   - Asta ne protejează de interpretări greșite.

3. **Care este comportamentul „normal”?**
   - Cum arată indicatorul într-o piață calmă, trend clar, range, stres extrem?
   - Nu numeric, ci calitativ: stabil/instabil, lent/rapid, zgomotos/neted.
   - Exemplu: „Într-o piață calmă, indicatorul ar trebui să fie relativ stabil și să nu oscileze violent.”
   - Dacă realitatea contrazice asta → ceva e greșit.

4. **Ce relație ne așteptăm să aibă cu randamentul?**
   - Nu toate indicatorii trebuie să fie corelați cu randamentul.
   - Ar trebui să fie corelat pozitiv, corelat negativ, deloc corelat?
   - Pe ce orizont: imediat, 5–10 zile, doar în anumite regimuri?
   - Exemplu: „Indicatorul de risc nu trebuie să fie corelat cu randamentul, ci cu drawdown-ul.”

5. **Cum interacționează cu alți indicatori?**
   - Are sens doar în combinație cu altul?
   - Își schimbă semnificația în funcție de regim?
   - Poate valida, filtra, tempera, amplifica?
   - Exemplu: „Un semnal de rebound are sens doar dacă regimul nu este SHOCK.”

6. **Este un indicator de:**
   - context (descrie mediul)
   - decizie (intră direct în policy)
   - explicație (ajută omul să înțeleagă)

   Un indicator poate fi foarte bun la explicație și prost la decizie (exact ce ai observat cu E_target_safe).
   SAFE face separarea explicită a acestor roluri.

7. **Ce așteptări REALISTE avem de la el?**
   - Formulăm o propoziție de genul: „Dacă indicatorul X crește, ne așteptăm ca Y să se întâmple, nu garantat, ci ca tendință statistică.”
   - Dacă nu putem formula asta → indicatorul nu e încă „înțeles”.

## 1️⃣ Randamentul — fundamentul SAFE

### Ce este randamentul, în sensul SAFE (nu matematic)

În SAFE, randamentul nu este „cât câștig”, ci:
- unitatea elementară de mișcare a pieței

Prețul este poziția. Randamentul este mișcarea dintre două poziții. Asta este o distincție crucială.

### 1.1 Ce încearcă să măsoare randamentul?

Randamentul măsoară:
- schimbarea relativă a valorii
- viteza locală a pieței
- direcția instantanee (sus / jos)
- intensitatea mișcării

SAFE nu „vede” piața ca o linie de prețuri, ci ca o succesiune de pași.
Fiecare zi spune: „Astăzi piața a făcut un pas de mărimea X, în direcția Y.”

### 1.2 Ce NU măsoară randamentul (foarte important)

Randamentul NU știe:
- unde este piața „scumpă” sau „ieftină”
- dacă trendul este sustenabil
- dacă urmează un rebound
- dacă suntem într-un regim periculos

Cu alte cuvinte: randamentul nu este context, este eveniment.
De aceea SAFE nu ia decizii doar pe baza randamentului.

### 1.3 De ce SAFE pornește de la randament, nu de la preț

**Problema prețului (fundamentală):**
- nu este staționar
- nu are scară fixă
- crește exponențial în timp (BTC)

A compara BTC la 1.000 cu BTC la 50.000 nu are sens direct.

**Ce rezolvă randamentul:**
- normalizează mișcările
- face datele comparabile în timp
- separă „mărimea mișcării” de „nivelul prețului”

În SAFE: două zile cu +3% sunt comparabile, indiferent dacă BTC era la 300$ sau 30.000$.

### 1.4 De ce randament logaritmic, conceptual (fără formule)

Fără să intrăm în matematică: randamentul logaritmic are 3 proprietăți esențiale pentru SAFE:

1. **Simetrie**
   - +10% urmat de −10% ≠ 0 (în randament simplu)
   - în randament logaritmic, mișcările se „echilibrează” corect
   - SAFE are nevoie de această simetrie pentru evaluarea riscului și agregarea mișcărilor

2. **Aditivitate în timp**
   - Randamentele logaritmice se adună natural pe zile
   - Asta permite calcul de trend, calcul de volatilitate și modelare HMM
   - SAFE folosește masiv această proprietate

3. **Aproximare locală foarte bună**
   - Pentru mișcări zilnice (1–5%), randamentul log ≈ randamentul simplu
   - Nu pierdem intuiția, dar câștigăm proprietăți matematice solide

### 1.5 Ce ne așteptăm să „spună” randamentul

Nu ne așteptăm ca randamentul să:
- prezică viitorul
- fie stabil
- fie „frumos”

Ne așteptăm ca el să fie:
- zgomotos
- cu cozi groase
- clusterizat în volatilitate
- asimetric în crize

Faptul că ai văzut „zgomot” în graficul randamentului este un semn bun, nu rău.
Din zgomotul randamentelor se nasc TOATE celelalte structuri.

### 1.6 Relația randamentului cu ceilalți indicatori

Randamentul este:
- **input pentru:** TS_50, volatilitate (band_w), HMM
- **referință pentru:** hazard (corecție / rebound)

Dar randamentul singur NU este decizie. El este materia primă.

### 1.7 Așteptarea realistă (formulată clar)

O propoziție SAFE-grade:

> „Randamentul zilnic ne spune cât și în ce direcție s-a mișcat piața, dar nu ne spune nimic despre context sau risc. SAFE folosește randamentul doar ca bază pentru a construi indicatori de context.”

Dacă cineva se așteaptă la mai mult de atât de la randament → îl va interpreta greșit.

### De ce acest pas este crucial

Dacă nu înțelegi randamentul:
- vei cere prea mult de la indicatori
- vei confunda zgomotul cu semnalul
- vei ajunge la „indicatori care mint”

SAFE evită asta pornind de la: un atom corect definit.

## 2️⃣ TS_50 — ce înseamnă „trend” în SAFE (și ce NU înseamnă)

În SAFE, TS_50 nu este un indicator de buy/sell. Este un indicator de context direcțional, construit din randamente, nu din preț.

### 2.1 Ce încearcă să măsoare TS_50? (intenția)

TS_50 (Trend Strength pe ~50 zile) încearcă să răspundă la o singură întrebare:

> „Există o direcție persistentă în mișcările recente ale pieței?”

Nu:
- „prețul e sus/jos”
- „trendul va continua”
- „suntem într-un bull market”

Ci strict: „Pașii zilnici, luați împreună, au o direcție dominantă?”

Este o măsură a biasului direcțional, nu a nivelului.

### 2.2 Ce NU măsoară TS_50 (foarte important)

TS_50 NU măsoară:
- dacă piața e scumpă sau ieftină
- dacă trendul e „bun” sau „sănătos”
- dacă urmează o inversare
- amplitudinea mișcării viitoare

De aceea:
- un TS_50 pozitiv NU înseamnă „cumpără”
- un TS_50 negativ NU înseamnă „vinde”

Este descriere, nu decizie.

### 2.3 De ce TS_50 e construit din randamente, nu din preț

Un SMA clasic răspunde la: „unde este prețul față de trecut?”

TS_50 răspunde la: „în ce direcție s-au acumulat mișcările?”

Diferența e subtilă, dar critică:
- poți avea preț sus fără trend (range)
- poți avea trend fără preț extrem

TS_50 vede coerența pașilor, nu poziția absolută.

### 2.4 Comportamentul „normal” al TS_50

**Piață calmă / range**
- TS_50 ≈ 0
- oscilează ușor
- semn schimbător

**Trend susținut**
- TS_50 > 0 pentru perioade lungi
- schimbări lente
- puțin zgomot

**Trend descendent**
- TS_50 < 0
- persistent negativ

**Stres / volatilitate extremă**
- TS_50 poate rămâne mic
- sau poate deveni extrem după șoc, nu înainte

**Observație importantă:** TS_50 reacționează, nu anticipează.

### 2.5 Relația așteptată cu randamentul

- Corelație slab pozitivă, pe termen mediu
- Foarte slabă pe termen scurt
- Inutil pentru „mâine”

De aceea TS_50: ajută la filtrare, NU ajută la timing.

### 2.6 Interacțiunea cu alți indicatori (SAFE mindset)

TS_50 devine interesant doar în combinație:
- TS_50 + band_w mic → trend calm, sustenabil
- TS_50 + band_w mare → trend tensionat, risc de șoc
- TS_50 pozitiv + SHOCK → contradicție → atenție

TS_50 singur nu decide nimic, dar schimbă interpretarea celorlalți indicatori.

### 2.7 Rolul lui TS_50 în SAFE

Clasificare clară:
- nu este indicator de decizie
- nu este predictor
- este context direcțional

În SAFE:
- ajută conviction_safe
- temperează sau susține entry_step_safe
- explică „de ce” o expunere e mai mare sau mai mică

### 2.8 Așteptarea realistă (formulată corect)

O propoziție SAFE-grade:

> „TS_50 ne spune dacă mișcările recente ale pieței au avut o direcție consistentă, dar nu ne spune nimic despre riscul sau durata acelui trend.”

Dacă cineva cere mai mult de la TS_50 → îl va folosi greșit.

### De ce acest pas contează

Mulți confundă: trend = predicție.
SAFE spune: trend = context acumulat, nimic mai mult.
De aici vine robustețea.

### Următorul pas

Dacă ești de acord, continuăm cu:

👉 3️⃣ band_w — ce înseamnă volatilitatea „contextuală” și de ce nu este VIX

Spune-mi și mergem mai departe.

> **User:** Desigur, continuam

## 3️⃣ band_w — volatilitatea contextuală (nu VIX, nu ATR)

band_w este unul dintre cei mai ușor de interpretat greșit indicatori, tocmai pentru că „volatilitate” pare un concept familiar. În SAFE, însă, el are un rol foarte specific.

### 3.1 Ce încearcă să măsoare band_w? (intenția)

band_w încearcă să răspundă la întrebarea:

> „Cât de larg este spațiul în care se mișcă prețul, raportat la comportamentul recent?”

Nu:
- „cât de mult a crescut/scăzut prețul”
- „cât de riscant e mâine”
- „suntem într-o criză”

Ci: „Cât de relaxat sau tensionat este mediul de mișcare?”
Este o măsură de tensiune a contextului, nu de direcție.

### 3.2 Ce NU măsoară band_w

band_w NU măsoară:
- direcția pieței
- randamentul așteptat
- probabilitatea unui eveniment anume
- dacă volatilitatea va crește sau scădea

Cu alte cuvinte: band_w nu prezice nimic, descrie lățimea cadrului în care piața se mișcă acum.

### 3.3 De ce „contextuală” și nu volatilitate brută

Volatilitatea clasică (ATR, std dev simplu):
- se uită doar la mărimea mișcărilor
- ignoră unde se află prețul în propria distribuție

band_w este diferit:
- este legată de benzi construite din comportamentul recent
- spune dacă piața „respiră larg” sau „merge pe o sârmă întinsă”

Două piețe pot avea:
- aceeași volatilitate numerică
- band_w diferit, pentru că una e într-un regim calm, cealaltă într-unul tensionat

### 3.4 Comportamentul „normal” al band_w

**Piață calmă / CORE**
- band_w mic
- se modifică lent
- puțin zgomot

**Trend stabil**
- band_w moderat
- crește ușor în trenduri sănătoase
- rămâne controlat

**Stres / SHOCK / SURGE**
- band_w mare
- variații rapide
- semn clar de „piață nervoasă”

**Observație-cheie:** creșterea band_w precede adesea deteriorarea contextului, dar nu spune cum se va manifesta.

### 3.5 Relația așteptată cu randamentul

- Corelație slabă sau zero cu randamentul mediu
- Corelație puternică cu drawdown, dispersia randamentelor, schimbări de regim

Exact cum ai observat: band_w ajută Sharpe și MDD, nu CAGR direct.

### 3.6 Interacțiunea cu alți indicatori (foarte important)

band_w este un amplificator de sens pentru alți indicatori:
- TS_50 mare + band_w mic → trend calm, „respirabil”
- TS_50 mare + band_w mare → trend tensionat, risc de revers
- band_w mare + P_CORRECTION_10D mare → risc asimetric, nu merită agresivitate
- band_w mare + HMM_CONF mic → tranziție de regim, incertitudine

Singur, band_w nu spune ce să faci. În combinație, spune cât de mult să ai încredere în ce spun ceilalți.

### 3.7 Rolul lui band_w în SAFE

Clasificare clară:
- nu este predictor
- nu este semnal
- este indicator de tensiune contextuală

În SAFE:
- reduce expunerea în medii fragile
- temperează entry_step_safe
- explică de ce SAFE „nu intră tare” chiar dacă trendul există

### 3.8 Așteptarea realistă (formulată corect)

O propoziție SAFE-grade:

> „band_w ne spune cât de larg și instabil este mediul de mișcare al pieței, nu în ce direcție se va mișca.”

Dacă cineva îl folosește ca semnal direcțional → îl va interpreta greșit.

### De ce acest indicator e crucial pentru SAFE

Fără band_w:
- SAFE ar deveni un sistem „trend-only”
- drawdown-ul ar exploda
- SHOCK și SURGE ar fi tratate la fel

band_w este unul dintre motivele principale pentru care SAFE bate riscul, chiar când nu bate CAGR.

### Următorul pas

Dacă ești de acord, continuăm cu:

👉 4️⃣ band_pos — poziționarea relativă în context (nu „overbought/oversold”)

Spune-mi și mergem mai departe.

> **User:** Desigur, continuam

## 4️⃣ band_pos — poziționarea relativă în context

*(nu „overbought / oversold”, nu semnal de revers)*

band_pos este probabil indicatorul care produce cele mai multe erori de interpretare la prima vedere, pentru că seamănă cu oscilatorii clasici. În SAFE, rolul lui este complet diferit.

### 4.1 Ce încearcă să măsoare band_pos? (intenția)

band_pos răspunde la întrebarea:

> „Unde se află prețul curent în propriul său spațiu de variație recent?”

Nu:
- unde se află față de „valoare”
- unde se află față de un maxim istoric
- dacă este supraevaluat sau subevaluat

Ci strict: poziție relativă în contextul definit de benzile recente.
Este un indicator de geometrie locală, nu de valoare.

### 4.2 Ce NU măsoară band_pos

band_pos NU măsoară:
- dacă prețul „trebuie” să scadă sau să crească
- probabilitatea unei corecții
- epuizarea trendului
- momentum

Prin urmare:
- band_pos mare ≠ vinde
- band_pos mic ≠ cumpără

În SAFE, aceste interpretări sunt greșite.

### 4.3 Cum trebuie „citit” corect band_pos

band_pos ≈ 0 → prețul este aproape de limita inferioară a contextului recent

band_pos ≈ 0.5 → prețul este în zona mediană a distribuției recente

band_pos ≈ 1 → prețul este aproape de limita superioară a contextului recent

Fără judecată, fără predicție.

### 4.4 Comportamentul „normal” al band_pos

**Piață calmă / CORE**
- oscilează regulat între 0 și 1
- mișcări lente
- mult timp în jurul lui 0.5

**Trend stabil**
- stă mult timp aproape de 1 într-un trend ascendent
- stă mult timp aproape de 0 într-un trend descendent

**Observație-cheie:** trendurile sănătoase NU revin des la mijloc.
De aceea, band_pos nu e semnal de revers.

**Stres / SHOCK / SURGE**
- poate „sări” violent între extreme
- devine instabil
- își pierde semnificația dacă band_w e mare

### 4.5 Relația așteptată cu randamentul

- Corelație slabă sau zero cu randamentul viitor
- Corelație puternică cu poziționarea în trend și distribuția mișcărilor

Exact ce ai văzut în testele tale: band_pos ajută în combinație, nu decide nimic singur.

### 4.6 Interacțiuni-cheie cu alți indicatori

**band_pos + TS_50**
- TS_50 > 0 și band_pos mare → trend „bine așezat”, nu e semnal de vânzare
- TS_50 ≈ 0 și band_pos extrem → poziționare fragilă, risc de revenire

**band_pos + band_w**
- band_pos extrem + band_w mic → poziționare stabilă
- band_pos extrem + band_w mare → poziționare instabilă, risc ridicat

**band_pos + HMM**
- band_pos mare în CORE → normal
- band_pos mare în SHOCK → contradicție → prudență

### 4.7 Rolul lui band_pos în SAFE

Clasificare clară:
- nu este semnal
- nu este predictor
- este indicator de poziționare contextuală

În SAFE:
- ajută la interpretarea trendului
- temperează deciziile agresive
- explică de ce o expunere este sau nu justificată

Este un „modulator”, nu un declanșator.

### 4.8 Așteptarea realistă (formulată corect)

O propoziție SAFE-grade:

> „band_pos ne spune unde se află prețul în propriul său interval recent, dar nu ne spune dacă acel interval se va rupe sau va rezista.”

### De ce acest indicator e important (chiar dacă nu e spectaculos)

Fără band_pos:
- SAFE ar pierde geometria locală a prețului
- trendurile ar fi interpretate prea simplist
- explicațiile pentru decizii ar fi mai slabe

band_pos este unul dintre indicatorii care nu impresionează, dar menține corectitudinea.

### Următorul pas

Dacă ești de acord, continuăm cu:

👉 5️⃣ P_CORRECTION_10D — ce înseamnă „risc de corecție” în SAFE (și ce NU înseamnă)

Spune-mi și mergem mai departe.

> **User:** Continuam!

## 5️⃣ P_CORRECTION_10D — „risc de corecție” în SAFE

*(nu predicție, nu timing, nu semnal de vânzare)*

Acesta este primul indicator din SAFE care sună periculos dacă este interpretat superficial. De aceea e esențial să-l fixăm conceptual foarte clar.

### 5.1 Ce încearcă să măsoare P_CORRECTION_10D? (intenția)

P_CORRECTION_10D încearcă să răspundă la întrebarea:

> „Cât de probabil este ca, în următoarele ~10 zile, piața să experimenteze o mișcare adversă semnificativă?”

Cheile sunt:
- probabilitate, nu certitudine
- adversă, nu neapărat trend descendent
- interval, nu zi exactă

Este un indicator de hazard, nu de direcție.

### 5.2 Ce NU măsoară P_CORRECTION_10D

P_CORRECTION_10D NU spune:
- „prețul va scădea mâine”
- „trendul s-a terminat”
- „trebuie să vinzi acum”
- „urmează crash”

Prin urmare:
- un P_CORRECTION_10D mare NU este un semnal de short
