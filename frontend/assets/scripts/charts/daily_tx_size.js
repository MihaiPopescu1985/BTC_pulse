---
layout: null
---
(function (global) {
    'use strict';

    const baseOption = {
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'shadow' }
        },
        legend: {},
        toolbox: {
            feature: {
                dataZoom: { yAxisIndex: 'none' },
                restore: {},
                saveAsImage: {}
            }
        },
        grid: {
            left: '3%',
            right: '4%',
            bottom: '3%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            axisLabel: { rotate: 45 }
        },
        yAxis: {
            type: 'value',
            name: 'Count'
        },
        dataset: {
            source: []
        },
        dataZoom: [
            { type: 'slider', xAxisIndex: 0, filterMode: 'filter' },
            { type: 'inside', xAxisIndex: 0, filterMode: 'filter' }
        ],
        series: [
            { type: 'bar', stack: 'total' },
            { type: 'bar', stack: 'total' },
            { type: 'bar', stack: 'total' },
            { type: 'bar', stack: 'total' },
            { type: 'bar', stack: 'total' },
            { type: 'bar', stack: 'total' },
            { type: 'bar', stack: 'total' },
            { type: 'bar', stack: 'total' }
        ]
    };

    function buildOption(rawData) {
        const option = global.ChartUtils.clone(baseOption);
        option.dataset = { source: rawData };
        return option;
    }

    global.chartRegistry = global.chartRegistry || {};
    global.chartRegistry.dailyTxSize = {
        buildOption: buildOption
    };
})(window);
