$.getJSON('http://127.0.0.1:3000/api/bars', function (data) {
        console.log(data);
        // create the chart
        Highcharts.stockChart('container', {
    
    
            title: {
                text: 'AAPL stock price by minute'
            },
    
            rangeSelector: {
                buttons: [{
                    type: 'hour',
                    count: 1,
                    text: '1h'
                }, {
                    type: 'day',
                    count: 1,
                    text: '1D'
                }, {
                    type: 'all',
                    count: 1,
                    text: 'All'
                }],
                selected: 1,
                inputEnabled: false
            },
    
            series: [{
                name: 'AAPL',
                type: 'candlestick',
                data: data.data,
                tooltip: {
                    valueDecimals: 2
                }
            }]
        });
    });