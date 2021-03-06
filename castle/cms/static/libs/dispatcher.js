define([
  'jquery',
  'castle-url/libs/es6-promise/promise.min',
  'castle-url/libs/object-assign'
], function($, promise, assign) {
  'use strict';

  var _callbacks = [];
  var _promises = [];

  var Dispatcher = function() {};
  Dispatcher.prototype = assign({}, Dispatcher.prototype, {

    /**
     * Register a Store's callback so that it may be invoked by an action.
     * @param {function} callback The callback to be registered.
     * @return {number} The index of the callback within the _callbacks array.
     */
    register: function(callback) {
      _callbacks.push(callback);
      return _callbacks.length - 1; // index
    },

    /**
     * dispatch
     * @param  {object} payload The data from the action.
     */
    dispatch: function(payload) {
      // First create array of promises for callbacks to reference.
      var resolves = [];
      var rejects = [];
      _promises = _callbacks.map(function(_, i) {
        return new promise.Promise(function(resolve, reject) {
          resolves[i] = resolve;
          rejects[i] = reject;
        });
      });
      // Dispatch to callbacks and resolve/reject promises.
      _callbacks.forEach(function(callback, i) {
        // Callback can return an obj, to resolve, or a promise, to chain.
        // See waitFor() for why this might be useful.
        promise.Promise.resolve(callback(payload)).then(function() {
          resolves[i](payload);
        }, function() {
          rejects[i](new Error('Dispatcher callback unsuccessful'));
        });
      });
      _promises = [];
    },
    /**
     * A bridge function between the views and the dispatcher, marking the action
     * as a view action.  Another variant here could be handleServerAction.
     * @param  {object} action The data coming from the view.
     */
    handleViewAction: function(action) {
      this.dispatch(action);
    }
  });

  return Dispatcher;
});
