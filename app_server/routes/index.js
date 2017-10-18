var express = require('express');
var router = express.Router();
var controllerMain = require('../controllers/main')

// homepageControllers is the callback function that
// implements the application logic of the homepage
router.get('/', controllerMain.index);

module.exports = router;
