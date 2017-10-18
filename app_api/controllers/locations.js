var mongoose = require('mongoose');

var Loc = mongoose.model('Location');

var sendJSONresponse = function(res, status, content) {
    res.status(status);
    res.json(content);
};

/* GET list of locations */
module.exports.locationsListByDistance = function(req, res) {
     sendJSONresponse(res, 200, [1,2,4,9,16,25,36,49]);
};
