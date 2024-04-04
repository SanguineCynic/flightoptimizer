window.onload = function() {
    celcius = true;
    tempSwitch = document.getElementById('temperature-switch'); 
    fLabel = document.getElementById('degree-label-F');
    cLabel = document.getElementById('degree-label-C')
    tempC = document.getElementById("tempC")
    tempF = document.getElementById("tempF")

    fLabel.style.visibility = 'hidden';
    tempF.style.display = 'none';

    tempSwitch.addEventListener('change', function(event) {
        if (celcius == true) {
            // show farenheit info
            celcius = false;
            fLabel.style.visibility= 'visible';
            cLabel.style.visibility= 'hidden';
            tempF.style.display='inline';
            tempC.style.display='none';
        } else {
            celcius = true;
            fLabel.style.visibility= 'hidden';
            cLabel.style.visibility= 'visible';
            tempF.style.display='none'
            tempC.style.display='inline'
        }
    });
  };