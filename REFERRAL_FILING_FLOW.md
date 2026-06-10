# Referral Filing (Free Tax) - Complete Flow

## Overview

**Referral Filing (Free Tax)** is completely different from Regular Filing:

- User doesn't pay money
- Instead, user invites 5 friends to file tax returns
- When all 5 friends register, user gets free filing
- User gets a **unique referral code** to share with friends

---

## Step-by-Step Data Save Timeline

```
┌──────────────────────────────────────────────────────────────┐
│ STEP 1: User Chooses "Free Tax" Filing Type                  │
├──────────────────────────────────────────────────────────────┤
│ When: User clicks "Free Tax" button                            │
│ What: Displays Step 1 with referrer details form               │
│ Action: NO SAVE YET - just switches UI mode                   │
│                                                               │
│ Form fields shown:                                             │
│ - Referrer Name (your name)                                   │
│ - Referrer Phone (your phone)                                 │
│ - Email                                                       │
│ - PAN                                                         │
│ - City Type                                                   │
│                                                               │
│ ❌ NO DATA SAVED YET                                           │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ STEP 2: Fill 5 Referral Details                              │
├──────────────────────────────────────────────────────────────┤
│ When: User fills names and phone numbers of 5 friends         │
│ What: Shows 5 entry fields for referral names/phones          │
│ Action: NO SAVE YET - just local form entry                   │
│                                                               │
│ Form fields:                                                  │
│ - Referral 1 Name + Phone (10 digits)                         │
│ - Referral 2 Name + Phone (10 digits)                         │
│ - Referral 3 Name + Phone (10 digits)                         │
│ - Referral 4 Name + Phone (10 digits)                         │
│ - Referral 5 Name + Phone (10 digits)                         │
│                                                               │
│ UI Update: Shows milestone tracker:                           │
│ "1/5 referrals filled" → "2/5" → ... → "5/5 ✅ Unlocked"     │
│                                                               │
│ ❌ NO DATA SAVED YET                                           │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ STEP 3: Click "Reveal Code" Button (CRITICAL SAVE POINT)     │
├──────────────────────────────────────────────────────────────┤
│ When: User completes all 5 referrals + clicks "Reveal Code"   │
│ What: revealReferralCode() function called                    │
│                                                               │
│ Process:                                                       │
│                                                               │
│ 3A. Validate referrer details:                                │
│     - Name, Phone (10 digits), Email, PAN, City Type all OK?  │
│     - If not → Show alert, return                             │
│                                                               │
│ 3B. Validate all 5 referrals filled:                          │
│     - checkReferralsComplete() returns true?                  │
│     - If not → Show "Let's Play Fair!" modal, return          │
│                                                               │
│ 3C. CREATE SUBMISSION (First Save):                           │
│     ✅ Backend endpoint: POST /api/save-phase                 │
│     ✅ Saves to Google Sheets:                                │
│        - filing_category: "free"                              │
│        - name: referrer_name                                  │
│        - phone: referrer_phone (normalized to 10 digits)       │
│        - email                                                │
│        - pan                                                  │
│        - city_type                                            │
│     ✅ Backend returns: submission_id (unique ID)             │
│     ✅ Frontend stores in localStorage                        │
│                                                               │
│ 3D. GENERATE REFERRAL CODE:                                   │
│     - Code format: "XXX_YYYYY" (e.g., "RAM_A1B2C")            │
│     - First 3 chars: First 3 letters of referrer name (caps)  │
│     - Last 5 chars: Random alphanumeric                       │
│     ✅ Stored in localStorage                                 │
│                                                               │
│ 3E. SAVE REFERRAL CODE & REFERRALS (Second Save):             │
│     ✅ Backend endpoint: POST /api/save-phase                 │
│     ✅ Saves to Google Sheets:                                │
│        - submission_id                                        │
│        - referral_code: "RAM_A1B2C"                           │
│        - referrer_name                                        │
│        - referrals: JSON array of 5 friends                   │
│                                                               │
│ 3F. NOTIFY REFERRALS via WhatsApp:                            │
│     - Backend sends WhatsApp message to each friend            │
│     - Message: "RAM referred you for free tax filing!"        │
│     - Includes: referral code, link to register              │
│                                                               │
│ ✅ DATA NOW IN GOOGLE SHEETS:                                 │
│    - Referrer info (name, phone, email, pan)                  │
│    - Referral code                                            │
│    - 5 referral phone numbers                                 │
│                                                               │
│ 🎉 User sees: "CONGRATULATIONS! Your code: RAM A1B2C"         │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ STEP 4: User Continues with Filing (if desired)              │
├──────────────────────────────────────────────────────────────┤
│ When: User clicks "Claim My Free Filing" button               │
│ What: Proceeds to regular filing flow (same as regular tax)   │
│                                                               │
│ Remaining steps same as regular filing:                       │
│ - Step 2: Upload Form 16, Payslips                            │
│ - Step 3: Upload investment docs                              │
│ - Step 4: Manual entry of deductions                          │
│ - Step 5: Review & confirm                                    │
│ - Step 6: Download & submit ITR                               │
│                                                               │
│ ✅ All data saved on each "NEXT" click                         │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ BACKGROUND: Friend Registers (Auto-Update)                   │
├──────────────────────────────────────────────────────────────┤
│ When: Friend receives WhatsApp, clicks link, registers        │
│ What: Friend enters their name + phone (same as referral)     │
│ Backend Action:                                               │
│   - Matches friend's phone with referral list                 │
│   - Updates referral status: "invited" → "registered"         │
│   ✅ Saves to "Referrals" sheet in Google Sheets              │
│                                                               │
│ After 5 friends register:                                     │
│   - Original referrer's status: "eligible for free filing"   │
│   - Friend's files tax → reduces free filing quota            │
└──────────────────────────────────────────────────────────────┘
```

---

## Data Saved to Google Sheets - Timeline

### **Save Point 1: When User Clicks "Reveal Code"**

**Endpoint:** `POST /api/save-phase`

**Data Saved to Main Sheet:**
```
Column          | Value
────────────────┼──────────────────────
submission_id   | abc-123-def (UUID)
filing_category | "free"
name            | "Rajesh Kumar"
phone           | "9876543210"
email           | "rajesh@email.com"
pan             | "ABCDE1234F"
city_type       | "metro"
timestamp       | Current date/time
```

**Response from Backend:**
```json
{
  "success": true,
  "submission_id": "abc-123-def",
  "referral_code": ""
}
```

---

### **Save Point 2: After Referral Code Generated**

**Endpoint:** `POST /api/save-phase` (Second call)

**Additional Data Saved:**
```
Column          | Value
────────────────┼──────────────────────
referral_code   | "RAM_A1B2C"
referrals       | ["Aman", "Bhavna", "Chirag", "Diya", "Esha"]
ref_phone_1     | "9111111111"
ref_phone_2     | "9222222222"
ref_phone_3     | "9333333333"
ref_phone_4     | "9444444444"
ref_phone_5     | "9555555555"
```

---

### **Auto-Update: When Friend Registers**

**Sheet:** "Referrals" (separate sheet)

**Saved Data:**
```
referrer_phone      | 9876543210
referred_phone      | 9111111111 (friend's phone)
referred_name       | "Aman"
status              | "registered" (auto-updated)
registration_date   | Current date/time
```

---

## Code Flow Diagram

```
User selects "Free Tax" on Step 1
        ↓
showReferralUI()
        ↓
User fills 5 referral names/phones
        ↓
User enters their own details (name, phone, email, pan)
        ↓
User clicks "Reveal Code" button
        ↓
revealReferralCode() function:
  │
  ├─ Validate referrer details (name, phone, email, pan)
  │  └─ If invalid → Show alert, return
  │
  ├─ Validate 5 referrals complete
  │  └─ If not → Show "Let's Play Fair" modal, return
  │
  ├─ Create submission:
  │  └─ POST /api/save-phase {filing_category: "free", ...}
  │  └─ Backend saves to Sheets
  │  └─ Returns submission_id
  │
  ├─ Generate referral code
  │  └─ Format: "RAM_A1B2C"
  │  └─ Store in localStorage
  │
  ├─ Save referral code + list:
  │  └─ POST /api/save-phase {referral_code, referrals, ...}
  │  └─ Backend saves to Sheets
  │
  └─ Notify referrals via WhatsApp
     └─ POST /api/notify-referrals
     └─ Sends message to each friend
        
        ↓
Show "CONGRATULATIONS!" modal with code
        ↓
User can proceed with filing or wait for friends to register
```

---

## Key Differences: Regular vs Referral Filing

| Aspect | Regular Filing | Referral (Free) Filing |
|--------|---|---|
| **When saved** | On Step 1 → NEXT | On "Reveal Code" click |
| **First save** | Name, phone, email, PAN | Name, phone, email, PAN |
| **Second save** | N/A | Referral code + list |
| **Payment** | ✅ Required | ❌ Free (if 5 register) |
| **Referrals** | Optional | ✅ Required (5 friends) |
| **Referral code** | Generated later | Generated immediately |
| **Frontend validation** | Step 1 → Step 2 flow | Name/Phone/Referrals |

---

## Testing Referral Flow Locally

### **Step 1: Start Backend**
```bash
cd backend
pip install -r requirements.txt
python app.py
```

### **Step 2: Start Frontend**
```bash
cd frontend
python -m http.server 8000
```

### **Step 3: Test Referral Filing**

1. Open `http://localhost:8000/filing.html`
2. (Or navigate to filing page)
3. **Click "Free Tax"** button
4. Enter:
   - Your name: "Rajesh Kumar"
   - Your phone: "9876543210" (10 digits)
   - Your email: "test@example.com"
   - Your PAN: "ABCDE1234F"
   - City type: "metro"
5. Fill 5 referral names/phones:
   - Aman: 9111111111
   - Bhavna: 9222222222
   - Chirag: 9333333333
   - Diya: 9444444444
   - Esha: 9555555555
6. **Click "Reveal Code"** button
7. **Check logs:**
   ```
   [SAVE_PHASE] Create submission for free filing
   [SAVE_PHASE] Saved referral code: RAM_XXXXX
   [UPLOAD_DOCUMENT] Or similar
   ```
8. **Check Google Sheet:**
   - New row should appear with your details
   - `referral_code` column should have code
   - `filing_category` = "free"

---

## Common Issues Testing Referral Flow

### **Issue: "Let's Play Fair!" modal keeps showing**
```
Cause: Not all 5 referrals filled correctly
Solution:
1. Verify all 5 rows have Name + Phone
2. Phone must be 10 digits (numeric only)
3. Try: 9111111111, 9222222222, etc.
4. Click "Reveal Code" again
```

### **Issue: "Please fill all your details" alert**
```
Cause: Your (referrer) details incomplete
Solution:
1. Name - required, any name OK
2. Phone - required, 10 digits
3. Email - required, must be valid (test@example.com OK)
4. PAN - required, any text OK (ABCDE1234F)
5. City Type - required, select "metro" or "non-metro"
6. Try again
```

### **Issue: Data not appearing in Google Sheet**
```
Cause: Google Sheets credentials not configured
Solution:
1. Set environment variables:
   $env:GOOGLE_SERVICE_ACCOUNT_JSON = '{"type":"service_account",...}'
   $env:GOOGLE_SHEET_ID = 'your-sheet-id'
2. Share sheet with service account email
3. Restart backend
4. Try again
```

### **Issue: WhatsApp notification not sent**
```
Cause: WhatsApp API not configured (non-critical)
Solution:
1. Check logs for [NOTIFY_REFERRALS] errors
2. If "not configured", that's OK - non-blocking
3. Referral code is still saved to Sheets
4. Manual WhatsApp notification OK
```

---

## Summary: When Data is Saved (Referral Filing)

1. **On "Reveal Code" click:**
   - ✅ Referrer details saved (name, phone, email, PAN)
   - ✅ Submission created with submission_id
   - ✅ Referral code generated

2. **Immediately after code generation:**
   - ✅ Referral code + 5 phone numbers saved
   - ✅ WhatsApp messages sent to friends

3. **When friend registers:**
   - ✅ Referral status updated to "registered"
   - ✅ Referrer can proceed with filing

4. **During filing:**
   - ✅ Same as regular filing (documents, deductions, etc.)

---

**Key Point:** Referral filing has TWO critical save points:
1. When user creates submission (referrer details)
2. When referral code is generated (with 5 referral phones)

Both must succeed for free filing to work!
