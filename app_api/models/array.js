var mongoose = require('mongoose');

var array1DSchema = new mongoose.Schema({
    name: {
        type: String,
        required: true
    },
    data: [Number],
});

mongoose.model('Array1D', array1DSchema);