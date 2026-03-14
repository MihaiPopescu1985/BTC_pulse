---
layout: default
title: BTC Pulse
---

<div class="content-wrapper">
  <section class="layout-main">
    <div id="main-chart-container" data-chart-key="dailySafe" style="width: 100%; height: 680px;"></div>

    <h2>How to read the dashboard (the SAFE flow)</h2>
    <div>
      <div>
        <b>Start with Regime</b>:
        if the regime probability mass is strongly bearish, SAFE stays defensive even if opportunity is rising.
      </div>
      <div>
        <b>Check short-horizon price statistics</b>:
        do we have momentum (autocorrelation) or mean reversion (rebound)?
      </div>
      <div>
        <b>Overlay on-chain</b>:
        is the move driven by broad participation, or are whales stepping in/out?
      </div>
      <div>
        <b>Compute Target Exposure</b>:
        SAFE “loads” exposure when expected payoff improves, but can still be vetoed by regime/hazard rules.
      </div>
    </div>

    <section>
      <h2>Indicators shown in the current BTC dashboard</h2>
      <p>
        The chart combines price candles with regime probabilities, short-horizon price statistics, SAFE exposure,
        and on-chain features. Below is a practical interpretation guide.
      </p>

      <table>
        <thead>
          <tr>
            <th>Line / Feature</th>
            <th>Scale</th>
            <th>How to interpret</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>UP_SLOW, UP_FAST<br/>RANGE_LOWVOL, RANGE_HIGHVOL<br/>DOWN_SLOW, DOWN_FAST</td>
            <td>0..1 probabilities</td>
            <td>
              Regime classifier output. When one state dominates (e.g., ~0.99), SAFE treats it as the market’s
              “operating mode”. Transitions (e.g., DOWN_SLOW → RANGE_LOWVOL) matter more than single-day wiggles.
            </td>
          </tr>
          <tr>
            <td>P_Corr_10D</td>
            <td>~ -1..+1</td>
            <td>
              Short-horizon autocorrelation (a proxy for momentum vs noise).
              Near <span>0</span> suggests “memoryless” price action (weak trend edge).
            </td>
          </tr>
          <tr>
            <td>P_Reb_10D</td>
            <td>0..1</td>
            <td>
              Estimated 10-day rebound likelihood / mean-reversion propensity. Low values imply weak bounce odds;
              rising values often appear before a stable range or recovery phase.
            </td>
          </tr>
          <tr>
            <td>E_target_safe</td>
            <td>0..1</td>
            <td>
              SAFE target exposure (risk budget allocation). It can climb while regime remains bearish:
              that means “opportunity is building” but “confirmation is missing”.
            </td>
          </tr>
          <tr>
            <td>OC_amount_log</td>
            <td>log scale</td>
            <td>
              Total on-chain transfer amount (log). High values = active network. Extreme spikes can accompany
              structural events; persistently low values can signal exhaustion/freeze.
            </td>
          </tr>
          <tr>
            <td>OC_vol_z</td>
            <td>z-score</td>
            <td>
              Standardized on-chain volume. Negative = below long-term mean; deep negative often means participation
              is muted (not necessarily bullish or bearish, but informative with other features).
            </td>
          </tr>
          <tr>
            <td>OC_whale_share</td>
            <td>0..1 (often small)</td>
            <td>
              Share of activity attributed to large entities (whales). Rising whale share ahead of price can
              indicate accumulation/distribution; very low whale share suggests price is driven by smaller flows.
            </td>
          </tr>
          <tr>
            <td>OC_dom_z</td>
            <td>z-score</td>
            <td>
              Dominance-like signal standardized. Negative = below average dominance/relative strength, often
              implying BTC is not “pulling liquidity” aggressively.
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </section>
</div>

<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
<script src="{{ site.baseurl }}/assets/scripts/charts/daily_safe.js"></script>
<script src="{{ site.baseurl }}/assets/scripts/dashboard.js"></script>
