// Global utility functions
document.addEventListener('DOMContentLoaded', function() {
    console.log('Temperature Monitoring System loaded!');
});

// Utility functions
function showAlert(message, type = 'info') {
    alert(message);
}

function formatTemperature(temp) {
    return parseFloat(temp).toFixed(1) + '°C';
}