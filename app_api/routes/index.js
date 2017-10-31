var express = require('express');
var router = express.Router();

var ctrlLocations = require('../controllers/array');

router.get('/array1D/test/:size', ctrlLocations.array1DTest);
router.get('/bars', ctrlLocations.bar);

module.exports = router;

