var express = require('express');
var router = express.Router();

var ctrlLocations = require('../controllers/array');

router.get('/array1D/test/:size', ctrlLocations.array1DTest);

module.exports = router;

