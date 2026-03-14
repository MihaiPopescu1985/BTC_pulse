---
layout: null
---
(function (global) {
    'use strict';

    function clone(value) {
        return JSON.parse(JSON.stringify(value));
    }

    function calculateMA(dayCount, values) {
        const result = [];
        for (let i = 0; i < values.length; i++) {
            if (i < dayCount) {
                result.push('-');
                continue;
            }
            let sum = 0;
            for (let j = 0; j < dayCount; j++) {
                sum += values[i - j][1];
            }
            result.push(+(sum / dayCount).toFixed(3));
        }
        return result;
    }

    global.ChartUtils = {
        clone: clone,
        calculateMA: calculateMA
    };
})(window);
