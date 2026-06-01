# 🗺️ FAIRTAX — DETAILED IMPLEMENTATION ROADMAP
**Document Date:** May 27, 2026  
**Status:** Ready for execution  
**Estimated Timeline:** 16-20 weeks to full platform  

---

## PART A: PHASE 1 — SECURE & STABILIZE (Weeks 1-3)

### Module 1.1: OTP-Based Authentication System (Week 1-2)
**Priority:** 🔴 CRITICAL  
**Effort:** Medium (80-100 hours)  
**Files to Create:**
- `backend/auth_service.py` (OTP generation, validation, session management)
- `backend/models/user.py` (User model)
- `backend/models/otp_log.py` (OTP tracking for rate limiting)
- `backend/middleware/auth.py` (Session verification middleware)
- `frontend/auth.html` (Login/signup page)

**Implementation Steps:**

1. **Database Schema** (if using PostgreSQL)
   ```sql
   CREATE TABLE users (
     id UUID PRIMARY KEY,
     phone VARCHAR(10) UNIQUE NOT NULL,
     name VARCHAR(255),
     email VARCHAR(255),
     pan VARCHAR(10),
     created_at TIMESTAMP,
     last_login TIMESTAMP,
     verified BOOLEAN DEFAULT false
   );

   CREATE TABLE otp_log (
     id UUID PRIMARY KEY,
     phone VARCHAR(10),
     otp_hash VARCHAR(255),
     created_at TIMESTAMP,
     expires_at TIMESTAMP,
     attempts INT DEFAULT 0,
     verified BOOLEAN DEFAULT false
   );

   CREATE TABLE sessions (
     id UUID PRIMARY KEY,
     user_id UUID REFERENCES users(id),
     token VARCHAR(255) UNIQUE,
     created_at TIMESTAMP,
     expires_at TIMESTAMP
   );
   ```

2. **Backend Implementation** (auth_service.py)
   ```python
   def generate_otp(phone: str) -> str:
       # Generate 6-digit OTP
       # Store hash in otp_log table
       # Send via SMS/WhatsApp
       # Return: {"otp_id": "xxx", "expires_in": 300}

   def verify_otp(phone: str, otp: str) -> dict:
       # Check OTP against hash
       # Enforce rate limits (3 attempts max)
       # Create user if not exists
       # Create session
       # Return: {"success": bool, "session_token": "xxx"}

   def validate_session(token: str) -> dict:
       # Check token validity and expiry
       # Return user data or error

   def refresh_token(token: str) -> str:
       # Extend token expiry
       # Return new token
   ```

3. **Middleware** (auth.py)
   ```python
   @app.before_request
   def check_auth():
       # Skip for public endpoints (/api/health, /whatsapp/webhook, /api/login)
       # Verify session token from Authorization header
       # Attach user to request context
       # Reject if invalid
   ```

4. **API Endpoints**
   ```
   POST /api/auth/request-otp
     Input: {"phone": "9876543210"}
     Output: {"otp_id": "xxx", "expires_in": 300}

   POST /api/auth/verify-otp
     Input: {"phone": "9876543210", "otp": "123456"}
     Output: {"session_token": "xxx", "user": {id, phone, name, ...}}

   POST /api/auth/logout
     Input: {} (header: Authorization: Bearer token)
     Output: {"success": true}
   ```

5. **Frontend Changes**
   - Add `auth.html` page with OTP entry
   - Modify landing page to require login
   - Store session token in localStorage
   - Add Authorization header to all API calls

**Testing:**
- Test OTP generation and expiry
- Test rate limiting (3 attempts)
- Test session token validation
- Test concurrent sessions
- Test token refresh

---

### Module 1.2: Rate Limiting & Security Hardening (Week 2)
**Priority:** 🔴 CRITICAL  
**Effort:** Medium (60-80 hours)  
**Files to Create:**
- `backend/middleware/rate_limiting.py` (Rate limit decorator)
- `backend/middleware/input_validation.py` (Input sanitization)
- `backend/config/security.py` (Security headers)

**Implementation:**

1. **Rate Limiting** (per endpoint)
   ```python
   from flask_limiter import Limiter

   limiter = Limiter(
       app=app,
       key_func=get_remote_address,
       default_limits=["200 per day", "50 per hour"]
   )

   @app.route("/api/auth/request-otp")
   @limiter.limit("3 per minute per ip")
   def request_otp():
       # OTP requests: max 3 per minute per IP
       pass

   @app.route("/api/extract")
   @limiter.limit("10 per minute per user")
   def extract():
       # Extract endpoint: max 10 per minute per authenticated user
       pass
   ```

2. **Input Validation**
   ```python
   def validate_phone(phone: str) -> bool:
       digits = ''.join(c for c in phone if c.isdigit())
       return len(digits) == 10 and digits[0] != '0'

   def validate_pan(pan: str) -> bool:
       return len(pan) == 10 and pan.isupper()

   def sanitize_string(s: str) -> str:
       # Remove special characters except allowed
       # Trim whitespace
       return s.strip()[:255]  # Limit length
   ```

3. **Security Headers**
   ```python
   @app.after_request
   def set_security_headers(response):
       response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
       response.headers['X-Content-Type-Options'] = 'nosniff'
       response.headers['X-Frame-Options'] = 'DENY'
       response.headers['Content-Security-Policy'] = "default-src 'self'"
       return response
   ```

4. **CSRF Protection**
   ```python
   from flask_wtf.csrf import CSRFProtect
   csrf = CSRFProtect(app)

   # For API endpoints: use token in header
   # X-CSRFToken: <token>
   ```

---

### Module 1.3: Comprehensive Audit Logging (Week 2-3)
**Priority:** 🟠 HIGH  
**Effort:** Medium (40-50 hours)  
**Files to Create:**
- `backend/models/audit_log.py` (Audit log model)
- `backend/services/audit_service.py` (Audit logging service)
- `backend/middleware/audit_logger.py` (Audit middleware)

**Implementation:**

1. **Audit Log Schema**
   ```sql
   CREATE TABLE audit_logs (
     id UUID PRIMARY KEY,
     user_id UUID REFERENCES users(id),
     action VARCHAR(100),  -- 'LOGIN', 'FILE_UPLOADED', 'QUOTED', 'PAID', etc.
     resource_type VARCHAR(50),  -- 'user', 'filing', 'referral'
     resource_id VARCHAR(100),
     old_value TEXT,  -- For changes
     new_value TEXT,
     ip_address VARCHAR(50),
     user_agent TEXT,
     created_at TIMESTAMP,
     status VARCHAR(20)  -- 'success', 'failure'
   );
   ```

2. **Audit Service**
   ```python
   def log_action(user_id: str, action: str, resource_type: str, 
                  resource_id: str, old_value=None, new_value=None,
                  ip_address=None, user_agent=None, status='success'):
       # Create audit log entry
       # Log to file + database for redundancy
       pass

   # Usage:
   audit_service.log_action(
       user_id=current_user.id,
       action='FILING_SUBMITTED',
       resource_type='filing',
       resource_id=submission_id,
       old_value=json.dumps(old_data),
       new_value=json.dumps(new_data),
       ip_address=request.remote_addr,
       user_agent=request.user_agent.string,
       status='success'
   )
   ```

3. **Key Events to Log**
   - User registration / login / logout
   - Document upload / deletion
   - Filing submission
   - Payment attempt / success / failure
   - Referral added / verified
   - Admin actions (approve quote, adjust fees, etc.)
   - Data access (viewing others' data)

---

**END OF PHASE 1**

---

## PART B: PHASE 2 — CORE FUNCTIONALITY (Weeks 4-7)

### Module 2.1: Razorpay Payment Integration (Week 4-5)
**Priority:** 🔴 CRITICAL  
**Effort:** High (100-120 hours)  
**Files to Create:**
- `backend/services/payment_service.py` (Razorpay integration)
- `backend/models/payment.py` (Payment model)
- `backend/models/order.py` (Order model)
- `frontend/payment.html` (Payment checkout page)

**Implementation:**

1. **Database Schema**
   ```sql
   CREATE TABLE orders (
     id UUID PRIMARY KEY,
     submission_id UUID REFERENCES filings(id),
     user_id UUID REFERENCES users(id),
     amount_paise INT,  -- ₹500 = 50000 paise
     status VARCHAR(20),  -- 'created', 'pending', 'paid', 'failed'
     razorpay_order_id VARCHAR(100),
     created_at TIMESTAMP,
     expires_at TIMESTAMP
   );

   CREATE TABLE payments (
     id UUID PRIMARY KEY,
     order_id UUID REFERENCES orders(id),
     razorpay_payment_id VARCHAR(100),
     razorpay_signature VARCHAR(255),
     amount_paise INT,
     status VARCHAR(20),  -- 'authorized', 'captured', 'failed', 'refunded'
     created_at TIMESTAMP,
     updated_at TIMESTAMP
   );

   CREATE TABLE refunds (
     id UUID PRIMARY KEY,
     payment_id UUID REFERENCES payments(id),
     razorpay_refund_id VARCHAR(100),
     amount_paise INT,
     reason VARCHAR(255),
     created_at TIMESTAMP
   );
   ```

2. **Payment Service**
   ```python
   import razorpay

   client = razorpay.Client(
       auth=(Config.RAZORPAY_KEY_ID, Config.RAZORPAY_KEY_SECRET)
   )

   def create_order(submission_id: str, amount: float) -> dict:
       # Create Razorpay order
       order = client.order.create(data={
           'amount': int(amount * 100),  # Convert to paise
           'currency': 'INR',
           'receipt': f'receipt_{submission_id}'
       })
       # Save to orders table
       return {'order_id': order['id'], 'amount': amount}

   def verify_payment(razorpay_order_id: str, razorpay_payment_id: str,
                     razorpay_signature: str) -> bool:
       # Verify signature
       # Mark payment as verified
       # Update filing status
       # Trigger notification
       pass

   def create_refund(payment_id: str, amount: float, reason: str) -> dict:
       # Create refund in Razorpay
       # Update database
       # Notify user
       pass
   ```

3. **API Endpoints**
   ```
   POST /api/payments/create-order
     Input: {"submission_id": "xxx"}
     Output: {"order_id": "order_xxx", "amount": 500}

   POST /api/payments/verify
     Input: {
       "order_id": "order_xxx",
       "payment_id": "pay_xxx",
       "signature": "sig_xxx"
     }
     Output: {"success": true, "status": "PAID"}

   POST /api/payments/refund
     Input: {"order_id": "order_xxx", "reason": "User requested"}
     Output: {"refund_id": "rfnd_xxx"}
   ```

4. **Frontend Implementation**
   - Razorpay script integration
   - Payment button with Razorpay options
   - Signature verification on client
   - Payment success/failure handling

---

### Module 2.2: Referral Tracking & Status History (Week 5)
**Priority:** 🟠 HIGH  
**Effort:** High (100-110 hours)  
**Files to Create:**
- `backend/models/referral.py` (Referral model)
- `backend/models/referral_status.py` (Referral status history)
- `backend/services/referral_service.py` (Referral logic)

**Implementation:**

1. **Database Schema**
   ```sql
   CREATE TABLE referrals (
     id UUID PRIMARY KEY,
     referrer_id UUID REFERENCES users(id),
     referred_user_id UUID REFERENCES users(id),
     referral_code VARCHAR(20) UNIQUE,
     status VARCHAR(50),  -- 'invited', 'registered', 'docs_uploaded', 'quoted', 'paid', 'filed', 'completed'
     referral_link VARCHAR(500),
     created_at TIMESTAMP,
     completed_at TIMESTAMP,
     reward_amount INT,  -- in paise
     reward_claimed BOOLEAN
   );

   CREATE TABLE referral_status_history (
     id UUID PRIMARY KEY,
     referral_id UUID REFERENCES referrals(id),
     old_status VARCHAR(50),
     new_status VARCHAR(50),
     changed_at TIMESTAMP,
     reason VARCHAR(255)
   );

   CREATE TABLE referral_milestones (
     id UUID PRIMARY KEY,
     referrer_id UUID REFERENCES users(id),
     milestone_level INT,  -- 1, 3, 5, 10
     completed_at TIMESTAMP,
     reward_amount INT,
     claimed BOOLEAN
   );
   ```

2. **Referral Status Flow**
   ```
   INVITED
     ↓
   REGISTERED (user clicks referral link and signs up)
     ↓
   DOCS_UPLOADED (user uploads documents)
     ↓
   QUOTED (quote generated)
     ↓
   PAID (payment completed)
     ↓
   FILED (ITR submitted)
     ↓
   COMPLETED (filing accepted by government)
   ```

3. **Referral Service**
   ```python
   def update_referral_status(referral_id: str, new_status: str) -> None:
       # Update status
       # Add to status history
       # Check if milestone achieved
       # Trigger notification to referrer
       # Update wallet if completed

   def check_milestones(referrer_id: str) -> list:
       # Get count of completed referrals
       # Check against milestones (1, 3, 5, 10)
       # Return list of achieved milestones

   def track_referral_event(referral_id: str, event: str):
       # Map events to status changes:
       # 'REGISTERED' -> 'registered'
       # 'DOCS_UPLOADED' -> 'docs_uploaded'
       # 'QUOTE_GENERATED' -> 'quoted'
       # 'PAYMENT_CONFIRMED' -> 'paid'
       # 'FILING_SUBMITTED' -> 'filed'
   ```

4. **Integration Points**
   - Update referral status on user registration
   - Update when documents uploaded
   - Update when quote generated
   - Update when payment confirmed
   - Update when filing submitted

---

### Module 2.3: Fraud Detection & Prevention (Week 6)
**Priority:** 🟠 HIGH  
**Effort:** Medium (80-100 hours)  
**Files to Create:**
- `backend/services/fraud_detection_service.py`
- `backend/models/device_fingerprint.py`
- `backend/models/suspicious_activity.py`

**Implementation:**

1. **Database Schema**
   ```sql
   CREATE TABLE device_fingerprints (
     id UUID PRIMARY KEY,
     user_id UUID REFERENCES users(id),
     device_hash VARCHAR(255),  -- SHA256 of user_agent + ip
     ip_address VARCHAR(50),
     user_agent TEXT,
     last_seen TIMESTAMP,
     created_at TIMESTAMP
   );

   CREATE TABLE suspicious_activities (
     id UUID PRIMARY KEY,
     user_id UUID REFERENCES users(id),
     activity_type VARCHAR(50),  -- 'duplicate_account', 'referral_self', 'unusual_pattern'
     severity VARCHAR(20),  -- 'low', 'medium', 'high', 'critical'
     description TEXT,
     action_taken VARCHAR(50),  -- 'flagged', 'blocked', 'reviewed'
     created_at TIMESTAMP
   );
   ```

2. **Fraud Checks**
   ```python
   def check_duplicate_account(phone: str, email: str) -> dict:
       # Check if phone already exists
       # Check if email already exists
       # Flag if multiple accounts from same device
       # Return: {'is_duplicate': bool, 'severity': 'low'|'high'}

   def check_self_referral(referrer_user_id: str, referral_phone: str) -> bool:
       # Check if referral phone matches referrer's phone
       # Check if same device (device fingerprint)
       # Return: is_self_referral

   def check_unusual_pattern(user_id: str) -> dict:
       # Check for rapid referral additions (e.g., 5 in 1 minute)
       # Check for unusual IP/device changes
       # Return: {'unusual': bool, 'reason': str, 'severity': str}

   def get_device_fingerprint(request) -> str:
       # SHA256 of user_agent + ip_address
       data = f"{request.user_agent.string}:{request.remote_addr}"
       return hashlib.sha256(data.encode()).hexdigest()
   ```

3. **Actions on Fraud Detection**
   - Flag account for review
   - Block referral addition
   - Send admin alert
   - Log suspicious activity
   - Request additional verification

---

### Module 2.4: ITR Filing Submission (Week 6-7)
**Priority:** 🔴 CRITICAL  
**Effort:** Very High (150-180 hours)  
**Files to Create:**
- `backend/services/itr_filing_service.py`
- `backend/models/filing.py`
- `backend/models/filing_status.py`
- `backend/integrations/itr_portal_api.py` (if available)

**Implementation:**

1. **Database Schema**
   ```sql
   CREATE TABLE filings (
     id UUID PRIMARY KEY,
     submission_id UUID,
     user_id UUID REFERENCES users(id),
     filing_year INT,  -- 2024, 2025, etc.
     itr_form VARCHAR(20),  -- 'ITR-1', 'ITR-2', 'ITR-3'
     status VARCHAR(50),  -- 'draft', 'ready', 'submitted', 'acknowledged', 'filed', 'completed'
     filing_reference_number VARCHAR(100),  -- Government assigned
     acknowledgment_receipt VARCHAR(500),  -- XML/PDF
     created_at TIMESTAMP,
     submitted_at TIMESTAMP,
     completed_at TIMESTAMP
   );

   CREATE TABLE filing_status_history (
     id UUID PRIMARY KEY,
     filing_id UUID REFERENCES filings(id),
     old_status VARCHAR(50),
     new_status VARCHAR(50),
     changed_at TIMESTAMP,
     notes TEXT
   );
   ```

2. **ITR Generation**
   ```python
   def generate_itr_xml(filing_id: str) -> str:
       # Fetch all filing data from Sheets/DB
       # Generate ITR XML according to government schema
       # Validate XML structure
       # Return XML string
       # Example: ITR-1 for salaried employees

   def validate_itr_xml(xml_string: str) -> dict:
       # Validate against ITR schema
       # Check required fields present
       # Check value ranges
       # Return: {'valid': bool, 'errors': []}

   def generate_filing_reference(user_id: str, filing_year: int) -> str:
       # Generate unique reference number
       # Format: FT-{year}-{user_id_hash}-{random}
       # Store in database
       pass
   ```

3. **Filing Submission (To ITR Portal)**
   ```python
   # Option A: Manual filing (user downloads XML and files manually)
   def generate_filing_package(filing_id: str) -> dict:
       # Generate ITR XML
       # Generate filling instructions PDF
       # Create downloadable ZIP file
       # Return download link

   # Option B: Automated filing (if portal API available)
   def submit_to_itr_portal(filing_id: str) -> dict:
       # Generate ITR XML
       # Call portal API to submit
       # Get acknowledgment
       # Update filing status
       # Trigger notification
       pass
   ```

4. **Filing Status Tracking**
   ```python
   def update_filing_status(filing_id: str, new_status: str, notes: str = '') -> None:
       # Update status
       # Add to status history
       # Trigger notification if major status change
       # Trigger referral status update if user is referred

   def poll_filing_status(filing_id: str) -> str:
       # Check government portal for status
       # Update if changed
       # Return current status
   ```

---

**END OF PHASE 2**

---

## PART C: PHASE 3 — USER EXPERIENCE (Weeks 8-10)

### Module 3.1: Email Notification Service (Week 8)
**Files:** backend/services/email_service.py, backend/models/email_template.py

### Module 3.2: SMS Notification Service (Week 8)
**Files:** backend/services/sms_service.py

### Module 3.3: User Dashboard (Week 9)
**Files:** frontend/dashboard.html, backend/api routes for dashboard data

### Module 3.4: Referral Dashboard (Week 9-10)
**Files:** frontend/referral-dashboard.html, backend/api routes

---

## PART D: PHASE 4 — ADMIN & COMPLIANCE (Weeks 11-14)

### Module 4.1: Admin Dashboard (Week 11-12)
**Files:** frontend/admin/, backend/admin_api.py

### Module 4.2: Database Migration (Week 12-14)
**Migration from Google Sheets to PostgreSQL**

---

## TESTING STRATEGY FOR EACH MODULE

### Unit Tests
- Each service should have comprehensive unit tests
- Test happy path + error cases
- Test edge cases and boundary conditions

### Integration Tests
- Test flow between modules
- Test API endpoints with real/mock external services

### Security Tests
- Test authentication bypasses
- Test rate limiting
- Test SQL injection, XSS, CSRF

### Load Tests
- Test with concurrent users
- Test with large file uploads
- Test payment processing under load

---

## DEPLOYMENT CHECKPOINTS

**Before Phase 1 Completion:**
- [ ] Authentication system tested
- [ ] Rate limiting effective
- [ ] Audit logging working
- [ ] Security headers in place

**Before Phase 2 Completion:**
- [ ] Payment integration tested with test card
- [ ] Referral tracking accurate
- [ ] Fraud detection catching test cases
- [ ] ITR XML generation validated

**Before Phase 3 Completion:**
- [ ] Email delivery working
- [ ] SMS delivery working
- [ ] Dashboard loading correctly
- [ ] All notifications triggered

**Before Phase 4 Completion:**
- [ ] Admin dashboard fully functional
- [ ] Database migration complete
- [ ] All data migrated successfully
- [ ] No data loss

---

## RISK MITIGATION

**Risk:** Phase 1 delays (authentication complex)  
**Mitigation:** Use Firebase Auth as temporary solution, migrate later

**Risk:** Razorpay integration issues  
**Mitigation:** Implement test mode first, use sandbox for testing

**Risk:** ITR Portal API unavailable  
**Mitigation:** Start with manual filing (user downloads XML)

**Risk:** Database migration data loss  
**Mitigation:** Run in parallel with Sheets for 1 week, validate all data

---

## SUCCESS METRICS

By end of Phase 1:
- [ ] Zero security vulnerabilities in OWASP Top 10
- [ ] All endpoints rate limited
- [ ] 100% audit logging coverage

By end of Phase 2:
- [ ] 100% payment success rate (test transactions)
- [ ] Referral tracking accuracy 99.9%
- [ ] Fraud detection catches 95%+ of test cases

By end of Phase 3:
- [ ] 99% email delivery rate
- [ ] 98% SMS delivery rate
- [ ] Dashboard load time < 2 seconds

By end of Phase 4:
- [ ] Admin can manage all platform operations
- [ ] Zero Sheets quota issues
- [ ] 99.99% uptime

---

**Document Owner:** Claude (AI Architect)  
**Last Updated:** May 27, 2026  
**Status:** Ready for implementation
