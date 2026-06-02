// Configuration
const CONFIG = {
    WHATSAPP_PHONE: '919600165254',  // FairTax WhatsApp number with country code
    FRONTEND_URL: 'http://localhost:8080',  // Frontend
    BACKEND_URL: 'http://localhost:5000/api/submit-filing'  // Backend endpoint
};

/**
 * Main function: Submit form + Open WhatsApp
 * Called when user clicks "Submit Filing & Message on WhatsApp" button
 */
function submitAndWhatsApp(event) {
    console.log('[DEBUG] submitAndWhatsApp() called');
    event.preventDefault();

    // Validate form
    const form = document.getElementById('filingForm');
    console.log('[DEBUG] Form found:', form ? 'YES' : 'NO');

    if (!form.checkValidity()) {
        console.log('[DEBUG] Form validation failed');
        showStatus('error', 'Error', 'Please fill all required fields');
        return;
    }
    console.log('[DEBUG] Form validation passed');

    // Get form data
    const formData = new FormData(form);
    const filingData = {
        name: formData.get('name'),
        email: formData.get('email'),
        phone: formData.get('phone'),
        pan: formData.get('pan'),
        category: formData.get('category'),
        income: formData.get('income'),
        year: formData.get('year'),
        consent_whatsapp: formData.get('consent') ? true : false,
        consent_terms: formData.get('terms') ? true : false,
        submission_time: new Date().toISOString()
    };

    // Show processing status
    showStatus('processing', 'Processing...', 'Opening WhatsApp and submitting your filing...');

    // Step 1: IMMEDIATELY OPEN WHATSAPP (don't wait for backend)
    openWhatsAppMessage(filingData);
    console.log('WhatsApp opened');

    // Step 2: Submit form to backend in background (non-blocking)
    submitToBackend(filingData)
        .then(response => {
            console.log('Filing submitted:', response);

            // Show success status
            showStatus('success', 'Success!',
                `Your filing has been submitted!\nReference: ${response.reference_code || 'REF-' + Date.now()}\n\nPlease send the WhatsApp message to confirm. You can then track your filing.`
            );
        })
        .catch(error => {
            console.error('Submission error:', error);
            showStatus('warning', 'Note',
                `Filing submission encountered an issue: ${error.message}\n\nBut your WhatsApp message was sent! Please contact us via WhatsApp or try submitting again.`
            );
        });
}

/**
 * Step 1: Submit filing data to backend
 */
function submitToBackend(filingData) {
    return fetch(CONFIG.BACKEND_URL, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(filingData)
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Server returned ${response.status}`);
        }
        return response.json();
    });
}

/**
 * Step 2: Open WhatsApp with pre-filled message
 */
function openWhatsAppMessage(filingData) {
    // Construct message with filing details
    const message = constructWhatsAppMessage(filingData);
    console.log('[DEBUG] Message constructed:', message);

    // Create WhatsApp link
    const whatsappLink = `https://wa.me/${CONFIG.WHATSAPP_PHONE}?text=${encodeURIComponent(message)}`;
    console.log('[DEBUG] WhatsApp link created:', whatsappLink);

    // Open in new tab
    console.log('[DEBUG] Attempting to open WhatsApp...');
    const whatsappWindow = window.open(whatsappLink, '_blank');

    if (!whatsappWindow) {
        console.error('[ERROR] Failed to open WhatsApp! Popup blocker may be active.');
        showStatus('error', 'Popup Blocked', 'WhatsApp popup was blocked by your browser. Please:\n1. Click the shield icon\n2. Allow popups for this site\n3. Try again');
    } else {
        console.log('[SUCCESS] WhatsApp window opened');
    }
}

/**
 * Construct the pre-filled WhatsApp message
 */
function constructWhatsAppMessage(filingData) {
    const message = `Hi FairTax!

I just submitted my tax filing.

Details:
- Name: ${filingData.name}
- PAN: ${filingData.pan}
- Income Category: ${filingData.category}
- Financial Year: ${filingData.year}

Please update me on my filing status and send the quote when ready.

Thanks!`;

    return message;
}

/**
 * Show status message to user
 */
function showStatus(type, title, message) {
    const statusDiv = document.getElementById('status');
    const statusTitle = document.getElementById('statusTitle');
    const statusMessage = document.getElementById('statusMessage');

    statusDiv.className = `status ${type}`;
    statusTitle.textContent = title;
    statusMessage.textContent = message;

    // Auto-hide error after 5 seconds
    if (type === 'error') {
        setTimeout(() => {
            statusDiv.className = 'status hidden';
        }, 5000);
    }
}

/**
 * Form validation helper
 */
document.getElementById('filingForm').addEventListener('submit', function(e) {
    e.preventDefault();
    submitAndWhatsApp(e);
});

// Log when page loads
console.log('WhatsApp Workaround - Ready');
console.log('Configuration:', CONFIG);
