# WhatsApp Automation Requirements for FairTax Backend

## Overview
This document outlines the WhatsApp automation features required for the FairTax platform to engage users and encourage referrals.

---

## 1. REFERRAL STATUS REPORT (3-Day Automation)

### Frequency
- Every 2-3 days automatically
- Send to user's WhatsApp number collected during signup

### Content to Include
```
📊 Your FairTax Referral Status

Total Referrals: [COUNT]
Referrals Filed: [COUNT] 
Your Earnings: ₹[AMOUNT]
Cashback Unlocked: ₹[AMOUNT]

🎯 Next Milestone: Refer [X] more friends to unlock ₹[AMOUNT]

---
💰 Refer & Earn Bonanza:
Refer 1 → ₹250
Refer 3 → ₹1,000
Refer 5 → FREE + ₹5,000
Refer 10 → ₹15,000

Check your wallet: [LINK to wallet.html]
```

### Implementation Details
- Query user's referral database
- Calculate completed referral count from database
- Calculate current earnings/cashback status
- Format as WhatsApp message
- Send via WhatsApp API (Twilio, WhatsApp Business API, etc.)
- Track delivery status in logs

---

## 2. ENGAGEMENT REMINDER MESSAGES

### Message Sequence (Optional, every 2-3 days)

#### Message 1: Referral Reminder
```
Have you referred your friends yet? 👋

Get ₹250-₹15,000 cashback just by sharing FairTax!
Your referral code: [CODE]

Share and earn →  [LINK]
```

#### Message 2: Wallet Check
```
Hurray! 🎉 Have you checked your wallet?

Your earnings may be waiting!
Check wallet → [LINK]
```

#### Message 3: Refund Status Update
```
Have you checked your filing status? 📋

See your ITR filing progress now →  [LINK]
```

### Implementation Details
- Store user's phone number during signup (Step 1, field: referrer_phone)
- Create schedule/cron job to send at 2-3 day intervals
- Personalize with user's referral code
- Include clickable links to relevant pages
- Track message delivery and user engagement

---

## 3. WITHDRAWAL NOTIFICATION

### Trigger
When user submits withdrawal request from Wallet (wallet.html)

### Content
```
💳 Withdrawal Request Submitted

Amount: ₹[AMOUNT]
UPI ID: [UPI_ID]
Referral Code: [CODE]
Number of Referrals: [COUNT]
Filing Status: [PENDING/COMPLETED]

Your cashback will be credited within 24 hours on next payout day (Thursday 3:30 PM).

---
⚠️ Admin Alert Sent
Our team has been notified. You'll receive confirmation on WhatsApp.
```

### Admin Notification (Internal)
Send to [ADMIN_WHATSAPP_NUMBERS] (two numbers to be configured):
```
🔔 WITHDRAWAL REQUEST

Taxpayer: [NAME]
Phone: [PHONE]
Amount: ₹[AMOUNT]
UPI: [UPI_ID]
Referral Code: [CODE]
Total Referrals: [COUNT]
Filing Status: [STATUSES]

Action: Process payment on next Thursday 3:30 PM
```

### Implementation Details
- Fetch admin phone numbers from env config (comma-separated)
- Send withdrawal request details to both admin numbers
- Store withdrawal request in database with timestamp
- Track payment status in Excel sheet
- Update user record with payment confirmation

---

## 4. FILING COMPLETION NOTIFICATION

### Trigger
When a user's ITR filing status is marked as "COMPLETED" by auditor in backend system

### Content to User
```
✅ Congratulations! Your ITR Filing is Complete

Filing Status: COMPLETED
Your Refund: ₹[AMOUNT]
Option Selected: [Option A/B/C]

Expected Payout: [DATE]

---
Don't forget to refer your friends! Share and earn up to ₹15,000
Your referral code: [CODE]

Refer now → [LINK]
```

### Trigger for Referrers (Users who referred them)
When a referral's filing is completed:
```
🎉 Great news! One of your referrals has completed filing

Your new wallet balance: ₹[NEW_BALANCE]
Total referrals completed: [COUNT]

Check your wallet → [LINK]
```

### Implementation Details
- Query completion status from database
- Identify all referrals of the main user
- Send to referring user (person who referred them)
- Update referrer's wallet balance
- Log transaction in audit trail

---

## 5. QUOTE READY NOTIFICATION

### Trigger
When quote PDF is ready (after auditor approval)

### Content
```
📄 Your Tax Quote is Ready!

Your personalized 3-option tax analysis is ready.

We'll send you a password-protected PDF within the next hour.

Once received, simply reply:
- Option A
- Option B  
- Option C

Based on your income and deductions, we recommend the option that gives you the maximum refund.

Have questions? Talk to our experts → [WHATSAPP_LINK]
```

### Implementation Details
- Trigger when auditor marks filing as "approved_quote_ready"
- Send WhatsApp message with instructions
- Later: Send PDF link via WhatsApp (after file upload to secure server)
- Listen for user response (Option A/B/C) via WhatsApp webhook
- Store user choice in database column "user_chosen_option"

---

## 6. PAYMENT RECEIVED CONFIRMATION

### Trigger
When payment screenshot is uploaded and marked as verified

### Content
```
💰 Payment Received - Thank You!

We've received your initial payment (50% of filing fee).

Your filing is now in progress.
You'll receive your refund within 7-10 working days (Option A), 3-5 days (Option B), or invested for 6 months (Option C).

Track your filing status → [LINK]
```

### Implementation Details
- Auto-trigger when payment_status = "verified"
- Send confirmation message
- Update excel sheet with "Payment Received: YES"
- Set flag for "Filing In Progress"

---

## 7. WEEKLY WINNERS ANNOUNCEMENT

### Trigger
Every Friday/Saturday at fixed time (e.g., 6 PM)

### Content
```
🏆 Weekly FairTax Winners! 🏆

Congratulations to this week's top referrers:

🥇 [NAME] - [COUNT] referrals
🥈 [NAME] - [COUNT] referrals
🥉 [NAME] - [COUNT] referrals

You could be next week's winner! Start referring now →  [LINK]

Join thousands who are earning ₹250-₹15,000 with FairTax! 🎁
```

### Implementation Details
- Query database for top 3 referrers (by referral_count) for current week
- Sort by count (descending)
- Format as WhatsApp message
- Send to broadcast group or individual messages based on config
- Store in "weekly_winners" table for audit trail
- Display on website's Winners Widget (already implemented in landing.html, wallet.html)

---

## 8. SYSTEM CONFIGURATION

### Required Environment Variables
```
WHATSAPP_API_KEY=<your-api-key>
WHATSAPP_PHONE_NUMBER=<business-phone>
ADMIN_WHATSAPP_NUMBERS=<number1,number2>  # Comma-separated
REFERRAL_REMINDER_INTERVAL=<3-days>
REFERRAL_REMINDER_ENABLED=true
WINNERS_ANNOUNCEMENT_DAY=Friday
WINNERS_ANNOUNCEMENT_TIME=18:00  # 24-hour format
```

### Required Database Columns
- `user_phone` - User's phone number (Step 1)
- `referral_code` - Generated code (Step 7)
- `referral_count` - Number of successful referrals
- `wallet_balance` - Current cashback balance
- `filing_status` - Current filing status
- `last_reminder_sent` - Timestamp of last automated message
- `last_payment_reminder_sent` - Timestamp of payment reminder
- `withdrawal_requests` - Table for withdrawal tracking
- `user_chosen_option` - Which refund option user selected (A/B/C)
- `payment_status` - verified/pending/failed

### WhatsApp API Integration (Recommended)
- **Twilio**: Easy integration, reliable, ~₹0.50-1 per message
- **WhatsApp Business API**: Direct integration with Meta, more features
- **MessageBird**: Alternative provider with good India coverage

### Scheduling Strategy
- Use **cron jobs** (Node cron, APScheduler, etc.) for automated triggers
- Store last_sent timestamp to avoid duplicate messages
- Implement message queue to handle failures gracefully
- Log all messages sent for audit and debugging

---

## 9. User Engagement Metrics to Track

### Dashboard/Admin Panel (Future Feature)
- Message delivery rate
- Message open rate (if supported by provider)
- Click-through rate on links
- User response rate (Option A/B/C selections)
- Conversion rate (referral → filing)
- Withdrawal request conversion rate

---

## 10. Privacy & Compliance

### GDPR/India Privacy Laws
- ✅ Store explicit opt-in for marketing messages (consent checkbox in Step 1)
- ✅ Provide unsubscribe option in every message ("Reply STOP to unsubscribe")
- ✅ Encrypt phone numbers in database
- ✅ Don't share phone numbers with third parties without consent
- ✅ Implement data retention policy (delete after X months if inactive)

### WhatsApp Business Policy
- ✅ Only send messages within 24-hour window (except user-initiated conversations)
- ✅ Use template messages for marketing content (not free-form)
- ✅ Don't use automated bots to respond to user messages
- ✅ Maintain sender reputation score

---

## 11. Implementation Priorities

### Phase 1 (MVP - High Priority)
1. Withdrawal notification to admin (Issue #12)
2. Filing completion notification to user
3. Quote ready notification

### Phase 2 (Medium Priority)
4. 3-day referral status report
5. Weekly winners announcement

### Phase 3 (Low Priority)
6. Engagement reminder messages (1-3 per week)
7. Advanced analytics dashboard

---

## 12. Testing Checklist

- [ ] Test message delivery with test phone numbers
- [ ] Verify message formatting (line breaks, emojis)
- [ ] Test personalization variables ([NAME], [AMOUNT], etc.)
- [ ] Verify links are clickable and not broken
- [ ] Test with different phone carriers
- [ ] Verify opt-in/opt-out functionality
- [ ] Monitor delivery rate and troubleshoot failures
- [ ] Test with production database (staging environment first)
- [ ] Verify timestamps are correct (timezone handling)
- [ ] Test with special characters in data

---

## 13. Future Enhancements

- WhatsApp payment integration (P2P transfers)
- Scheduled appointment booking via WhatsApp
- File upload via WhatsApp (alternative to web form)
- Tax tips/educational messages based on user profile
- Multi-language support (Hindi, Tamil, etc.)
- Voice message updates

---

**Status**: Approved for Development
**Owner**: Backend Team
**Estimated Effort**: 40-60 hours (depending on API choice)
**Start Date**: [TBD]

