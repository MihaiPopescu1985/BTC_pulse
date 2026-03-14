---
layout: post
title: "Range Bias Strengthens as Touch Odds Stay Two-Sided"
date: 2026-01-09
author: BTC Pulse
description: "Range-lowvol regime strengthened while on-chain activity stayed muted; touch odds remain balanced." 
---

Price slipped from 91,099.99 to 90,641.28 while remaining in the lower band zone (band_pos 0.16 to 0.15).  
The HMM regime mix tilted further toward range-lowvol (0.58 to 0.77) and away from down-fast (0.39 to 0.12), suggesting less downside intensity even as price drifted lower.


Short-horizon stats also leaned toward mean reversion: P_Rebound_10D rose slightly above P_Correction_10D, and the calibrated touch table shows a two-sided profile over 10 days (up +2%: 72%, down -2%: 62%; +5%: 51% vs -5%: 39%).  
Exposure guidance eased (E_target_safe 0.51 to 0.49) and conviction stayed low, consistent with a cautious, range-aware stance.


On-chain activity stabilized but remained muted: total amount ticked up and vol z-score improved (0.23 to 0.49), while whale share z-score slipped slightly below zero. Net signal: participation is not expanding aggressively yet.


Near-term expectation: range conditions likely persist unless on-chain volume and whale dominance accelerate meaningfully.  
The balance of touch probabilities argues for patience and tighter risk sizing rather than directional conviction.

=== SAFE Touch Probabilities (calibrated) ===  
Eval date (price anchor): 2026-01-09 | close=90,641.28  
Conditioning SAFE date:   2026-01-08  

Regime probs (conditioning):  
  P_UP_SLOW_HMM       : 0.0000  
  P_UP_FAST_HMM       : 0.0000  
  P_RANGE_LOWVOL_HMM  : 0.5759  
  P_RANGE_HIGHVOL_HMM : 0.0000  
  P_DOWN_SLOW_HMM     : 0.0375  
  P_DOWN_FAST_HMM     : 0.3866  

Calibrated mixture params (daily log-return):  
  mu    = +0.001356  (~+0.136% per day)  
  sigma = 0.026875 (~2.687% daily)  

--- Touch probabilities within horizon ---  
Horizon: 10 days | sims: 20000  

UP targets:  
    +2%:  72.2%  
    +5%:  50.8%  
   +10%:  24.4%  
DOWN targets:  
    -2%:  62.4%  
    -5%:  38.7%  
   -10%:  13.0%  

--- Calibration per regime (mu, sigma, weight_sum) ---  
P_UP_SLOW_HMM        mu=+0.001055 sigma=0.025629 wsum=480.2  
P_UP_FAST_HMM        mu=+0.003245 sigma=0.035042 wsum=343.3  
P_RANGE_LOWVOL_HMM   mu=+0.000002 sigma=0.022145 wsum=416.1  
P_RANGE_HIGHVOL_HMM  mu=-0.000385 sigma=0.030473 wsum=446.1  
P_DOWN_SLOW_HMM      mu=+0.000770 sigma=0.037607 wsum=452.2  
P_DOWN_FAST_HMM      mu=+0.003429 sigma=0.031520 wsum=181.1  
