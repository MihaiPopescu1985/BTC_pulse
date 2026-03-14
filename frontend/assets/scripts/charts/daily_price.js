---
layout: null
---
(function (global) {
    'use strict';

    const baseOption = {
        legend: {
            bottom: 10,
            left: 'center',
            data: ['BTC daily price', 'MA5', 'MA10', 'MA20', 'MA30']
        },
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'cross' }
        },
        axisPointer: {
            link: [{ xAxisIndex: 'all' }],
            label: { backgroundColor: '#777' }
        },
        toolbox: {
            feature: {
                dataZoom: { yAxisIndex: false },
                restore: {},
                saveAsImage: {}
            }
        },
        visualMap: {
            show: false,
            seriesIndex: 5,
            dimension: 2,
            pieces: [
                { value: 1, color: '#ec0000' },
                { value: -1, color: '#00da3c' }
            ]
        },
        grid: [
            { left: '10%', right: '8%', height: '50%' },
            { left: '10%', right: '8%', top: '63%', height: '16%' }
        ],
        xAxis: [
            {
                type: 'category',
                data: [],
                boundaryGap: false,
                axisLine: { onZero: false },
                splitLine: { show: false },
                min: 'dataMin',
                max: 'dataMax',
                axisPointer: { z: 100 }
            },
            {
                type: 'category',
                gridIndex: 1,
                data: [],
                boundaryGap: false,
                axisLine: { onZero: false },
                axisTick: { show: false },
                splitLine: { show: false },
                axisLabel: { show: false },
                min: 'dataMin',
                max: 'dataMax'
            }
        ],
        yAxis: [
            { scale: true, splitArea: { show: true } },
            {
                scale: true,
                gridIndex: 1,
                splitNumber: 2,
                axisLabel: { show: false },
                axisLine: { show: false },
                axisTick: { show: false },
                splitLine: { show: false }
            }
        ],
        dataZoom: [
            { type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 },
            { show: true, xAxisIndex: [0, 1], type: 'slider', top: '85%', start: 0, end: 100 }
        ],
        series: [
            {
                name: 'BTC daily price',
                type: 'candlestick',
                data: [],
                itemStyle: {
                    color: '#00da3c',
                    color0: '#ec0000',
                    borderColor: '#00da3c',
                    borderColor0: '#ec0000'
                }
            },
            { name: 'MA5', type: 'line', data: [], smooth: true, lineStyle: { opacity: 0.5 } },
            { name: 'MA10', type: 'line', data: [], smooth: true, lineStyle: { opacity: 0.5 } },
            { name: 'MA20', type: 'line', data: [], smooth: true, lineStyle: { opacity: 0.5 } },
            { name: 'MA30', type: 'line', data: [], smooth: true, lineStyle: { opacity: 0.5 } },
            { name: 'Volume', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: [] }
        ]
    };

    function splitDailyPriceData(rawData) {
        const categoryData = [];
        const values = [];
        const volumes = [];

        rawData.forEach((row, index) => {
            categoryData.push(row.timestamp);
            values.push([row.open, row.close, row.low, row.high]);
            volumes.push([index, row.volume, row.open > row.close ? 1 : -1]);
        });

        return { categoryData, values, volumes };
    }

    function buildOption(rawData) {
        const option = global.ChartUtils.clone(baseOption);
        const data = splitDailyPriceData(rawData);

        option.xAxis[0].data = data.categoryData;
        option.xAxis[1].data = data.categoryData;
        option.series[0].data = data.values;
        option.series[1].data = global.ChartUtils.calculateMA(5, data.values);
        option.series[2].data = global.ChartUtils.calculateMA(10, data.values);
        option.series[3].data = global.ChartUtils.calculateMA(20, data.values);
        option.series[4].data = global.ChartUtils.calculateMA(30, data.values);
        option.series[5].data = data.volumes;

        return option;
    }

    global.chartRegistry = global.chartRegistry || {};
    global.chartRegistry.dailyPrice = {
        buildOption: buildOption
    };
})(window);
