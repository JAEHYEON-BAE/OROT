// Make accidental live API access a test failure.
global.fetch = jest.fn(() =>
  Promise.reject(new Error("Network is disabled in mobile tests.")),
);
