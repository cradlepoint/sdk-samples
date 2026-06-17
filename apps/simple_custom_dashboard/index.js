function headerSelect(name) {
    document.getElementById("menu").style.display = "none";
    document.getElementById("menu button").style.backgroundColor = "";

    document.getElementById("upload").style.display = "none";
    document.getElementById("upload button").style.backgroundColor = "";

    document.getElementById(name).style.display = "block";
    document.getElementById(name + " button").style.backgroundColor = "green";
}

function show_buttons() {
    document.getElementById("default config").style.display = "none";
    document.getElementById("main page").style.display = "block";
}

function handle_router_data (data) {
    var json_data = JSON.parse(data);
    document.getElementById("host os").innerHTML = "Host OS: " + json_data.host_os;
    document.getElementById("system id").innerHTML = "System ID: " + json_data.system_id;
    document.getElementById("modem temp").innerHTML = "Modem Temp: " + json_data.modem_temp;
}

function get_data() {
    var data_to_get = "value=router_data";
    var http = new XMLHttpRequest();
    var baseURL = window.location.href
    http.open("POST", baseURL, true);
    http.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");

    http.onreadystatechange = function() {
        if(http.readyState == 4 && http.status == 200) {
            handle_router_data(http.responseText);
        }
    }

    http.send(data_to_get);
}
