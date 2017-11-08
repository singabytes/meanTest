/// <reference path="../Scripts/angular-1.1.4.js" />

/*#######################################################################

  Normally like to break AngularJS apps into the following folder structure
  at a minimum:

  /app
      /controllers      
      /directives
      /services
      /partials
      /views

  #######################################################################*/

  var app = angular.module('dashboardApp', []);
  
  //This configures the routes and associates each route with a view and a controller
  app.config(function ($routeProvider) {
      $routeProvider
          .when('/customers',
              {
                  controller: 'CustomersController',
                  templateUrl: './partials/customers.html'
              })
          //Define a route that has a route parameter in it (:customerID)
          //.when('/customerorders/:customerID',
          //    {
          //        controller: 'CustomerOrdersController',
          //        templateUrl: 'app/partials/customerOrders.html'
          //    })
          .otherwise({ redirectTo: '/customers' });
  });