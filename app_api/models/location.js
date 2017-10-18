var mongoose = require('mongoose');

var locationSchema = new mongoose.Schema({
    name: {
        type: String,
        required: true
    },
    data: [Number],
});

mongoose.model('Location', locationSchema);