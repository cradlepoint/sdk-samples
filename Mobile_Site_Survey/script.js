// api url
const api_url =
    "/config";

// Defining async function
async function getapi(url) {

    // Storing response
    const response = await fetch(url);

    // Storing data in form of JSON
    var config = await response.json();
    console.log(config);
    loadForm(config);
}

// Function to load dynamic form
function loadForm(config) {
    $('#enabled').attr('checked', config.enabled);
    $('#min_distance').attr('value', config.min_distance);
    $('#enable_timer').attr('checked', config.enable_timer);
    $('#min_time').attr('value', config.min_time);
    $('#all_wans').attr('checked', config.all_wans);
    $('#speedtests').attr('checked', config.speedtests);
    $('#packet_loss').attr('checked', config.packet_loss);
    $('#write_csv').attr('checked', config.write_csv);
    $('#send_to_server').prop('checked', config.send_to_server);
    $('#full_diagnostics').prop('checked', config.full_diagnostics);
    $('#include_logs').prop('checked', config.include_logs);
    $('#server_url').attr('value', config.server_url);
    $('#server_token').attr('value', config.server_token);
    $('#enable_surveyors').prop('checked', config.enable_surveyors);
    $('#surveyors').attr('value', config.surveyors);
    $('#debug').attr('checked', config.debug);
    $('#version').text('Mobile Site Survey v' + config.version);
    if (config.results) {
        $('#results').val(config.results);
    }
}

// Calling that async function
getapi(api_url);
