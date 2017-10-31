var mongoose = require('mongoose');
var moment = require('moment')

var array1DModel = mongoose.model('Array1D');
var barModel = mongoose.model('Bar');

var sendJSONresponse = function(res, status, content) {
    res.status(status);
    res.json(content);
};

/* one dimensional array */
module.exports.array1DTest = function(req, res) {
    var array = []
    for (i = 0; i < req.params.size; i++) {
        array.push(i*i);
    }
    content = { name: 'array1DTest', data: array };
    sendJSONresponse(res, 200, content);
};

/* stock bar */
module.exports.bar = function(req, res) {
    barModel.find( {}, null, { sort: { timestamp: 1 }}, function(err, data) {
        if (err) return console.error(err);
        var arraybig = [];
        for (i = 0; i < data.length; i++) {
            var arraysmall = [];
            var tt = moment(data[i].timestamp, 'YYYY-MM-DD HH:mm:ss');
            //console.log(tt);
            var epoch = tt.unix() * 1000; // in ms
            //console.log(epoch);
            arraysmall.push(epoch);
            arraysmall.push(data[i].open);
            arraysmall.push(data[i].high);
            arraysmall.push(data[i].low);
            arraysmall.push(data[i].close);
            arraybig.push(arraysmall);
        }
        content = { data: arraybig };
        sendJSONresponse(res, 200, content);
    });
};

/*module.exports.bar = function(req, res) {
    barModel
    .findById('')
    .select('')
    .exec(
      function(err, location) {
        if (err) {
          sendJSONresponse(res, 400, err);
        } else {
          doAddReview(req, res, location);
        }
      }
  );
};*/



