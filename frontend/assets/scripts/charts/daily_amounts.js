---
layout: null
---
(function (global) {
    'use strict';

    const baseOption = {
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'cross' }
        },
        toolbox: {
            feature: {
                dataZoom: { yAxisIndex: 'none' },
                restore: {},
                saveAsImage: {}
            }
        },
        xAxis: { type: 'category' },
        yAxis: { type: 'value' },
        dataZoom: [
            { type: 'slider', xAxisIndex: 0, filterMode: 'filter' },
            { type: 'inside', xAxisIndex: 0, filterMode: 'filter' }
        ],
        series: [
            {
                type: 'line',
                smooth: true,
                symbol: 'none',
                areaStyle: {}
            }
        ]
    };

    function buildOption(rawData) {
        const option = global.ChartUtils.clone(baseOption);
        option.dataset = { source: Object.entries(rawData) };
        return option;
    }

    global.chartRegistry = global.chartRegistry || {};
    global.chartRegistry.dailyAmounts = {
        buildOption: buildOption
    };
})(window);
