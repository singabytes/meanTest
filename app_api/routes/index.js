var express = require('express');
var router = express.Router();

var ctrlLocations = require('../controllers/locations');

router.get('/locations', ctrlLocations.locationsListByDistance);

module.exports = router;
