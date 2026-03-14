---
layout: default
title: BTC Pulse
---

<div class="content-wrapper">
  <section class="layout-main">
    <div>
      <span>SAFE</span>
      <span>Statistical Asset Flow Engine</span>
      <span> - probabilistic regimes + hazard + exposure</span>
    </div>
    <h1>SAFE: a context engine for BTC risk decisions</h1>
    <p>
      SAFE is not a price predictor and not a signal generator. It summarizes the current
      market context as probabilities and converts that context into a target exposure level.
      The core question is: <b>"How much risk makes sense right now?"</b>
    </p>

    <section>
      <div>
        <h2>SAFE in one paragraph</h2>
        <p>
          SAFE treats BTC as a living system whose behavior changes over time. It estimates
          probabilistic regimes, combines them with risk features (volatility, trend stress, hazard),
          and produces a continuous target exposure between <b>0 and 1</b>. The dashboard is built
          for understanding and risk control, not for impulsive trading.
        </p>

        <div></div>

        <h2>A simple analogy</h2>
        <p>
          Think of price as the road and SAFE as the weather plus road conditions. It does not tell you
          the exact destination, but it tells you whether conditions are safe enough to drive fast
          or whether you should slow down.
        </p>

        <div></div>

        <h2>What SAFE does and does not do</h2>
        <div>
          <div>
            <strong>What it does</strong>
            <p>
              Describes market context, reduces risk in dangerous periods, and stays transparent
              through auditable indicators.
            </p>
          </div>
          <div>
            <strong>What it does not do</strong>
            <p>
              It does not promise to beat buy and hold, it does not call tops or bottoms, and it does
              not generate buy or sell signals.
            </p>
          </div>
        </div>

        <div></div>

        <h2>How to read SAFE outputs</h2>
        <p>
          The operational output is a <b>target exposure</b> (0..1) and a simple action label
          (<b>NO ACTION</b>, <b>INCREASE</b>, <b>DECREASE</b>). Adjustments are gradual, and the current
          bias is <b>long-only</b> with risk throttling.
        </p>
      </div>

      <div>
        <h2>Regimes shown in the dashboard</h2>
        <table>
          <thead>
            <tr>
              <th>Regime</th>
              <th>Meaning</th>
              <th>Typical context</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>CORE</td>
              <td>Stable, normal market behavior</td>
              <td>Lower noise, steady conditions</td>
            </tr>
            <tr>
              <td>DRIFT</td>
              <td>Stable but gently directional</td>
              <td>Soft trend without strong conviction</td>
            </tr>
            <tr>
              <td>SURGE</td>
              <td>Strong move with high volatility</td>
              <td>Fast repricing, momentum-driven</td>
            </tr>
            <tr>
              <td>SHOCK</td>
              <td>Stress regime, elevated volatility</td>
              <td>Risk-off conditions, drawdown risk</td>
            </tr>
          </tbody>
        </table>

        <p>
          Markets often contain <b>multiple regimes at once</b>. SAFE shows them as probabilities,
          not hard switches.
        </p>

        <div></div>

        <h2>High-level pipeline</h2>
        <div>
          <div><b>1) Features</b>: returns, volatility, trend, stress</div>
          <div><b>2) Regimes</b>: probabilistic state estimates (HMM)</div>
          <div><b>3) Hazard</b>: event risk of adverse moves</div>
          <div><b>4) Exposure</b>: capital-aware target allocation</div>
        </div>

        <div></div>

        <h2>Design principles</h2>
        <div>
          <div><b>Calibrated probabilities</b> over pretty scores</div>
          <div><b>Regime awareness</b> over single indicators</div>
          <div><b>Auditability</b> over black-box ML</div>
        </div>
      </div>
    </section>

    <h2>Disclaimer</h2>
    <p>
      SAFE is a research and engineering framework. It is not financial advice.
      Any strategy built on top of SAFE should include robust risk controls and
      out-of-sample validation.
    </p>

  </section>
</div>
