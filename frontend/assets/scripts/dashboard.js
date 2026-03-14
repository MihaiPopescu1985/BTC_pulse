---
layout: null
---

// Data from files
const dataFiles = {
  dailyAmounts: {{ site.data.daily_amounts | jsonify }},
  dailyPrice: {{ site.data.daily_price | jsonify }},
  dailyTxSize: {{ site.data.daily_tx_size | jsonify }},
  dailySafe: {
    features: {{ site.data.features | jsonify }},
    onchain: {{ site.data.onchain_features | jsonify }},
    dailyPrice: {{ site.data.daily_price | jsonify }}
  }
};

// Display
document.addEventListener('DOMContentLoaded', () => {
    
    // Container initialization
    const chartDom = document.getElementById('main-chart-container');
    if (!chartDom) {
        console.error('Chart container not found.');
        return;
    }
    const myChart = echarts.init(chartDom);

    // Render the chart
    function renderChart(key) {
        // Loading data and options
        const rawData = dataFiles[key];
        const chartDef = window.chartRegistry && window.chartRegistry[key];

        if (!rawData || !chartDef) {
            console.error('Data or cofiguration missing for:', key);
            return;
        }

        // Reset the chart with the new options
        const option = chartDef.buildOption(rawData);
        myChart.setOption(option, true);
    }

    // Changing charts
    const navButtons = document.querySelectorAll('.nav-btn');
    
    navButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            // UI: toggle the active class
            navButtons.forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');

            // Logic: draw the requested chart
            const key = e.target.getAttribute('data-key');
            if (key) {
                renderChart(key);
            }
        });
    });

    // Loading the first chart
    const defaultKey = chartDom.dataset.chartKey || 'dailyTxSize';
    renderChart(defaultKey);

    // Automatic resize
    window.addEventListener('resize', () => {
        myChart.resize();
    });
});
