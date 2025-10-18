document.addEventListener('DOMContentLoaded', function() {
    // --- Element References ---
    const statusContainer = document.getElementById('status-container');
    const statusText = document.getElementById('status-text');
    const qrImage = document.getElementById('qr-image');
    const startBtn = document.getElementById('start-session-btn');
    const disconnectBtn = document.getElementById('disconnect-session-btn');
    const connectedInfo = document.getElementById('connected-info');
    const connectedUser = document.getElementById('connected-user');

    // --- API URLs (from Django template tags) ---
    const startUrl = statusContainer.dataset.startUrl;
    const statusUrl = statusContainer.dataset.statusUrl;
    const disconnectUrl = statusContainer.dataset.disconnectUrl;

    let statusInterval;

    // --- UI Update Function ---
    function updateUI(state) {
        // Default states
        statusContainer.className = 'status-box'; // Reset class
        qrImage.style.display = 'none';
        startBtn.style.display = 'none';
        disconnectBtn.style.display = 'none';
        connectedInfo.style.display = 'none';
        startBtn.disabled = false;
        disconnectBtn.disabled = false;

        statusText.textContent = state.message || '...';

        if (state.status === 'CONNECTED') {
            statusContainer.classList.add('status-connected');
            disconnectBtn.style.display = 'inline-block';
            connectedInfo.style.display = 'block';
            connectedUser.textContent = state.pushname || 'Unknown';
            if (statusInterval) clearInterval(statusInterval);
        } else if (state.status === 'QR_READY') {
            statusContainer.classList.add('status-qr');
            if (state.qr) {
                qrImage.src = 'data:image/png;base64,' + state.qr;
                qrImage.style.display = 'block';
            }
            disconnectBtn.style.display = 'inline-block'; // Can disconnect during QR stage
        } else if (state.status === 'DISCONNECTED') {
            statusContainer.classList.add('status-disconnected');
            startBtn.style.display = 'inline-block';
        } else if (state.status === 'STARTING') {
            statusContainer.classList.add('status-starting');
            startBtn.disabled = true;
        } else { // Error state
            statusContainer.classList.add('status-error');
            startBtn.style.display = 'inline-block';
        }
    }

    // --- API Call Functions ---
    async function checkStatus() {
        try {
            const response = await fetch(statusUrl);
            const data = await response.json();
            updateUI(data);
        } catch (error) {
            console.error('Status check failed:', error);
            updateUI({ status: 'ERROR', message: 'Could not connect to the server. Is it running?' });
            if (statusInterval) clearInterval(statusInterval);
        }
    }

    async function startSession() {
        updateUI({ status: 'STARTING', message: 'Initializing session... Please wait.' });
        try {
            const response = await fetch(startUrl, { method: 'POST' });
            const data = await response.json();
            updateUI(data);

            // Start polling for status immediately after requesting start
            if (statusInterval) clearInterval(statusInterval);
            statusInterval = setInterval(checkStatus, 4000); // Poll every 4 seconds
            setTimeout(checkStatus, 1000); // Check once quickly
        } catch (error) {
            console.error('Start session failed:', error);
            updateUI({ status: 'ERROR', message: 'Failed to start the session.' });
        }
    }

    async function disconnectSession() {
        updateUI({ status: 'STARTING', message: 'Disconnecting...' });
        if (statusInterval) clearInterval(statusInterval);
        try {
            const response = await fetch(disconnectUrl, { method: 'POST' });
            const data = await response.json();
            updateUI({ status: 'DISCONNECTED', message: data.message || 'Successfully disconnected.' });
        } catch (error) {
            console.error('Disconnect failed:', error);
            updateUI({ status: 'ERROR', message: 'Failed to disconnect.' });
        }
    }

    // --- Event Listeners ---
    startBtn.addEventListener('click', startSession);
    disconnectBtn.addEventListener('click', disconnectSession);

    // --- Initial Load ---
    // Start polling immediately on page load to get the current state
    checkStatus();
    statusInterval = setInterval(checkStatus, 8000); // And then poll every 8 seconds
});