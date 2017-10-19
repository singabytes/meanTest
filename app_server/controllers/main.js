/* Get home page */

var request = require('request');

var apiOptions = {
  server : "http://127.0.0.1:3000"
};
if (process.env.NODE_ENV === 'production') {
  apiOptions.server = "https://getting-mean-loc8r.herokuapp.com";
}

module.exports.index = function(req, response) {
    renderHomePage(req, response)
};

var renderHomePage = function(req, res) {
    res.render('index', {
        title: 'Express',
        params: { x: '10', y: '20'}
    });
}
   


