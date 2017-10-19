/* Get home page */

var request = require('request');

var apiOptions = {
  server : "http://127.0.0.1:3000"
};
if (process.env.NODE_ENV === 'production') {
  apiOptions.server = "https://getting-mean-loc8r.herokuapp.com";
}

module.exports.index = function(req, response) { // ne pas mettre request car conflit avec methode request
    var requestOptions, path;
    path = '/api/locations';
    requestOptions = {
        url : apiOptions.server + path,
        method : "GET",
        json : {},
        qs : {}
    };
    request(
        requestOptions,
        function(err, response, body) {
            data = body;
            //if (response.statusCode == 200 && data.length) {
            //}
            renderHomePage(req, response, data)
        }
    );
};