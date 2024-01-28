'use client'

import React, {useEffect, useRef, useState} from 'react';
import HighchartsReact from 'highcharts-react-official';
import Highcharts from 'highcharts/highstock';

import HighchartsExporting from 'highcharts/modules/exporting';

if (typeof Highcharts === 'object') {
    HighchartsExporting(Highcharts);
}

const Chart = () => {
    const chartRef = useRef();

    const staticData = [
        {
            x: 1,
            y: 4.278691803278688,
        },
        {
            x: 5,
            y: 4.278704918032787,
        },
        {
            x: 10,
            y: 4.27872131147541,
        },
        {
            x: 15,
            y: 4.278737704918033,
        },
        {
            x: 20,
            y: 4.278754098360656,
        },
        {
            x: 50,
            y: 4.278852459016393,
        },
        {
            x: 100,
            y: 4.279016393442623,
        },
        {
            x: 150,
            y: 4.279180327868852,
        },
        {
            x: 200,
            y: 4.279344262295083,
        },
        {
            x: 500,
            y: 4.280327868852459,
        },
        {
            x: 1000,
            y: 4.281967213114754,
        },
        {
            x: 1500,
            y: 4.283606557377049,
        },
        {
            x: 2000,
            y: 4.285245901639344,
        },
        {
            x: 5000,
            y: 4.295081967213115,
        },
        {
            x: 10000,
            y: 4.311475409836066,
        },
        {
            x: 15000,
            y: 4.327868852459017,
        },
        {
            x: 20000,
            y: 4.344262295081967,
        },
        {
            x: 50000,
            y: 4.442622950819673,
        },
        {
            x: 100000,
            y: 4.606557377049181,
        },
        {
            x: 150000,
            y: 4.770491803278689,
        },
        {
            x: 200000,
            y: 4.9344262295081975,
        },
        {
            x: 500000,
            y: 5.918032786885246,
        },
        {
            x: 1000000,
            y: 7.557377049180328,
        },
        {
            x: 1250000,
            y: 8.377049180327868,
        },
        {
            x: 1500000,
            y: 9.19672131147541,
        },
        {
            x: 1750000,
            y: 10.01639344262295,
        },
        {
            x: 2000000,
            y: 10.83606557377049,
        },
        {
            x: 2250000,
            y: 11.655737704918032,
        },
        {
            x: 2500000,
            y: 12.475409836065573,
        },
        {
            x: 2750000,
            y: 13.295081967213115,
        },
        {
            x: 3000000,
            y: 14.114754098360658,
        },
        {
            x: 3500000,
            y: 15.754098360655739,
        },
        {
            x: 4000000,
            y: 17.39344262295082,
        },
        {
            x: 5000000,
            y: 20.672131147540984,
        },
        {
            x: 10000000,
            y: 25,
        },
    ];

    const [chartOptions, setChartOptions] = useState({
        xAxis: {
            type: 'logarithmic',
            crosshair: {
                color: '#4E7DD9',
                dashStyle: 'Dash',
            },
            ordinal: false,
            minRange: 1,
        },
        yAxis: {
            opposite: false,
            labels: {
                format: '{value}%',
            },
            gridLineDashStyle: 'Dash',
            gridLineColor: '#01052D40',
            gridLineWidth: 0.5,
            // min: yAxisMin,
        },
        series: [
            {
                type: 'areaspline',
                name: 'Chart',
                data: null,
                lineWidth: 3,
                lineColor: '#4E7DD9',
                fillColor: {
                    linearGradient: {
                        x1: 0,
                        y1: 0,
                        x2: 0,
                        y2: 1,
                    },
                    stops: [
                        [0, 'rgba(78, 125, 217, 0.4)'],
                        [1, 'rgba(78, 125, 217, 0.05)'],
                    ],
                },
                marker: {
                    fillColor: 'white',
                    lineWidth: 2,
                    radius: 3,
                    lineColor: '#4E7DD9',
                },
                animation: {
                    duration: 500,
                },
            },
        ],
        chart: {
            backgroundColor: 'transparent',
            // zoomType: "x",
        },
        navigation: {
            enabled: false,
            buttonOptions: {
                enabled: false,
            },
        },
        rangeSelector: {enabled: false},
        credits: {enabled: false},
        tooltip: {
            animation: true,
            // xDateFormat: "",
            useHTML: true,
            backgroundColor: 'rgba(255, 255, 255)',
            borderWidth: 1,
            borderRadius: 15,
            borderColor: '#B0C4DB',
            shadow: {
                offsetX: 1,
                offsetY: 2,
                width: 2,
                opacity: 0.05,
            },
            shape: 'square',
            // split: true,
            hideDelay: 100,
            outside: false,
        },
        navigator: {
            handles: {
                // lineWidth: 1,
                width: 20,
                height: 30,
            },
            maskFill: 'rgba(78, 125, 217, 0.2)',
            outlineWidth: 0,
            enabled: false,
            xAxis: {},
        },
        scrollbar: {
            enabled: false,
        },
    });

    useEffect(() => {
        setChartOptions({
            series: {
                data: staticData,
            },
        });
    }, []);

    return (
        <div>
            <HighchartsReact
                highcharts={Highcharts}
                options={chartOptions}
                constructorType="chart"
                ref={chartRef}
            />
        </div>
    );
};

export default Chart;
