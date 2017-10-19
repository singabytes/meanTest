var mongoose = require('mongoose');

var array1DModel = mongoose.model('Array1D');

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





