const express = require('express');
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode');
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = 3001;

// Middleware to parse JSON request bodies
app.use(express.json());

// Define a consistent path for session data
const SESSION_FILE_PATH = path.join(__dirname, 'whatsapp_session');

const client = new Client({
    authStrategy: new LocalAuth({ clientId: 'client-one', dataPath: SESSION_FILE_PATH }),
    puppeteer: {
        headless: true, // Use headless mode for server environments
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu'
        ],
    },
});

let qrData = null; // Stores the latest QR code data (base64 format)
let clientStatus = 'DISCONNECTED'; // Explicitly track the client's state

// --- Client Event Handlers for Robust Status Tracking ---

client.on('qr', (qr) => {
    console.log('QR Code Received. Broadcasting to clients.');
    clientStatus = 'QR_READY';
    qrcode.toDataURL(qr, (err, url) => {
        if (err) {
            console.error('QR code generation failed:', err);
            qrData = null;
        } else {
            qrData = url.split(',')[1]; // Store only the base64 part of the data URL
        }
    });
});

client.on('ready', () => {
    console.log('Client is ready and connected!');
    clientStatus = 'CONNECTED';
    qrData = null; // QR code is no longer needed
});

client.on('authenticated', () => {
    console.log('Session authenticated successfully.');
    clientStatus = 'CONNECTED';
});

client.on('auth_failure', (msg) => {
    console.error('Authentication Failure:', msg);
    clientStatus = 'DISCONNECTED';
});

client.on('disconnected', (reason) => {
    console.log('Client was disconnected. Reason:', reason);
    clientStatus = 'DISCONNECTED';
    qrData = null;
});

client.on('message', message => {
    if (message.body.toLowerCase() === '!ping') {
        message.reply('pong');
    }
});

// --- API Endpoints ---

// 1. Start Session/Generate QR (FIXED: Changed to POST)
app.post('/api/v1/whatsapp/start', (req, res) => {
    console.log('Received /start request.');
    if (clientStatus === 'CONNECTED' || clientStatus === 'QR_READY') {
        return res.status(400).json({ status: 'ERROR', message: `Client is already active (${clientStatus}). Please disconnect first.` });
    }

    console.log('Initializing client...');
    clientStatus = 'STARTING';
    client.initialize().catch(err => {
        console.error("Client initialization failed:", err);
        clientStatus = 'DISCONNECTED';
    });
    res.json({ status: 'STARTING', message: 'Client initialization has begun. Please poll the /status endpoint for a QR code.' });
});

// 2. Disconnect/Logout (FIXED: Changed to POST)
app.post('/api/v1/whatsapp/disconnect', (req, res) => {
    console.log('Received /disconnect request.');
    client.logout()
        .then(() => {
            res.json({ status: 'DISCONNECTED', message: 'Session has been successfully disconnected.' });
        })
        .catch(error => {
            console.error('Error during client logout:', error);
            res.status(500).json({ status: 'ERROR', message: 'An error occurred during the disconnect process.', error: error.message });
        });
});

// 3. Check Status (Correctly uses GET)
app.get('/api/v1/whatsapp/status', (req, res) => {
    let message = 'Client status is being determined.';
    let pushname = null;

    if (clientStatus === 'CONNECTED' && client.info) {
        pushname = client.info.pushname;
        message = `Connected as ${pushname} (${client.info.me.user})`;
    } else if (clientStatus === 'QR_READY') {
        message = 'QR Code is ready. Please scan it with your WhatsApp mobile app.';
    } else if (clientStatus === 'DISCONNECTED') {
        message = 'Client is disconnected. Click "Start Session" to begin.';
    } else if (clientStatus === 'STARTING') {
        message = 'Client is initializing. A QR code should be available shortly...';
    }

    res.json({
        status: clientStatus,
        message: message,
        qr: qrData, // Send the base64 QR data if it exists
        pushname: pushname,
    });
});


// 4. Send Message Endpoint (NEW)
app.post('/api/v1/whatsapp/send', async (req, res) => {
    if (clientStatus !== 'CONNECTED') {
        return res.status(400).json({ success: false, message: 'Cannot send message. WhatsApp client is not connected.' });
    }

    const { number, message } = req.body;

    if (!number || !message) {
        return res.status(400).json({ success: false, message: 'Request must include both a "number" and a "message".' });
    }

    // Format the number for whatsapp-web.js: [country_code][number]@c.us
    // Example: +923001234567 becomes 923001234567@c.us
    const chatId = `${number.replace('+', '')}@c.us`;

    try {
        await client.sendMessage(chatId, message);
        console.log(`Successfully sent message to ${number}`);
        res.json({ success: true, message: `Message successfully sent to ${number}.` });
    } catch (error) {
        console.error(`Failed to send message to ${number}:`, error);
        res.status(500).json({ success: false, message: `Failed to send message to ${number}.`, error: error.toString() });
    }
});


// --- Server Start ---
app.listen(PORT, () => {
    console.log(`WhatsApp Service is running on http://localhost:${PORT}`);
    console.log('Ready to receive commands from the Django application.');
});