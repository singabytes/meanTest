$(function() {
  var chart;
  var colors = Highcharts.getOptions().colors;
  var name = 'Browser brands';

  var browserSharingData;

  $.get('./javascripts/browserSharing.json', function(resp) {
    console.log(resp);
    browserSharingData = resp;
    chart = new Highcharts.Chart({
      chart: {
        renderTo: 'container',
        type: 'pie'
      },
      title: {
        text: 'Browser market share'
      },
      yAxis: {
        title: {
          text: 'This is the yAxis'
        }
      },
      plotOptions: {
        pie: {
          shadow: true
        }
      },
      tooltip: {
        valueSuffic: '%'
      },
      series: [{
        name: 'Browsers',
        data: browserSharingData,
        innerSize: '120',
        size: '240',
        dataLabels: {
          distance: 15,
          formatter: function() {
            return this.y > 1 ? '<b>' + this.point.name + ':</b> ' + this.y + '%' : null;
          }
        }
      }]
    });
  });


});
