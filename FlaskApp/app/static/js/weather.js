window.onload = function() {
    metric = true;
    tempSwitch = document.getElementById('temperature-switch'); 
    fLabel = document.getElementById('degree-label-F');
    cLabel = document.getElementById('degree-label-C');

    // Use getElementsByClassName to select elements by class name
    tempC = document.getElementsByClassName("metric");
    tempF = document.getElementsByClassName("imperial");

    fLabel.style.visibility = 'hidden';
    // Hide all elements with class 'imperial'
    for (let i = 0; i < tempF.length; i++) {
        tempF[i].style.display = 'none';
    }

    tempSwitch.addEventListener('change', function(event) {
        if (metric == true) {
            // show farenheit info
            metric = false;
            fLabel.style.visibility= 'visible';
            cLabel.style.visibility= 'hidden';
            // Show all elements with class 'imperial' and hide 'metric'
            for (let i = 0; i < tempF.length; i++) {
                tempF[i].style.display='inline';
            }
            for (let i = 0; i < tempC.length; i++) {
                tempC[i].style.display='none';
            }
        } else {
            metric = true;
            fLabel.style.visibility= 'hidden';
            cLabel.style.visibility= 'visible';
            // Hide all elements with class 'imperial' and show 'metric'
            for (let i = 0; i < tempF.length; i++) {
                tempF[i].style.display='none';
            }
            for (let i = 0; i < tempC.length; i++) {
                tempC[i].style.display='inline';
            }
        }
    });
};
