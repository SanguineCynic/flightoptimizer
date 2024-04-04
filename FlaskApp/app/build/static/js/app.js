/* Add your Application JavaScript */
console.log('this is some JavaScript code');

function notify() {
  alert('in here I will do something');
}

// notify();

// Helper function to select elements
function select(selector) {
  return document.querySelector(selector);
}

// Function to add event listener
function on(event, selector, handler, capture = false) {
  const element = select(selector);
  if (element) {
    element.addEventListener(event, handler, capture);
  }
}

// Event listener for mobile nav toggle
function handleMobileNavToggle(e) {
  const navbar = select('#navbar');
  navbar.classList.toggle('navbar-mobile');
  e.currentTarget.classList.toggle('bi-list');
  e.currentTarget.classList.toggle('bi-x');
}

// Event listener for mobile nav dropdowns activation
function handleDropdownActivation(e) {
  const navbar = select('#navbar');
  if (navbar.classList.contains('navbar-mobile')) {
    e.preventDefault();
    e.currentTarget.nextElementSibling.classList.toggle('dropdown-active');
  }
}

// Add event listeners on page load
window.addEventListener('DOMContentLoaded', () => {
  on('click', '.mobile-nav-toggle', handleMobileNavToggle);
  on('click', '.navbar .dropdown > a', handleDropdownActivation, true);
});
