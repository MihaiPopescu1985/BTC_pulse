---
layout: post
title: "On-chain Activity Cools, Range Bias Holds"
date: 2026-01-08
author: BTC Pulse
description: "Last two days show cooling activity and a shift toward range conditions with reduced downside intensity."
---

Over the last two sessions, on-chain activity cooled materially while price held near the lower part of its band.  
Total on-chain amount fell from ~1.00M to ~0.69M, the volume z-score dropped from 1.37 to 0.23, and whale share normalized (whale share z-score from 0.81 to 0.02).  
This looks less like acute distribution and more like a pause in participation.

Regime probabilities shifted toward range: HMM range-lowvol rose (0.37 to 0.58), while HMM down-fast eased (0.61 to 0.39).  
Band position stayed low (0.166 to 0.159), suggesting price remains in a lower-band zone, but without fresh downside acceleration.  
Exposure guidance softened (E_target_safe 0.58 to 0.51), reflecting reduced conviction.

Near-term expectation: a choppy, range-leaning phase unless participation re-accelerates. If on-chain volume and dominance stay muted, the model likely favors patience over aggressive adds; if volume and whale dominance re-expand, risk of a sharper move (either rebound or renewed downside) rises.

=== SAFE Touch Probabilities (calibrated) ===  
Eval date (price anchor): 2026-01-08 | close=91,099.99  
Conditioning SAFE date:   2026-01-07  

Regime probs (conditioning):  
  P_UP_SLOW_HMM       : 0.0000  
  P_UP_FAST_HMM       : 0.0000  
  P_RANGE_LOWVOL_HMM  : 0.3742  
  P_RANGE_HIGHVOL_HMM : 0.0000  
  P_DOWN_SLOW_HMM     : 0.0109  
  P_DOWN_FAST_HMM     : 0.6148  

Calibrated mixture params (daily log-return):  
  mu    = +0.002130  (~+0.213% per day)  
  sigma = 0.028517 (~2.852% daily)  

--- Touch probabilities within horizon ---  
Horizon: 10 days | sims: 20000  

UP targets:  
    +2%:  74.9%  
    +5%:  55.4%  
   +10%:  29.3%  
DOWN targets:  
    -2%:  61.4%  
    -5%:  38.2%  
   -10%:  13.4%  

--- Calibration per regime (mu, sigma, weight_sum) ---  
P_UP_SLOW_HMM        mu=+0.001055 sigma=0.025629 wsum=480.2  
P_UP_FAST_HMM        mu=+0.003245 sigma=0.035042 wsum=343.3  
P_RANGE_LOWVOL_HMM   mu=+0.000012 sigma=0.022165 wsum=415.3  
P_RANGE_HIGHVOL_HMM  mu=-0.000385 sigma=0.030473 wsum=446.1  
P_DOWN_SLOW_HMM      mu=+0.000771 sigma=0.037612 wsum=452.1  
P_DOWN_FAST_HMM      mu=+0.003443 sigma=0.031529 wsum=181.0  
