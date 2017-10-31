var mongoose = require('mongoose');

var array1DSchema = new mongoose.Schema({
    name: {
        type: String,
        required: true
    },
    data: [Number],
});

mongoose.model('Array1D', array1DSchema);

var barSchema = new mongoose.Schema({
        timestamp: {
            type: String,
            required: true
        },
        open: {
            type: Number,
            required: true
        },
        high: {
            type: Number,
            required: true
        },
        low: {
            type: Number,
            required: true
        },
        close: {
            type: Number,
            required: true
        }
    }, {
        collection: 'EURUSD1min'
    }
);

mongoose.model('Bar', barSchema);