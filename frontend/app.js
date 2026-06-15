const API = 'https://fairtax-backend.onrender.com/api'; // PRODUCTION: Render backend

let currentStep = 1;
const TOTAL = 7;

// ❗ REPLACED phone with submission_id
let submissionId = localStorage.getItem("submission_id") || "";

// Store refund amounts from backend calculation
let refundAmounts = { A: 0, B: 0, C: 0 };
// Reset submission_id at the start of every new browser session (tab open/close)
if (!sessionStorage.getItem("session_active")) {
  localStorage.removeItem("submission_id");
  submissionId = "";
  sessionStorage.setItem("session_active", "1");
}

const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

// ─── PREMIUM ANIMATION & INTERACTION FUNCTIONS (Global Scope) ──────────
function showReferralTeaser() {
  const teaser = document.getElementById("referralTeaser");
  if (teaser) {
    teaser.style.display = "block";
    setTimeout(() => {
      teaser.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 100);
  }
}

function scrollToForm() {
  const formCard = document.querySelector("form");
  if (formCard) {
    formCard.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function celebrateUnlock(message, emoji) {
  const celebration = document.createElement("div");
  celebration.className = "milestone-celebration";
  celebration.innerHTML = `
    <span class="celebration-emoji">${emoji}</span>
    <h3 style="font-size:20px;margin:12px 0;font-weight:900">${message}</h3>
  `;
  document.body.appendChild(celebration);

  setTimeout(() => {
    celebration.style.opacity = "0";
    celebration.style.transform =
      "translate(-50%, -50%) scale(0.5) rotate(-10deg)";
    celebration.style.transition = "all 0.4s ease";
    setTimeout(() => celebration.remove(), 400);
  }, 2000);
}

function checkReferralsComplete() {
  let count = 0;
  for (let i = 1; i <= 5; i++) {
    const nameField = $(`[name="ref_name_${i}"]`);
    const phoneField = $(`[name="ref_phone_${i}"]`);
    if (nameField && phoneField && nameField.value && phoneField.value) {
      count++;
    }
  }
  return count;
}

function updateReferralTeaser() {
  const refs = checkReferralsComplete();
  const remaining = Math.max(0, 5 - refs);
  const status =
    refs === 5
      ? "✅ Unlocked"
      : remaining === 0
        ? "✅ Unlocked"
        : `${remaining} more`;

  const referralsNeedEl = document.getElementById("referralsNeeded");
  const statusEl = document.getElementById("filingStatus");

  if (referralsNeedEl) referralsNeedEl.textContent = remaining;
  if (statusEl) statusEl.textContent = status;

  // Show celebration if just unlocked
  if (remaining === 0 && refs === 5) {
    celebrateUnlock("🎉 Free Filing Unlocked!", "🎊");
  }

  // Update milestone tracker
  updateMilestoneTracker(refs);
}

function updateMilestoneTracker(refs) {
  for (let i = 1; i <= 5; i++) {
    const circle = $(`#milestone-circle-${i}`);
    const step = $(`#milestone-${i}`);
    if (circle && step) {
      if (i <= refs) {
        circle.classList.remove("locked");
        circle.classList.add("unlocked");
        step.classList.add("unlocked");
      } else {
        circle.classList.add("locked");
        circle.classList.remove("unlocked");
        step.classList.remove("unlocked");
      }
    }
  }
}

function initEnhancedMilestoneTracker() {
  const tracker = document.getElementById("enhancedMilestoneTracker");
  const rewards = document.getElementById("rewardCardsContainer");
  const cta = document.getElementById("conversionCtaSection");

  if (filingType === "free") {
    if (tracker) tracker.style.display = "block";
    if (rewards) rewards.style.display = "block";
    if (cta) cta.style.display = "block";
    updateReferralTeaser();
  }
}

function initScrollAnimations() {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.1 },
  );

  $$(
    ".scroll-fade-in, .scroll-slide-left, .scroll-slide-right, .premium-reward-card, .conversion-cta-section",
  ).forEach((el) => {
    observer.observe(el);
  });
}

function showStep(n) {
  $$(".step").forEach((s) => s.classList.remove("active"));
  $(`.step[data-step="${n}"]`).classList.add("active");
  if (n <= TOTAL) {
    $("#bar").style.width = (n / TOTAL) * 100 + "%";
    $("#stepLabel").textContent = `Step ${n} of ${TOTAL}`;
  } else {
    $("#bar").style.width = "100%";
    $("#stepLabel").textContent = `Submitted`;
  }

  // Navigation visibility rules:
  // - Prev: visible on steps 2..(TOTAL-1) (hide on thank-you step)
  // - Next: visible on steps before the Confirm step (1..TOTAL-2)
  // - Submit: visible on the Confirm step only (TOTAL-1)
  // - On thank-you (TOTAL), hide prev/next/submit
  const isThankYou = n === TOTAL;
  $("#prev").style.display = n > 1 && n < TOTAL ? "block" : "none";
  $("#next").style.display = n >= 1 && n < TOTAL - 1 ? "block" : "none";
  $("#submit").style.display = n === TOTAL - 1 ? "block" : "none";

  if (isThankYou) {
    $("#prev").style.display = "none";
    $("#next").style.display = "none";
    $("#submit").style.display = "none";
  }

  // Update offer/reveal button visibility whenever the visible step changes
  try {
    updateOfferButtons();
  } catch (e) {
    /* ignore */
  }
}

function collectStep(n) {
  const obj = {};
  $(`.step[data-step="${n}"]`)
    .querySelectorAll("input,select,textarea")
    .forEach((el) => {
      if (!el.name) return;

      if (el.type === "checkbox") obj[el.name] = el.checked ? "1" : "";
      else if (el.value !== undefined) obj[el.name] = el.value;
    });

  return obj;
}

function validateStep(n) {
  const inputs = $(`.step[data-step="${n}"]`).querySelectorAll(
    "input[required], select[required]",
  );

  for (const i of inputs) {
    if (i.offsetParent === null) continue;
    if (!i.checkValidity()) {
      i.reportValidity();
      return false;
    }
  }
  // If user picked Free Tax, require referral step complete on step 1
  if (n === 1 && filingType === "free") {
    if (!referralCode && !checkReferralsComplete()) {
      alert("Please complete 5 referrals to continue with Free Tax.");
      return false;
    }
  }
  return true;
}

// ── SAVE PHASE (collect current step data and persist to backend) ──────
function showToast(msg, type = "warn") {
  let toast = document.getElementById("_saveToast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "_saveToast";
    toast.style.cssText = "position:fixed;bottom:24px;left:50%;transform:translateX(-50%);z-index:9999;padding:12px 22px;border-radius:12px;font-size:14px;font-weight:600;box-shadow:0 4px 20px rgba(0,0,0,.25);transition:opacity .4s;pointer-events:none;";
    document.body.appendChild(toast);
  }
  toast.style.background = type === "error" ? "#dc2626" : type === "success" ? "#10B981" : "#f59e0b";
  toast.style.color = "#fff";
  toast.textContent = msg;
  toast.style.opacity = "1";
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { toast.style.opacity = "0"; }, 3500);
}

async function savePhase(extraData) {
  try {
    let stepData = extraData || collectStep(currentStep);

    if (filingType === "regular" && !stepData.filing_category) {
      stepData.filing_category = "regular";
    } else if (filingType === "free" && !stepData.filing_category) {
      stepData.filing_category = "free";
    }

    if (submissionId) {
      stepData.submission_id = submissionId;
    }

    const r = await fetch(`${API}/save-phase`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(stepData),
    });

    const j = await r.json();

    if (!j.success) {
      console.error("[SAVE_PHASE] Server error:", j.error);
      showToast("⚠️ Could not save progress — you can still continue.", "warn");
      return null;
    }

    if (j.submission_id) {
      submissionId = j.submission_id;
      localStorage.setItem("submission_id", submissionId);
      console.log("[SAVE_PHASE] ✅ Saved. submission_id =", submissionId);
    }

    if (j.referral_code) {
      referralCode = j.referral_code;
      localStorage.setItem("referral_code", referralCode);
      const rcEl = document.querySelector('[name="referral_code"]');
      if (rcEl) rcEl.value = referralCode;
    }

    return j;
  } catch (e) {
    // Network error (backend unreachable / Render cold start) — don't block user
    console.warn("[SAVE_PHASE] Network error (will retry on next step):", e.message);
    showToast("⚠️ Server is waking up — your data is safe, please continue.", "warn");
    return null;
  }
}

// Filing type (Regular / Free) and referral flow
// filing.html is for regular tax filing only
let filingType = "regular"; // Pre-set to regular filing on filing.html
let referralCode = localStorage.getItem("referral_code") || "";
let cameraStream = null;
let cameraTargetInput = null;
// ── EXTRACTION LOADER — tips + cancel ────────────────────────────────────────
const TAX_TIPS = [
  "💡 Section 80C lets you save up to ₹1.5L in tax — PPF, ELSS, and EPF contributions all qualify.",
  "💡 HRA exemption applies even if rent is paid to a family member, with a proper rental agreement.",
  "💡 NPS (Section 80CCD(1B)) gives ₹50,000 extra deduction beyond the ₹1.5L 80C limit.",
  "💡 Standard deduction of ₹75,000 under New Regime applies automatically — no proof needed.",
  "💡 Home loan interest up to ₹2 lakh per year is deductible under Section 24(b) in Old Regime.",
  "💡 If your total income is ≤₹12L under New Regime, the 87A rebate wipes your tax liability to zero.",
  "💡 Medical insurance premiums qualify under Section 80D — up to ₹25,000 for self and family.",
  "💡 LTA (Leave Travel Allowance) is tax-free for actual domestic travel — two trips in a 4-year block.",
  "💡 Professional tax paid is deductible from gross salary — typically ₹2,400 per year.",
  "💡 Gratuity up to ₹20 lakh received on retirement is fully exempt under Section 10(10).",
  "💡 Donations to PM-CARES or the National Relief Fund qualify for 100% deduction under Section 80G.",
  "💡 ELSS mutual funds lock in for just 3 years and count toward 80C — shortest lock-in of any 80C option.",
];

let _tipInterval = null;
let _extractController = null;
let _extractionCancelled = false;

function _startProgress(durationSeconds) {
  const fill = document.querySelector(".loader-progress-fill");
  if (!fill) return;
  fill.style.transition = "none";
  fill.style.width = "0%";
  fill.getBoundingClientRect(); // force reflow
  fill.style.transition = `width ${durationSeconds}s linear`;
  setTimeout(() => { fill.style.width = "88%"; }, 50);
}

function _resetProgress() {
  const fill = document.querySelector(".loader-progress-fill");
  if (!fill) return;
  fill.style.transition = "none";
  fill.style.width = "0%";
}

function startExtractionLoader(progressDuration = 90) {
  const loader = document.getElementById("extractionLoader");
  const tipEl = document.getElementById("extractTip");

  if (loader) {
    loader.style.display = "block";
    loader.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  if (tipEl) {
    let idx = 0;
    tipEl.textContent = TAX_TIPS[idx];
    tipEl.classList.remove("tip-fade-out");
    clearInterval(_tipInterval);
    _tipInterval = setInterval(() => {
      tipEl.classList.add("tip-fade-out");
      setTimeout(() => {
        idx = (idx + 1) % TAX_TIPS.length;
        tipEl.textContent = TAX_TIPS[idx];
        tipEl.classList.remove("tip-fade-out");
      }, 500);
    }, 7000);
  }

  _startProgress(progressDuration);
  _extractController = new AbortController();
  return _extractController.signal;
}

function stopExtractionLoader() {
  const loader = document.getElementById("extractionLoader");
  if (loader) loader.style.display = "none";
  clearInterval(_tipInterval);
  _tipInterval = null;
  _resetProgress();
}

async function cancelExtraction() {
  _extractionCancelled = true;
  if (_extractController) {
    _extractController.abort();
    _extractController = null;
  }
  stopExtractionLoader();

  if (currentStep === 2) {
    // Skip extraction entirely — jump straight to Step 4 (manual entry)
    currentStep = 4;
    showStep(currentStep);
  } else if (currentStep === 3) {
    // Cancel any in-flight background extractions, go straight to Step 4 (manual entry)
    Object.values(_step3Controllers).forEach((c) => { try { c.abort(); } catch (e) {} });
    serializeAllInvestmentProofs();
    currentStep = 4;
    showStep(currentStep);
  } else {
    // Submit loader cancelled — just restore the form
    const statusEl = document.getElementById("extractStatus") || document.querySelector(".status.loading");
    if (statusEl) {
      statusEl.style.display = "block";
      statusEl.className = "status";
      statusEl.textContent = "Fill in the fields below.";
    }
    $("#submit").disabled = false;
  }
}

async function uploadDocs(inputId, docType) {
  const input = $(`#${inputId}`);
  if (!input || !input.files.length) return;

  const fd = new FormData();

  [...input.files].forEach((f) => fd.append("file", f));
  fd.append("doc_type", docType);
  fd.append("submission_id", submissionId);

  const status = $("#extractStatus");
  const signal = startExtractionLoader();

  try {
    // Use /api/itr/extract for ITR-specific extraction
    const r = await fetch(`${API}/itr/extract`, { method: "POST", body: fd, signal });
    const j = await r.json();

    if (j.success && j.data) {
      // Auto-fill extracted fields into Step 4 review form
      const extracted = j.data;

      // Personal info — only auto-fill when the corresponding input is empty
      if (extracted.personal) {
        const p = extracted.personal || {};
        // Fill pan/phone/email only if field is empty
        ["pan", "phone", "email"].forEach((k) => {
          const el = document.querySelector(`[name="${k}"]`);
          try {
            if (!el) return;
            const cur = (el.value || "").toString().trim();
            if ((!cur || cur.length === 0) && p[k]) el.value = p[k];
          } catch (e) {
            /* ignore */
          }
        });

        // Fill name only when user hasn't already entered their name
        try {
          const nameEl = document.querySelector('[name="name"]');
          const curName =
            (nameEl && (nameEl.value || "").toString().trim()) || "";
          if (nameEl && !curName && p.name) nameEl.value = p.name;
        } catch (e) {
          /* ignore */
        }
      }

      // Income info — fill all salary fields
      // Use inc[k] first (nested income object), fall back to extracted[k] (top-level)
      // This handles cases where AI returns 0 in the nested mapping but correct value at top level.
      if (extracted.income) {
        const inc = extracted.income;
        [
          "gross_salary", "basic_salary", "hra_received", "tds_paid",
          "pf_employee", "pf_employer", "professional_tax",
          "lta", "special_allowance", "car_lease_allowance",
          "uniform_allowance", "gratuity", "leave_encashment"
        ].forEach((k) => {
          const el = document.querySelector(`[name="${k}"]`);
          if (!el) return;
          // Prefer nested inc[k], fall back to top-level extracted[k]
          const val = inc[k] || extracted[k];
          if (val) el.value = val;
          console.log(`[FILL] ${k}: inc=${inc[k]}, top=${extracted[k]}, used=${val}`);
        });
      }

      // Deductions
      if (extracted.deductions) {
        const ded = extracted.deductions;
        ["home_loan_interest", "nps_self", "home_loan_principal", "nps_employer",
         "school_fees", "nps_pran"].forEach((k) => {
          const el = document.querySelector(`[name="${k}"]`);
          if (!el) return;
          const val = ded[k] || extracted[k];
          if (val) el.value = val;
        });
      }

      // ✅ AUTO-SAVE extracted data to Google Sheets immediately
      try {
        const inc = extracted.income || {};
        const ded = extracted.deductions || {};
        // Use nested inc/ded fields with top-level extracted fallback (same logic as form filling)
        const flatData = {
          gross_salary: inc.gross_salary || extracted.gross_salary || 0,
          basic_salary: inc.basic_salary || extracted.basic_salary || 0,
          hra_received: inc.hra_received || extracted.hra_received || 0,
          tds_paid: inc.tds_paid || extracted.tds_paid || 0,
          pf_employee: inc.pf_employee || extracted.pf_employee || 0,
          pf_employer: inc.pf_employer || extracted.pf_employer || 0,
          professional_tax: inc.professional_tax || extracted.professional_tax || 0,
          lta: inc.lta || extracted.lta || 0,
          special_allowance: inc.special_allowance || extracted.special_allowance || 0,
          home_loan_interest: ded.home_loan_interest || extracted.home_loan_interest || 0,
          nps_self: ded.nps_self || extracted.nps_self || 0,
          pan: extracted.personal?.pan || extracted.pan || "",
        };
        await savePhase(flatData);
        console.log(
          "[EXTRACTION] ✅ Extracted data auto-saved to Google Sheets",
        );
      } catch (e) {
        console.warn(
          "[EXTRACTION] ⚠️ Auto-save failed (will save when user clicks Next):",
          e,
        );
      }

      if (status) {
        status.className = "status success";
        _lastExtraction[inputId] = { data: j.data, docType };
        status.innerHTML = `✅ Extracted & Saved! Review on next step. ${_dvVerifyBtn(inputId)}`;
      }
    } else if (status) {
      status.className = "status error";
      status.textContent = "⚠️ Could not extract — fill manually.";
    }
  } catch (e) {
    if (e.name === "AbortError") return;
    if (status) {
      status.className = "status error";
      status.textContent = "❌ " + e.message;
    }
  } finally {
    stopExtractionLoader();
  }
}

// (filingType variables declared above)

function setFilingType(type) {
  filingType = type;
  const hidden = document.querySelector("[name='filing_type']");
  if (hidden) hidden.value = type;
  if (type === "free") {
    document.getElementById("freeReferralSection").style.display = "block";
    document.getElementById("regularForm").style.display = "none";
    const btn = document.getElementById("revealCodeBtn");
    if (btn) btn.disabled = false;
    showReferralTeaser();
    initEnhancedMilestoneTracker();
    initScrollAnimations();
    initReferrerAutoSave();  // Auto-save referrer details as user enters them
    initReferralFieldAutoSave();  // Auto-save each referral as user enters them
  } else {
    document.getElementById("freeReferralSection").style.display = "none";
    const rf = document.getElementById("regularForm");
    rf.style.display = "block";
    // Ensure contact inputs are visible and focused for the user
    try {
      const first =
        rf.querySelector('input[name="name"]') ||
        rf.querySelector('input[name="phone"]') ||
        rf.querySelector('input[name="email"]');
      if (first) {
        first.focus();
        first.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    } catch (e) {
      // ignore
    }
  }

  // Update offer-related buttons when filing type changes
  try {
    updateOfferButtons();
  } catch (e) {
    /* ignore */
  }
}

// ── AUTO-SAVE REFERRER DETAILS (Free Filing) ──────────────────────────────────
let _autoSaveTimer = null;
let _lastSavedReferrerData = null;

async function autoSaveReferrerDetails() {
  /**
   * Auto-save referrer details (name, phone, email, PAN, city) as user enters them.
   * This ensures data is saved BEFORE "Reveal Code" click, so code generation works reliably.
   */

  // Only for free filing
  if (filingType !== "free") return;

  // Collect current referrer details
  const refName = document.querySelector('[name="referrer_name"]')?.value?.trim() || "";
  const refPhoneRaw = document.querySelector('[name="referrer_phone"]')?.value?.trim() || "";
  const refEmail = document.querySelector('[name="email"]')?.value?.trim() || "";
  const refPan = document.querySelector('[name="pan"]')?.value?.trim() || "";
  const cityType = document.querySelector('[name="city_type"]')?.value || "";

  const refPhone = _normalizePhone(refPhoneRaw);

  // Check if data has changed since last save
  const currentData = JSON.stringify({refName, refPhone, refEmail, refPan, cityType});
  if (_lastSavedReferrerData === currentData) {
    return; // No change, skip save
  }

  // Validate minimum fields before saving
  if (!refName || !refPhone || !refEmail || !refPan || !cityType) {
    console.log("[AUTO_SAVE] Skipping - incomplete referrer details");
    return;
  }

  // Validate email format
  const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRe.test(refEmail)) {
    console.log("[AUTO_SAVE] Skipping - invalid email");
    return;
  }

  // Validate phone is 10 digits
  if (refPhone.length !== 10) {
    console.log("[AUTO_SAVE] Skipping - phone not 10 digits");
    return;
  }

  try {
    console.log("[AUTO_SAVE] Saving referrer details:", {refName, refPhone, refEmail, refPan, cityType});

    // Save to Google Sheets
    await savePhase({
      filing_category: "free",
      name: refName,
      phone: refPhone,
      email: refEmail,
      pan: refPan,
      city_type: cityType,
    });

    _lastSavedReferrerData = currentData;
    console.log("[AUTO_SAVE] ✅ Referrer details saved successfully");

    // Show brief success indicator
    showToast("✅ Your details saved", "success");

  } catch (e) {
    console.warn("[AUTO_SAVE] Failed to save (non-blocking):", e.message);
    // Non-blocking: allow user to continue even if save fails
  }
}

// Attach auto-save listeners to referrer detail fields
function initReferrerAutoSave() {
  const fields = [
    'referrer_name',
    'referrer_phone',
    'email',
    'pan',
    'city_type'
  ];

  fields.forEach(fieldName => {
    const field = document.querySelector(`[name="${fieldName}"]`);
    if (!field) return;

    // Trigger auto-save on blur (after user leaves field)
    field.addEventListener('blur', () => {
      // Debounce: cancel pending save, schedule new one
      clearTimeout(_autoSaveTimer);
      _autoSaveTimer = setTimeout(autoSaveReferrerDetails, 500);
    });

    // Also trigger on Enter key
    if (field.tagName === 'INPUT') {
      field.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
          clearTimeout(_autoSaveTimer);
          autoSaveReferrerDetails();
        }
      });
    }
  });

  console.log("[AUTO_SAVE] Initialized for referrer details");
}

// ── AUTO-SAVE REFERRAL (Free Filing) ────────────────────────────────────────
let _referralAutoSaveTimers = {}; // Debounce timer per referral index
let _lastSavedReferralData = {}; // Track last saved referral data per index

async function autoSaveReferral(index) {
  /**
   * Auto-save individual referral (name + phone) as user enters them.
   * Saves to "The 5" sheet immediately so data is never lost.
   */

  // Only for free filing
  if (filingType !== "free") return;

  // Get referrer name and phone (from auto-saved referrer details or form)
  const referrerName = document.querySelector('[name="referrer_name"]')?.value?.trim() || "";
  const referrerPhoneRaw = document.querySelector('[name="referrer_phone"]')?.value?.trim() || "";
  const referrerPhone = _normalizePhone(referrerPhoneRaw);

  // Get referral name and phone
  const refName = document.querySelector(`[name="ref_name_${index}"]`)?.value?.trim() || "";
  const refPhoneRaw = document.querySelector(`[name="ref_phone_${index}"]`)?.value?.trim() || "";
  const refPhone = _normalizePhone(refPhoneRaw);

  // Check if data has changed since last save
  const currentData = JSON.stringify({refName, refPhone});
  if (_lastSavedReferralData[index] === currentData) {
    return; // No change, skip save
  }

  // Validate both name and phone are filled
  if (!refName || !refPhone) {
    console.log(`[AUTO_SAVE_REF${index}] Skipping - incomplete referral`);
    return;
  }

  // Validate phone is 10 digits
  if (refPhone.length !== 10) {
    console.log(`[AUTO_SAVE_REF${index}] Skipping - phone not 10 digits`);
    return;
  }

  try {
    console.log(`[AUTO_SAVE_REF${index}] Saving referral: {refName: "${refName}", refPhone: "${refPhone}"}`);

    // Save to backend (which will save to "The 5" sheet)
    const res = await fetch(`${API}/save-referral`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        referrer_name: referrerName,
        referrer_phone: referrerPhone,
        referral_name: refName,
        referral_phone: refPhone,
        referral_index: index
      })
    });

    const j = await res.json();
    if (j.success) {
      _lastSavedReferralData[index] = currentData;
      console.log(`[AUTO_SAVE_REF${index}] ✅ Referral saved successfully`);
      showToast(`✅ Referral ${index} saved`, "success");
    } else {
      console.warn(`[AUTO_SAVE_REF${index}] Server error: ${j.error}`);
    }
  } catch (e) {
    console.warn(`[AUTO_SAVE_REF${index}] Failed to save (non-blocking):`, e.message);
    // Non-blocking: allow user to continue even if save fails
  }
}

// Attach auto-save listeners to referral fields
function initReferralFieldAutoSave() {
  for (let i = 1; i <= 5; i++) {
    const nameField = document.querySelector(`[name="ref_name_${i}"]`);
    const phoneField = document.querySelector(`[name="ref_phone_${i}"]`);

    if (!nameField || !phoneField) continue;

    // Trigger auto-save on blur for name field
    nameField.addEventListener('blur', () => {
      clearTimeout(_referralAutoSaveTimers[i]);
      _referralAutoSaveTimers[i] = setTimeout(() => autoSaveReferral(i), 500);
    });

    // Trigger auto-save on blur for phone field
    phoneField.addEventListener('blur', () => {
      clearTimeout(_referralAutoSaveTimers[i]);
      _referralAutoSaveTimers[i] = setTimeout(() => autoSaveReferral(i), 500);
    });

    // Also trigger on Enter key
    nameField.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        clearTimeout(_referralAutoSaveTimers[i]);
        autoSaveReferral(i);
      }
    });

    phoneField.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        clearTimeout(_referralAutoSaveTimers[i]);
        autoSaveReferral(i);
      }
    });
  }

  console.log("[AUTO_SAVE] Initialized for referral fields");
}

// Control visibility of promotional buttons (reveal/joker) based on filing type and step
function updateOfferButtons() {
  const confirmBtn = document.getElementById("jokerBtnConfirm");
  if (confirmBtn) {
    // Only show the Confirm-step 'Reveal Offer' when user explicitly chose Free Tax
    // and they are on the Confirm & Submit step (data-step="6"). Hide otherwise.
    try {
      confirmBtn.style.display =
        filingType === "free" && currentStep === 6 ? "" : "none";
    } catch (e) {
      confirmBtn.style.display = "none";
    }
  }

  // The free referral 'Reveal Code' button should only be visible for Free filings
  const revealBtn = document.getElementById("revealCodeBtn");
  if (revealBtn) revealBtn.style.display = filingType === "free" ? "" : "none";

  // Joker play button: always visible as a gamified tease; enable only when eligible
  const jokerBtn = document.getElementById("jokerPlayBtn");
  if (jokerBtn) {
    try {
      jokerBtn.style.display = "inline-flex";
      if (filingType === "free" && countCompleteReferrals() >= 5)
        jokerBtn.classList.remove("locked");
      else jokerBtn.classList.add("locked");
    } catch (e) {
      jokerBtn.style.display = "inline-flex";
      jokerBtn.disabled = true;
    }
  }
}

// wiring choice-type buttons
$$(".choice-type").forEach((b) =>
  b.addEventListener("click", () => {
    setFilingType(b.dataset.type);
    $$(".choice-type").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");

    // Safety: if user switches to Regular and contact fields are not filled,
    // clear any existing `submission_id` to avoid accidental creation/usage.
    if (b.dataset.type === "regular") {
      try {
        const nameEl = document.querySelector('[name="name"]');
        const phoneEl = document.querySelector('[name="phone"]');
        const emailEl = document.querySelector('[name="email"]');
        const hasName =
          nameEl && nameEl.value && nameEl.value.toString().trim().length > 0;
        const hasPhone =
          phoneEl &&
          (phoneEl.value || "").toString().replace(/\D/g, "").length >= 10;
        const hasEmail =
          emailEl && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailEl.value);
        if (!hasName || !hasPhone || !hasEmail) {
          submissionId = "";
          try {
            localStorage.removeItem("submission_id");
          } catch (e) {}
        }
      } catch (e) {
        // noop
      }
    }
  }),
);

function _normalizePhone(raw) {
  const s = (raw || "").toString();
  const digits = (s.match(/\d/g) || []).join("");
  return digits.length >= 10 ? digits.slice(-10) : digits;
}

function _isValidPhone(raw) {
  const p = _normalizePhone(raw);
  return /^\d{10}$/.test(p) && !/^0+$/.test(p);
}

function checkReferralsComplete() {
  for (let i = 1; i <= 5; i++) {
    const n =
      document.querySelector(`[name="ref_name_${i}"]`)?.value?.trim() || "";
    const pRaw =
      document.querySelector(`[name="ref_phone_${i}"]`)?.value?.trim() || "";
    if (!n || !_isValidPhone(pRaw)) return false;
  }
  return true;
}

function getReferrals() {
  const arr = [];
  for (let i = 1; i <= 5; i++) {
    const name =
      document.querySelector(`[name="ref_name_${i}"]`)?.value?.trim() || "";
    const phoneRaw =
      document.querySelector(`[name="ref_phone_${i}"]`)?.value?.trim() || "";
    const phone = _normalizePhone(phoneRaw);
    arr.push({ name, phone });
  }
  return arr;
}

// Unified reveal/generate referral code flow
async function revealReferralCode() {
  // Step 1: Validate referrer details for FREE tax
  const refName =
    document.querySelector('[name="referrer_name"]')?.value?.trim() || "";
  const refPhoneRaw =
    document.querySelector('[name="referrer_phone"]')?.value?.trim() || "";
  const refEmail =
    document.querySelector('[name="email"]')?.value?.trim() || "";
  const refPan = document.querySelector('[name="pan"]')?.value?.trim() || "";
  const cityType = document.querySelector('[name="city_type"]')?.value || "";

  const refPhone = _normalizePhone(refPhoneRaw);

  if (
    !refName ||
    !_isValidPhone(refPhone) ||
    !refEmail ||
    !refPan ||
    !cityType
  ) {
    alert(
      "Please fill all your details: Name, Phone (10 digits), Email, PAN, and City Type",
    );
    return;
  }

  // Step 2: Validate referrals
  if (!checkReferralsComplete()) {
    try {
      showPlayFairModal();
    } catch (e) {
      $("#freeMessage").textContent =
        "Please fill all 5 referrals with valid 10-digit phones.";
    }
    return;
  }

  // Step 3: If a code already exists, just show the modal
  const existing = localStorage.getItem("referral_code") || referralCode;
  if (existing) {
    referralCode = existing;
    showJokerModal();
    return;
  }

  // Step 4: Create submission if it doesn't exist (for FREE tax filing)
  if (!submissionId) {
    try {
      const result = await savePhase({
        filing_category: "free",
        name: refName,
        phone: refPhone,
        email: refEmail,
        pan: refPan,
        city_type: cityType,
      });
      if (result.submission_id) {
        submissionId = result.submission_id;
        localStorage.setItem("submission_id", submissionId);
      }
    } catch (e) {
      console.warn("Failed to create submission (non-blocking):", e);
    }
  }

  // Step 5: Generate referral code
  const namePart = refName.toLowerCase();
  const randomNumbers = Math.floor(Math.random() * 100).toString().padStart(2, '0');
  const code = namePart + "_FAIRTAX" + randomNumbers;

  referralCode = code;
  localStorage.setItem("referral_code", code);
  const rcEl = document.querySelector('[name="referral_code"]');
  if (rcEl) rcEl.value = code;
  $("#freeMessage").textContent =
    `Get your code at the end — share with your referrals.`;

  // Step 6: Save referral code and referrals to server
  try {
    await savePhase({
      submission_id: submissionId,
      referral_code: code,
      referrer_name: refName,
      referrals: JSON.stringify(getReferrals()),
    });
    console.log("[REFERRAL] Code saved to backend:", code);
  } catch (e) {
    console.warn("savePhase failed for referral code:", e);
  }

  // Step 7: Notify referrals via WhatsApp
  try {
    await fetch(`${API}/notify-referrals`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        submission_id: submissionId,
        referrer_name: refName,
        referral_code: code,
        referrals: getReferrals(),
      }),
    });
  } catch (e) {
    console.warn("notify-referrals failed:", e);
  }
}

// Joker button click - same as reveal code but with celebration
document.getElementById("jokerPlayBtn")?.addEventListener("click", async () => {
  if (!checkReferralsComplete()) {
    showPlayFairModal();
    return;
  }
  // Trigger the same reveal flow
  await revealReferralCode();
});

// ── JOKER MODAL ──────────────────────────────────────────────────────────
function showJokerModal() {
  const modal = document.getElementById("jokerModal");
  const code = (referralCode || localStorage.getItem("referral_code") || "—")
    .toString()
    .toUpperCase();
  const spaced = code === "—" ? code : code.split("").join(" ");
  // restore celebratory content
  const titleEl = modal.querySelector(".joker-title");
  if (titleEl) titleEl.textContent = "CONGRATULATIONS!";
  const msgEl = modal.querySelector(".joker-msg");
  if (msgEl)
    msgEl.innerHTML =
      "You are the <b>6th Person</b> — your fees is <b>absolutely FREE!</b>";
  const codeEl = document.getElementById("jokerRevealCode");
  if (codeEl) {
    codeEl.style.display = "";
    codeEl.textContent = spaced;
  }
  const closeBtn = modal.querySelector(".joker-close-btn");
  if (closeBtn) closeBtn.textContent = "Claim My Free Filing";
  const rc = document.getElementById("refCode");
  if (rc) rc.textContent = code;
  modal.style.display = "flex";
}

function showPlayFairModal() {
  const modal = document.getElementById("jokerModal");
  const titleEl = modal.querySelector(".joker-title");
  if (titleEl) titleEl.textContent = "Let's Play Fair!";
  const msgEl = modal.querySelector(".joker-msg");
  if (msgEl)
    msgEl.innerHTML =
      '<span class="joker-tease">🃏 <b>Let\'s Play Fair!</b> Fill all 5 referrals and click again for your surprise... 🎭</span>';
  const codeEl = document.getElementById("jokerRevealCode");
  if (codeEl) codeEl.style.display = "none";
  const closeBtn = modal.querySelector(".joker-close-btn");
  if (closeBtn) closeBtn.textContent = "Okay";
  modal.style.display = "flex";
}

// keep the confirm button for the final step
document
  .getElementById("jokerBtnConfirm")
  ?.addEventListener("click", showJokerModal);

// Camera capture helpers
async function openCameraFor(inputId) {
  cameraTargetInput = document.getElementById(inputId);
  const modal = document.getElementById("cameraModal");
  modal.style.display = "flex";
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "environment" },
      audio: false,
    });
    const v = document.getElementById("cameraVideo");
    v.srcObject = cameraStream;
    await v.play();
  } catch (e) {
    alert("Camera not available: " + e.message);
    modal.style.display = "none";
  }
}

function closeCamera() {
  const modal = document.getElementById("cameraModal");
  modal.style.display = "none";
  if (cameraStream) {
    cameraStream.getTracks().forEach((t) => t.stop());
    cameraStream = null;
  }
}

document.getElementById("captureBtn")?.addEventListener("click", async () => {
  const v = document.getElementById("cameraVideo");
  const c = document.getElementById("cameraCanvas");
  c.width = v.videoWidth;
  c.height = v.videoHeight;
  const ctx = c.getContext("2d");
  ctx.drawImage(v, 0, 0, c.width, c.height);
  c.toBlob(
    (blob) => {
      const f = new File([blob], `capture_${Date.now()}.jpg`, {
        type: "image/jpeg",
      });
      const dt = new DataTransfer();
      // keep existing files
      try {
        for (const f2 of cameraTargetInput.files) dt.items.add(f2);
      } catch (e) {}
      dt.items.add(f);
      cameraTargetInput.files = dt.files;
    },
    "image/jpeg",
    0.9,
  );
  closeCamera();
});

document.getElementById("closeCamera")?.addEventListener("click", closeCamera);

// attach camera btns
$$(".camera-btn").forEach((b) =>
  b.addEventListener("click", (e) => {
    const target = b.dataset.target;
    if (target) openCameraFor(target);
  }),
);

// ══════════════════════════════════════════════════════════════════════════
// DOCUMENT VERIFY MODAL
// ══════════════════════════════════════════════════════════════════════════

// Stores last extraction result per inputId
const _lastExtraction = {};

// Field definitions shown in the verify panel per doc type
const DV_FIELDS = {
  form16:   [{ k:"gross_salary",l:"Gross Salary" },{ k:"basic_salary",l:"Basic Salary" },{ k:"hra_received",l:"HRA Received" },{ k:"tds_paid",l:"TDS Paid" },{ k:"pf_employee",l:"PF (Employee)" },{ k:"professional_tax",l:"Professional Tax" },{ k:"pan",l:"PAN" }],
  payslip:  [{ k:"gross_salary",l:"Gross Salary" },{ k:"basic_salary",l:"Basic Salary" },{ k:"hra_received",l:"HRA Received" },{ k:"tds_paid",l:"TDS Paid" },{ k:"pf_employee",l:"PF (Employee)" },{ k:"pf_employer",l:"PF (Employer)" },{ k:"professional_tax",l:"Professional Tax" },{ k:"lta",l:"LTA" },{ k:"special_allowance",l:"Special Allowance" }],
  homeloan: [{ k:"home_loan_interest",l:"Interest (Annual)" },{ k:"home_loan_principal",l:"Principal (Annual)" },{ k:"bank_name",l:"Bank / Lender" },{ k:"loan_account_no",l:"Account No" },{ k:"loan_outstanding",l:"Outstanding Balance" }],
  insurance:[{ k:"premium_paid",l:"Premium Paid" },{ k:"policy_no",l:"Policy No" },{ k:"insurer_name",l:"Insurer" },{ k:"sum_assured",l:"Sum Assured" }],
  nps:      [{ k:"nps_pran",l:"PRAN Number" },{ k:"nps_self",l:"Employee Contribution" },{ k:"nps_employer",l:"Employer Contribution" }],
  school:   [{ k:"school_name",l:"School Name" },{ k:"school_fees",l:"Fees (Annual)" }],
  donation: [{ k:"org_name",l:"Organisation" },{ k:"donation_amount",l:"Amount Donated" }],
};
const DV_MONEY = new Set(["gross_salary","basic_salary","hra_received","tds_paid","pf_employee","pf_employer","professional_tax","lta","special_allowance","home_loan_interest","home_loan_principal","loan_outstanding","premium_paid","sum_assured","nps_self","nps_employer","school_fees","donation_amount"]);

function _dvVerifyBtn(inputId) {
  return `<button class="dv-verify-btn" onclick="openDocVerify('${inputId}')">📄 Verify</button>`;
}

function openDocVerify(inputId) {
  const input = document.getElementById(inputId);
  const ext = _lastExtraction[inputId];
  if (!input || !input.files.length) {
    alert("No file uploaded for this document yet.\nGo back to Step 2 or 3 and upload the file first.");
    return;
  }

  const files = Array.from(input.files);
  const tabsEl = document.getElementById("dvTabs");
  const fieldsEl = document.getElementById("dvFieldsInner");

  // Build file tabs
  window._dvFiles = files;
  window._dvUrls = files.map(f => URL.createObjectURL(f));
  tabsEl.innerHTML = files.map((f,i) =>
    `<button class="dv-tab${i===0?" active":""}" onclick="dvShowFile(${i})" title="${f.name}">${f.name}</button>`
  ).join("");
  dvShowFile(0);

  // Build extracted fields
  const docType = ext?.docType || "";
  const raw = ext?.data || {};
  const flat = { ...raw, ...(raw.income||{}), ...(raw.deductions||{}), ...(raw.personal||{}) };
  const defs = DV_FIELDS[docType] || [];

  if (defs.length) {
    fieldsEl.innerHTML = defs.map(({ k, l }) => {
      const v = flat[k];
      if (v === undefined || v === null || v === "" || v === 0) return "";
      const isMoney = DV_MONEY.has(k);
      const display = isMoney ? "₹" + Number(v).toLocaleString("en-IN") : v;
      return `<div class="dv-field">
        <div class="dv-field-label">${l}</div>
        <div class="dv-field-value${isMoney?" dv-money":""}">${display}</div>
      </div>`;
    }).join("") || '<div class="dv-no-data">No extracted values to display.</div>';
  } else {
    fieldsEl.innerHTML = '<div class="dv-no-data">Upload a file and extract to see values here.</div>';
  }

  document.getElementById("docVerifyModal").style.display = "flex";
  document.body.style.overflow = "hidden";
}

function dvShowFile(idx) {
  const frameEl = document.getElementById("dvFrame");
  const file = window._dvFiles[idx];
  const url = window._dvUrls[idx];
  document.querySelectorAll(".dv-tab").forEach((t,i) => t.classList.toggle("active", i===idx));
  const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
  frameEl.innerHTML = isPdf
    ? `<iframe src="${url}"></iframe>`
    : `<img src="${url}" alt="${file.name}">`;
}

function closeDocVerify() {
  document.getElementById("docVerifyModal").style.display = "none";
  document.body.style.overflow = "";
}

// ── File preview buttons ──────────────────────────────────────────────────
// Automatically adds a "👁 Preview" button next to every file input.
// Button is hidden until a file is selected, then opens it in a new tab.
document.querySelectorAll('input[type="file"]').forEach((input) => {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "preview-btn";
  btn.innerHTML = "👁&nbsp; Preview File";
  btn.style.display = "none";
  btn.addEventListener("click", () => {
    const files = Array.from(input.files || []);
    if (!files.length) return;
    files.forEach((f) => window.open(URL.createObjectURL(f), "_blank"));
  });
  input.parentElement.insertBefore(btn, input.nextSibling);
  input.addEventListener("change", () => {
    btn.style.display = input.files && input.files.length ? "inline-block" : "none";
  });
});

// fetch winners for widget
async function loadWinners() {
  try {
    const r = await fetch(`${API}/winners`);
    const j = await r.json();
    const list = document.getElementById("winnersList");
    list.innerHTML = "";
    (j.winners || []).forEach((w) => {
      const li = document.createElement("li");
      li.textContent = `${w.name} — ${w.reward}`;
      list.appendChild(li);
    });
  } catch (e) {
    console.warn("winners load failed", e);
  }
}
loadWinners();

// Form16 toggle
$$(".choice").forEach((btn) => {
  btn.onclick = () => {
    $$(".choice").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");

    const val = btn.dataset.form16;

    document.querySelector("[name='has_form16']").value = val;

    $("#form16Section").style.display = val === "yes" ? "block" : "none";
    $("#payslipSection").style.display = "block";
  };
});

$("#next").onclick = async () => {
  const nextBtn = $("#next");
  if (nextBtn.disabled) return; // block re-entry while processing
  nextBtn.disabled = true;
  const _origNextText = nextBtn.textContent;
  nextBtn.textContent = "Please wait…";

  try {

  // Prevent progressing from step 1 unless filing type is explicitly chosen
  if (currentStep === 1 && !filingType) {
    alert("Please select Regular Tax or Free Tax to continue.");
    return;
  }

  if (!validateStep(currentStep)) return;

  // STEP 1 → create submission (for REGULAR filing only)
  // FREE filing submission is created in revealReferralCode()
  if (currentStep === 1) {
    try {
      if (filingType === "regular") {
        const s1 = collectStep(1);
        const missing = [];
        if (!s1.name || !s1.name.toString().trim()) missing.push("name");
        const phoneDigits = (s1.phone || "").toString().replace(/\D/g, "");
        if (phoneDigits.length < 10) missing.push("phone");
        const mail = s1.email || "";
        const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!mail || !emailRe.test(mail)) missing.push("email");
        if (missing.length) {
          alert("Please fill required fields: " + missing.join(", "));
          return;
        }

        // Save submission for REGULAR filing — retry once, block on failure
        let s1Result = await savePhase();
        if (!s1Result || !submissionId) {
          await new Promise((res) => setTimeout(res, 1500));
          s1Result = await savePhase();
        }
        if (!s1Result || !submissionId) {
          alert("Could not reach the server. Please wait a moment and try again.");
          return;
        }
      } else if (filingType === "free") {
        // For FREE filing, auto-save Step 1 to generate referral code with correct name
        if (!referralCode && !localStorage.getItem("referral_code")) {
          try {
            const s1 = collectStep(1);
            // Referral flow uses referrer_name/referrer_phone, not name/phone
            const actualName = s1.referrer_name || s1.name;
            const actualPhone = s1.referrer_phone || s1.phone;

            const missing = [];
            if (!actualName || !actualName.toString().trim()) missing.push("name");
            const phoneDigits = (actualPhone || "").toString().replace(/\D/g, "");
            if (phoneDigits.length < 10) missing.push("phone");
            const mail = s1.email || "";
            const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!mail || !emailRe.test(mail)) missing.push("email");
            if (missing.length) {
              alert("Please fill required fields: " + missing.join(", "));
              return;
            }

            // Auto-save Step 1 data for FREE filing
            await savePhase({
              filing_category: "free",
              name: actualName,
              phone: actualPhone,
              email: s1.email,
              pan: s1.pan,
              city_type: s1.city_type,
            });
          } catch (e) {
            console.warn("Step 1 auto-save failed (non-blocking):", e);
          }
        }
        // Submission created via auto-save above
      } else {
        alert("Please select a filing type first.");
        return;
      }
    } catch (e) {
      // savePhase throws on server validation or network errors — do not advance
      console.error("Step 1 submission failed:", e);
      return;
    }
  }

  _extractionCancelled = false;

  // STEP 2 → doc extract
  if (currentStep === 2) {
    await uploadDocs("form16", "form16");
    await uploadDocs("payslips", "payslip");
    if (_extractionCancelled) return; // cancel already advanced the step
  }

  // STEP 3 → wait for any still-running background extractions, then serialize
  if (currentStep === 3) {
    const inFlight = Object.values(_step3Promises).filter(Boolean);
    if (inFlight.length) {
      startExtractionLoader();
      await Promise.allSettled(inFlight);
      stopExtractionLoader();
    }
    if (_extractionCancelled) return; // cancel already advanced the step
    serializeAllInvestmentProofs();
  }

  // Avoid double-saving on step 1 (we already created submission earlier)
  if (currentStep !== 1) {
    await savePhase();
  }

  if (currentStep < TOTAL) {
    currentStep++;
    showStep(currentStep);
  }

  } finally {
    nextBtn.disabled = false;
    nextBtn.textContent = _origNextText;
  }
};

$("#prev").onclick = () => {
  if (currentStep > 1) {
    currentStep--;
    showStep(currentStep);
  }
};

$("#submit").onclick = async () => {
  if (!$("#consent").checked) {
    alert("Please consent to continue.");
    return;
  }

  const all = {
    submission_id: submissionId,
  };

  for (let i = 1; i <= TOTAL; i++) {
    Object.assign(all, collectStep(i));
  }

  $("#submit").disabled = true;

  // Show animated loader with submit-specific messaging
  startExtractionLoader(25);
  const _loaderTitle = document.querySelector(".loader-title");
  const _loaderSub   = document.querySelector(".loader-sub");
  const _cancelBtn   = document.querySelector(".cancel-extract-btn");
  if (_loaderTitle) _loaderTitle.textContent = "Calculating your refund";
  if (_loaderSub)   _loaderSub.textContent   = "Crunching numbers — usually 1–2 minutes";
  if (_cancelBtn)   _cancelBtn.style.display  = "none";

  try {
    const r = await fetch(`${API}/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(all),
    });

    const j = await r.json();

    if (j.success) {
      // Store referral code for wallet and referral pages
      const refCode = j.referral_code || "—";
      localStorage.setItem("referral_code", refCode);

      $("#refCode").textContent = refCode;

      // NOTE: Refund amounts are NOT displayed to users in web UI
      // They are only stored in backend, sheets, and PDF (via WhatsApp)
      // Users see "Congratulations" on submit, then "Quote Approved!" after approval
      // The 6 quote options appear only in PDF, never in web UI

      currentStep = 7;
      showStep(7);

      // ── OPEN WHATSAPP TO FAIRTAX ──────────────────────────────────────────
      // Send notification to FairTax that user just submitted filing
      try {
        const waMessage = "Hey FairTax! 🎉 I just submitted my filing!";
        const fairtaxWANumber = "919600165254"; // FairTax WhatsApp number
        const waUrl = `https://wa.me/${fairtaxWANumber}?text=${encodeURIComponent(waMessage)}`;
        console.log("[SUBMIT] Opening WhatsApp to FairTax");
        window.open(waUrl, '_blank');
      } catch (e) {
        console.warn("[SUBMIT] Failed to open WhatsApp (non-blocking):", e.message);
      }
    } else {
      alert("Error: " + j.error);
    }
  } catch (e) {
    alert("Network error: " + e.message);
  }

  stopExtractionLoader();
  // Restore loader text for future extraction use
  if (_loaderTitle) _loaderTitle.textContent = "AI is reading your documents";
  if (_loaderSub)   _loaderSub.textContent   = "Usually takes 10–20 seconds";
  if (_cancelBtn)   _cancelBtn.style.display  = "";

  $("#submit").disabled = false;
};

// ── REFUND OPTION SELECTION ──────────────────────────────────────────────
function _inr(n) {
  return "₹" + Number(n || 0).toLocaleString("en-IN");
}

// Calculate refund amounts based on actual backend calculation
function calculateRefundAmounts(backendData = {}) {
  // If backend provides actual calculated refunds, use them
  if (backendData && backendData.refund_old_a !== undefined) {
    return {
      A: Math.round(backendData.refund_old_a || 0),
      B: Math.round(backendData.refund_old_b || 0),
      C: Math.round(backendData.refund_old_c || 0),
    };
  }

  // Fallback: Estimate refund (simplified: TDS - tax owed)
  // This is only used if backend data is not available
  const grossSalary = parseFloat(
    document.querySelector('[name="gross_salary"]')?.value || 0,
  );
  const tdsPaid = parseFloat(
    document.querySelector('[name="tds_paid"]')?.value || 0,
  );

  let estimatedRefund = tdsPaid * 0.85; // 85% of TDS as placeholder

  if (estimatedRefund < 5000) estimatedRefund = 5000;
  if (estimatedRefund > 200000) estimatedRefund = 200000;

  return {
    A: Math.round(estimatedRefund),
    B: Math.round(estimatedRefund * 0.98), // 2% fee
    C: Math.round(estimatedRefund * 1.075), // 7.5% interest over 6 months
  };
}

async function selectRefundOption(option) {
  if (!submissionId) {
    alert("Please complete the form first.");
    return;
  }

  try {
    const r = await fetch(`${API}/choose-option`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ submission_id: submissionId, plan_id: option }),
    });

    const j = await r.json();

    if (!j.success) {
      alert(j.error || "Error saving choice.");
      return;
    }

    // Update UI to show selected option
    document.querySelectorAll(".option-card").forEach((card) => {
      card.classList.remove("selected");
    });
    document
      .querySelector(`.option-card[data-option="${option}"]`)
      ?.classList.add("selected");

    // Show payment instructions using stored amounts from submit
    const amount = refundAmounts[option];
    const descriptions = {
      A: "Direct bank transfer within 7-10 working days",
      B: "Expedited processing within 3-5 working days (₹500 fee)",
      C: "Invest for 6 months @ 7.5% and earn interest",
    };

    const upiId = j.payment_upi || "fairtaxadvisors@upi";
    const waMsg = encodeURIComponent(
      `Hi FairTax Team!\n\nI have selected Option ${option} for my refund.\n\nSubmission ID: ${submissionId}\nRefund Amount: ${_inr(amount)}\n\nKindly confirm. Thank you!`,
    );

    document.getElementById("quoteResult").innerHTML = `
      <div class="payment-card">
        <h3>✅ Option ${option} Selected!</h3>
        <p style="color:#166534;font-size:14px;margin-bottom:14px">
          ${descriptions[option]}
        </p>
        <div style="font-size:13px;color:#166534;margin-bottom:6px;font-weight:600">Your Refund Amount</div>
        <div class="payment-upi" style="font-size:28px;margin-bottom:6px">${_inr(amount)}</div>
        <div style="font-size:13px;color:#475569;margin-bottom:4px">Payment Required (50% upfront)</div>
        <div class="payment-upi" style="font-size:24px;margin-bottom:6px;color:#166534">${_inr(amount * 0.5)}</div>
        <div style="font-size:13px;color:#475569;margin-bottom:4px">UPI ID</div>
        <div style="font-size:16px;font-weight:800;color:#166534;margin-bottom:4px" id="upiDisplay">${upiId}</div>
        <button onclick="navigator.clipboard.writeText('${upiId}').then(()=>{document.getElementById('upiDisplay').textContent='Copied! ✓';}).catch(()=>{})"
          style="background:#e2e8f0;border:none;padding:5px 14px;border-radius:8px;cursor:pointer;font-size:12px;margin-bottom:16px">
          📋 Copy UPI ID
        </button>
        <br>
        <a class="payment-wa-btn" href="https://wa.me/917397510254?text=${waMsg}" target="_blank" rel="noopener">
          📱 Send Confirmation on WhatsApp →
        </a>
      </div>
    `;
  } catch (e) {
    alert("Network error: " + e.message);
  }
}

async function chooseOption(planId, fee, upfront) {
  try {
    const r = await fetch(`${API}/choose-option`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ submission_id: submissionId, plan_id: planId }),
    });
    const j = await r.json();
    if (!j.success) {
      alert(j.error || "Error saving choice.");
      return;
    }

    const upiId = j.payment_upi || "fairtaxadvisors@upi";
    const waMsg = encodeURIComponent(
      `Hi FairTax Team!\n\nI have selected Plan ${planId} for my ITR filing.\n\nSubmission ID: ${submissionId}\nAmount to Pay (50% upfront): ${_inr(upfront)}\n\nKindly confirm. Thank you!`,
    );

    document.getElementById("quoteResult").innerHTML = `
      <div class="payment-card">
        <h3>✅ Plan ${planId} Selected!</h3>
        <p style="color:#166534;font-size:14px;margin-bottom:14px">
          Pay 50% upfront to begin filing. Remaining 50% is due <b>only after</b> your refund is credited.
        </p>
        <div style="font-size:13px;color:#166534;margin-bottom:6px;font-weight:600">Amount to Pay Now</div>
        <div class="payment-upi" style="font-size:28px;margin-bottom:6px">${_inr(upfront)}</div>
        <div style="font-size:13px;color:#475569;margin-bottom:4px">UPI ID</div>
        <div style="font-size:16px;font-weight:800;color:#166534;margin-bottom:4px" id="upiDisplay">${upiId}</div>
        <button onclick="navigator.clipboard.writeText('${upiId}').then(()=>{document.getElementById('upiDisplay').textContent='Copied! ✓';}).catch(()=>{})"
          style="background:#e2e8f0;border:none;padding:5px 14px;border-radius:8px;cursor:pointer;font-size:12px;margin-bottom:16px">
          📋 Copy UPI ID
        </button>
        <br>
        <a class="payment-wa-btn" href="https://wa.me/917397510254?text=${waMsg}" target="_blank" rel="noopener">
          📱 Send Payment Screenshot on WhatsApp →
        </a>
        <p style="font-size:11px;color:#64748b;margin-top:14px">
          Send your payment screenshot on WhatsApp to activate filing immediately.
          You can also <a href="status.html?id=${submissionId}" style="color:#2563eb">track your filing status here</a>.
        </p>
      </div>`;
  } catch (e) {
    alert("Network error: " + e.message);
  }
}

$("#checkQuote").onclick = async () => {
  const out = document.getElementById("quoteResult");
  out.innerHTML =
    '<p style="color:#64748b;text-align:center;padding:12px">⏳ Checking your quote status...</p>';

  try {
    const r = await fetch(`${API}/quote/${submissionId}`);
    const j = await r.json();

    if (!j.success) {
      out.innerHTML =
        '<div class="milestone-hint" style="margin:0">Submission not found. Please check your submission ID.</div>';
      return;
    }

    if (!j.approved) {
      out.innerHTML = `<div class="milestone-hint" style="margin:0">⏳ ${j.message || "Your filing is under expert review. You'll get a WhatsApp notification once approved!"}</div>`;
      return;
    }

    // Display quote approved message with password
    const quoteMsg = encodeURIComponent(
      `Hi FairTax Team,\n\nPlease share my quote for submission ID: ${submissionId}\n\nThank you!`,
    );

    out.innerHTML = `
      <div style="background:#eef2ff;border:2px solid #6366f1;border-radius:12px;padding:18px;text-align:center">
        <div style="font-size:18px;font-weight:800;color:#3730a3;margin-bottom:8px">✅ Quote Approved!</div>
        <div style="color:#374151;margin-bottom:10px">Your detailed quote and filing plan options have been sent to your WhatsApp number. <strong>Please check your WhatsApp messages to view and download the secured report.</strong></div>
        ${
          j.pdf_password
            ? `
        <div style="margin-top:12px;padding:12px;background:#fef3c7;border-radius:8px;border:1px solid #fcd34d">
          <div style="font-size:12px;color:#78350f;margin-bottom:6px;font-weight:600">PDF Password:</div>
          <div style="font-size:16px;color:#dc2608;font-weight:800;letter-spacing:2px;font-family:monospace">${j.pdf_password}</div>
        </div>`
            : ""
        }
        <div style="margin-top:12px">
          <a class="payment-wa-btn" href="https://wa.me/917397510254?text=${quoteMsg}" target="_blank" rel="noopener">📱 Contact Support on WhatsApp</a>
        </div>
        <p style="font-size:12px;color:#6b7280;margin-top:12px">You can also track filing progress on the <a href="status.html?id=${submissionId}" style="color:#2563eb">Status page</a>.</p>
      </div>`;
  } catch (e) {
    out.innerHTML = `<p style="color:#dc2626">Error: ${e.message}</p>`;
  }
};

// ── FREE ELIGIBILITY CHECKBOX ────────────────────────────────────────────
document
  .getElementById("freeEligibility")
  ?.addEventListener("change", function () {
    document.getElementById("eligibilityProof").style.display = this.checked
      ? "block"
      : "none";
  });

// ── MILESTONE REFERRAL TRACKER ───────────────────────────────────────────
const MILESTONES = [
  {
    count: 10,
    reward: "₹15,000",
    msg: "🌟 LEGENDARY! 10 referrals — you earn <b>₹15,000</b> cashback!",
    next: "You've unlocked the maximum reward!",
    mega: true,
  },
  {
    count: 5,
    reward: "₹5,000 + FREE Filing",
    msg: "🏆 Outstanding! 5 referrals — <b>FREE filing</b> + <b>₹5,000</b> cashback!",
    next: "Add 5 more to unlock ₹15,000!",
    mega: true,
  },
  {
    count: 3,
    reward: "₹1,000",
    msg: "🎊 Incredible! 3 referrals done — you earn <b>₹1,000</b> cashback!",
    next: "Add 2 more for ₹5,000 + FREE filing!",
  },
  {
    count: 1,
    reward: "₹250",
    msg: "🎉 Amazing! 1 referral done — you earn <b>₹250</b> cashback!",
    next: "Add 2 more for ₹1,000!",
  },
];

function countCompleteReferrals() {
  let count = 0;
  for (let i = 1; i <= 5; i++) {
    const n =
      document.querySelector(`[name="ref_name_${i}"]`)?.value?.trim() || "";
    const pRaw =
      document.querySelector(`[name="ref_phone_${i}"]`)?.value?.trim() || "";
    const p = _normalizePhone(pRaw);
    if (n && p && /^\d{10}$/.test(p)) count++;
  }
  return count;
}

function updateMilestoneTracker() {
  const tracker = document.getElementById("milestoneTracker");
  if (!tracker) return;
  const count = countCompleteReferrals();

  // Keep Joker CTA visible as a tease; enable it only when milestone reached
  const jokerBtn = document.getElementById("jokerPlayBtn");
  if (jokerBtn) {
    jokerBtn.style.display = "inline-flex";
    if (count >= 5) jokerBtn.classList.remove("locked");
    else jokerBtn.classList.add("locked");
  }

  if (count === 0) {
    tracker.innerHTML = `<div class="milestone-hint">🚀 Add your first referral to start earning!<br>
      <small>Refer 1 → ₹250 &nbsp;·&nbsp; Refer 3 → ₹1,000 &nbsp;·&nbsp; Refer 5 → FREE + ₹5,000 &nbsp;·&nbsp; Refer 10 → ₹15,000</small></div>`;
    return;
  }

  const reached = MILESTONES.find((m) => count >= m.count);
  // find next milestone (strictly greater than current count)
  const next = MILESTONES.find((m) => m.count > count);

  if (!reached) return;

  const rewardText = reached.reward || "";
  let nextText = next
    ? `Add ${next.count - count} more for ${next.reward}`
    : "You've unlocked the maximum reward!";

  tracker.innerHTML = `<div class="milestone-badge${reached.mega ? " mega" : ""}">
    🎉 <strong>${count}</strong> referrals done — <span style="font-weight:800">${rewardText}</span>
    <div class="milestone-next">👉 ${nextText}</div>
  </div>`;

  // If user completed 5 referrals and no referral code exists, auto-generate and reveal once
  if (count >= 5 && !localStorage.getItem("referral_code")) {
    if (!sessionStorage.getItem("auto_reveal_triggered")) {
      sessionStorage.setItem("auto_reveal_triggered", "1");
      try {
        revealReferralCode();
      } catch (e) {
        console.warn("auto reveal failed", e);
      }
    }
  }
}

// Attach milestone tracker to all referral inputs via delegation
document
  .getElementById("referralsList")
  ?.addEventListener("input", updateMilestoneTracker);

// Enable/disable "Reveal Code" button based on form completion
function updateRevealCodeButton() {
  const refName =
    document.querySelector('[name="referrer_name"]')?.value?.trim() || "";
  const refPhoneRaw =
    document.querySelector('[name="referrer_phone"]')?.value?.trim() || "";
  const refEmail =
    document.querySelector('[name="email"]')?.value?.trim() || "";
  const refPan = document.querySelector('[name="pan"]')?.value?.trim() || "";
  const cityType = document.querySelector('[name="city_type"]')?.value || "";
  const refPhone = _normalizePhone(refPhoneRaw);

  const referrerComplete =
    refName && _isValidPhone(refPhone) && refEmail && refPan && cityType;
  const referralsComplete = checkReferralsComplete();
  const btnEnabled = referrerComplete && referralsComplete;

  const btn = document.getElementById("revealCodeBtn");
  if (btn) {
    btn.disabled = !btnEnabled;
  }
}

// Attach to all relevant input fields
document
  .querySelector('[name="referrer_name"]')
  ?.addEventListener("input", updateRevealCodeButton);
document
  .querySelector('[name="referrer_phone"]')
  ?.addEventListener("input", updateRevealCodeButton);
document
  .querySelector('[name="email"]')
  ?.addEventListener("input", updateRevealCodeButton);
document
  .querySelector('[name="pan"]')
  ?.addEventListener("input", updateRevealCodeButton);
document
  .querySelector('[name="city_type"]')
  ?.addEventListener("change", updateRevealCodeButton);
document
  .getElementById("referralsList")
  ?.addEventListener("input", updateRevealCodeButton);

// ensure tracker initializes on page load in case fields are pre-filled
window.addEventListener("DOMContentLoaded", () => {
  updateMilestoneTracker();
  updateRevealCodeButton();
});

// ── STRUCTURED PROOF SECTION HELPERS ────────────────────────────────────
function toggleSection(id, val) {
  const el = document.getElementById(id);
  if (el) el.style.display = val === "yes" ? "block" : "none";
}

function addHomeLoan() {
  const list = document.getElementById("homeLoanList");
  const div = document.createElement("div");
  div.className = "entry-row";
  div.innerHTML = `
    <div class="entry-grid">
      <label>Loan Account / Policy No.<input class="hl-f" data-key="policy_no" placeholder="Account number"></label>
      <label>Sanction Date<input class="hl-f" data-key="sanction_date" type="date"></label>
      <label>Disbursed Amount (₹)<input class="hl-f" data-key="disbursed" type="number" placeholder="₹"></label>
      <label>Outstanding Amount (₹)<input class="hl-f" data-key="outstanding" type="number" placeholder="₹"></label>
      <label class="full-col">Bank / NBFC Name<input class="hl-f" data-key="bank_name" placeholder="e.g. SBI, HDFC Bank"></label>
    </div>
    <button type="button" class="remove-btn" onclick="this.closest('.entry-row').remove();serializeHomeLoan()">✕ Remove</button>`;
  list.appendChild(div);
}

function addInsurance(listId, type) {
  const list = document.getElementById(listId);
  const div = document.createElement("div");
  div.className = "entry-row";
  div.innerHTML = `
    <div class="entry-grid">
      <label>Insurance Company<input class="ins-f" data-key="company" data-type="${type}" placeholder="e.g. LIC, HDFC ERGO"></label>
      <label>Policy Number<input class="ins-f" data-key="policy_no" data-type="${type}" placeholder="Policy no."></label>
      <label class="full-col">Annual Premium (₹)<input class="ins-f" data-key="premium" data-type="${type}" type="number" placeholder="₹"></label>
    </div>
    <button type="button" class="remove-btn" onclick="this.closest('.entry-row').remove();serializeInsurance()">✕ Remove</button>`;
  list.appendChild(div);
}

function addDonation() {
  const list = document.getElementById("donationList");
  const div = document.createElement("div");
  div.className = "entry-row";
  div.innerHTML = `
    <div class="entry-grid">
      <label>Donee PAN<input class="don-f" data-key="donee_pan" style="text-transform:uppercase" placeholder="ABCDE1234F" maxlength="10"></label>
      <label>Institution Name<input class="don-f" data-key="institution" placeholder="Name of trust / org"></label>
      <label>Amount (₹)<input class="don-f" data-key="amount" type="number" placeholder="₹"></label>
      <label>Date<input class="don-f" data-key="date" type="date"></label>
    </div>
    <button type="button" class="remove-btn" onclick="this.closest('.entry-row').remove();serializeDonations()">✕ Remove</button>`;
  list.appendChild(div);
}

function serializeHomeLoan() {
  const data = Array.from(
    document.querySelectorAll("#homeLoanList .entry-row"),
  ).map((row) => {
    const obj = {};
    row.querySelectorAll(".hl-f").forEach((f) => {
      obj[f.dataset.key] = f.value;
    });
    return obj;
  });
  const el = document.getElementById("homeLoansJson");
  if (el) el.value = JSON.stringify(data);
}

function serializeInsurance() {
  const typeMap = {
    lifeInsList: "life",
    healthSelfList: "health_self",
    healthParentList: "health_parent",
  };
  const all = [];
  ["lifeInsList", "healthSelfList", "healthParentList"].forEach((listId) => {
    document.querySelectorAll(`#${listId} .entry-row`).forEach((row) => {
      const obj = { type: typeMap[listId] };
      row.querySelectorAll(".ins-f").forEach((f) => {
        obj[f.dataset.key] = f.value;
      });
      all.push(obj);
    });
  });
  const el = document.getElementById("insurancePoliciesJson");
  if (el) el.value = JSON.stringify(all);
}

function serializeDonations() {
  const data = Array.from(
    document.querySelectorAll("#donationList .entry-row"),
  ).map((row) => {
    const obj = {};
    row.querySelectorAll(".don-f").forEach((f) => {
      obj[f.dataset.key] = f.value;
    });
    // auto-sum sec_80g from donation amounts
    return obj;
  });
  const el = document.getElementById("donationsJson");
  if (el) el.value = JSON.stringify(data);
  // Auto-populate total 80G field
  const total = data.reduce((s, d) => s + (parseFloat(d.amount) || 0), 0);
  const g80 = document.querySelector('[name="sec_80g"]');
  if (g80 && !g80.dataset.manualOverride) g80.value = total || "";
}

function serializeAllInvestmentProofs() {
  serializeHomeLoan();
  serializeInsurance();
  serializeDonations();
}

// ── SPOUSE SECTION ───────────────────────────────────────────────────────
document.getElementById("showSpouseForm")?.addEventListener("click", () => {
  document.getElementById("spouseForm").style.display = "block";
  document.getElementById("showSpouseForm").style.display = "none";
});

document.getElementById("submitSpouse")?.addEventListener("click", async () => {
  const name = document.querySelector('[name="spouse_name"]')?.value?.trim();
  const pan = document.querySelector('[name="spouse_pan"]')?.value?.trim();
  const phone = document.querySelector('[name="spouse_phone"]')?.value?.trim();

  if (!name || !phone) {
    alert("Please enter spouse name and phone number.");
    return;
  }
  if (phone && !/^\d{10}$/.test(phone)) {
    alert("Phone must be 10 digits.");
    return;
  }

  const statusEl = document.getElementById("spouseStatus");
  statusEl.style.display = "block";
  statusEl.className = "status loading";
  statusEl.textContent = "Saving spouse details...";

  try {
    await fetch(`${API}/save-phase`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        submission_id: submissionId,
        spouse_name: name,
        spouse_pan: pan,
        spouse_phone: phone,
        spouse_discount: "20",
      }),
    });
    statusEl.className = "status success";
    statusEl.textContent =
      "✅ Spouse details saved! 20% discount will be applied to their filing.";
    document.getElementById("submitSpouse").disabled = true;
  } catch (e) {
    statusEl.className = "status error";
    statusEl.textContent = "❌ Error saving: " + e.message;
  }
});

// ── MANUAL OVERRIDE FLAG for 80G ─────────────────────────────────────────
document
  .querySelector('[name="sec_80g"]')
  ?.addEventListener("input", function () {
    this.dataset.manualOverride = this.value ? "1" : "";
  });

// ── STEP 3: BACKGROUND EXTRACTION (fires on file select, no global loader) ───
const STEP3_DOCS = [
  ["docHome",      "homeloan",  "homeLoanStatus"],
  ["docInsLife",   "insurance", "lifeInsStatus"],
  ["docInsHealth", "insurance", "healthSelfStatus"],
  ["docNps",       "nps",       "npsStatus"],
  ["docSchool",    "school",    "schoolStatus"],
  ["docDon",       "donation",  "donationStatus"],
];
const _step3Controllers = {};
const _step3Promises    = {};

async function extractSectionBg(inputId, docType, statusId) {
  const input = document.getElementById(inputId);
  if (!input || !input.files.length) return;

  if (_step3Controllers[inputId]) _step3Controllers[inputId].abort();
  const controller = new AbortController();

  // STEP 1: Immediately upload/save documents (before extraction)
  // This ensures documents are saved even if extraction fails or user cancels
  await uploadDocumentImmediately(inputId, docType, statusId);
  _step3Controllers[inputId] = controller;

  const statusEl = document.getElementById(statusId);
  if (statusEl) {
    statusEl.style.display = "block";
    statusEl.className = "status loading";
    statusEl.textContent = "🔍 Extracting…";
  }

  const fd = new FormData();
  [...input.files].forEach((f) => fd.append("file", f));
  fd.append("doc_type", docType);
  fd.append("submission_id", submissionId);

  try {
    const r = await fetch(`${API}/itr/extract`, {
      method: "POST",
      body: fd,
      signal: controller.signal,
    });
    const j = await r.json();
    if (j.success && j.data && Object.keys(j.data).length > 0) {
      fillInvestmentFields(j.data, docType);
      if (statusEl) {
        _lastExtraction[inputId] = { data: j.data, docType };
        statusEl.className = "status success";
        statusEl.innerHTML = `✅ Extracted! ${_dvVerifyBtn(inputId)}`;
      }
    } else if (statusEl) {
      statusEl.className = "status";
      statusEl.textContent = "⚠️ Could not extract — fill fields manually.";
    }
  } catch (err) {
    if (err.name === "AbortError") return;
    if (statusEl) {
      statusEl.className = "status error";
      statusEl.textContent = "❌ " + err.message;
    }
  }
}

// ── IMMEDIATE DOCUMENT UPLOAD (Save on file selection, silent) ──────────────────────
async function uploadDocumentImmediately(inputId, docType, statusId) {
  const input = document.getElementById(inputId);
  if (!input || !input.files.length) return;

  const fd = new FormData();
  [...input.files].forEach((f) => fd.append("documents", f));
  fd.append("doc_type", docType);
  fd.append("submission_id", submissionId);

  try {
    console.log(`[UPLOAD] Saving ${input.files.length} file(s) for ${docType} in background`);
    const r = await fetch(`${API}/upload-document`, { method: "POST", body: fd });
    const j = await r.json();

    if (j.success) {
      console.log(`[UPLOAD] Documents saved: ${j.urls.join(", ")}`);
      return true;
    } else {
      console.warn(`[UPLOAD] Could not save: ${j.error}. Extraction will proceed.`);
      return false;
    }
  } catch (err) {
    console.error(`[UPLOAD] Background save failed: ${err.message}. Extraction will proceed.`);
    return false;
  }
}

// ── INLINE DOCUMENT EXTRACTION ───────────────────────────────────────────
async function extractSection(inputId, docType, statusId) {
  const input = document.getElementById(inputId);
  if (!input || !input.files.length) {
    alert("Please select a file first, then click Extract.");
    return;
  }

  const statusEl = document.getElementById(statusId);
  const signal = startExtractionLoader();

  if (statusEl) {
    statusEl.style.display = "block";
    statusEl.className = "status loading";
    statusEl.textContent = "🔍 AI reading document...";
  }

  // STEP 1: Immediately upload/save documents in background (non-blocking)
  uploadDocumentImmediately(inputId, docType, statusId);

  const fd = new FormData();
  [...input.files].forEach((f) => fd.append("file", f));
  fd.append("doc_type", docType);
  fd.append("submission_id", submissionId);

  try {
    // Use /api/itr/extract for proper ITR extraction
    const r = await fetch(`${API}/itr/extract`, { method: "POST", body: fd, signal });
    const j = await r.json();

    if (j.success && j.data && Object.keys(j.data).length > 0) {
      fillInvestmentFields(j.data, docType);
      if (statusEl) {
        _lastExtraction[inputId] = { data: j.data, docType };
        statusEl.className = "status success";
        statusEl.innerHTML = `✅ Extracted! Review & confirm the fields below. ${_dvVerifyBtn(inputId)}`;
      }
    } else {
      if (statusEl) {
        statusEl.className = "status error";
        statusEl.textContent =
          "⚠️ Could not auto-extract — please fill fields manually.";
      }
    }
  } catch (err) {
    if (err.name === "AbortError") return;
    if (statusEl) {
      statusEl.className = "status error";
      statusEl.textContent = "❌ " + err.message;
    }
  } finally {
    stopExtractionLoader();
  }
}

function fillInvestmentFields(data, docType) {
  const set = (name, val) => {
    const el = document.querySelector(`[name="${name}"]`);
    if (el && val && !el.value) el.value = val;
  };

  if (docType === "homeloan") {
    addHomeLoan();
    const rows = document.querySelectorAll("#homeLoanList .entry-row");
    const last = rows[rows.length - 1];
    if (last) {
      if (data.loan_account_no)
        last.querySelector('[data-key="policy_no"]').value =
          data.loan_account_no;
      if (data.bank_name)
        last.querySelector('[data-key="bank_name"]').value = data.bank_name;
      if (data.loan_outstanding)
        last.querySelector('[data-key="outstanding"]').value =
          data.loan_outstanding;
    }
    serializeHomeLoan();
    // Also store in hidden-compatible fields for calc
    if (data.home_loan_interest)
      set("home_loan_interest", data.home_loan_interest);
    if (data.home_loan_principal)
      set("home_loan_principal", data.home_loan_principal);
  } else if (docType === "nps") {
    set("nps_pran", data.nps_pran);
    set("nps_self", data.nps_self);
    set("nps_employer", data.nps_employer);
  } else if (docType === "school") {
    set("school_fees", data.school_fees);
  } else if (docType === "insurance") {
    const isHealth = (data.coverage_type || "")
      .toLowerCase()
      .includes("health");
    const listId = isHealth ? "healthSelfList" : "lifeInsList";
    const insType = isHealth ? "health_self" : "life";
    addInsurance(listId, insType);
    const rows = document.querySelectorAll(`#${listId} .entry-row`);
    const last = rows[rows.length - 1];
    if (last) {
      if (data.insurer_name)
        last.querySelector('[data-key="company"]').value = data.insurer_name;
      if (data.policy_no)
        last.querySelector('[data-key="policy_no"]').value = data.policy_no;
      if (data.premium_amount)
        last.querySelector('[data-key="premium"]').value = data.premium_amount;
    }
    serializeInsurance();
  } else if (docType === "donation") {
    addDonation();
    const rows = document.querySelectorAll("#donationList .entry-row");
    const last = rows[rows.length - 1];
    if (last) {
      if (data.donee_pan)
        last.querySelector('[data-key="donee_pan"]').value = data.donee_pan;
      if (data.organization_name)
        last.querySelector('[data-key="institution"]').value =
          data.organization_name;
      if (data.donation_amount)
        last.querySelector('[data-key="amount"]').value = data.donation_amount;
    }
    serializeDonations();
  }
}

// ─── PREMIUM ANIMATIONS & INTERACTIONS ───────────────────────────────────
// Scroll-triggered animations for form elements
function initScrollAnimations() {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.style.opacity = "1";
          entry.target.style.transform = "translateY(0)";
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.1, rootMargin: "0px 0px -50px 0px" },
  );

  $$(
    ".choice-buttons, .file, .grid label, .proof-section, .option-card",
  ).forEach((el) => {
    el.style.opacity = "0";
    el.style.transform = "translateY(20px)";
    el.style.transition = "opacity 0.5s ease, transform 0.5s ease";
    observer.observe(el);
  });
}

// Premium form field focus effects
function initPremiumFormInteractions() {
  $$("input, select, textarea").forEach((field) => {
    field.addEventListener("focus", () => {
      const parent = field.parentElement;
      if (parent) {
        parent.style.transition = "all 0.3s ease";
      }
    });
  });
}

// Premium button interactions
function initPremiumButtonEffects() {
  $$("button").forEach((btn) => {
    btn.addEventListener("mouseenter", function () {
      if (
        this.classList.contains("btn-primary") ||
        this.classList.contains("choice-type")
      ) {
        this.style.transform = "translateY(-4px)";
      }
    });

    btn.addEventListener("mouseleave", function () {
      this.style.transform = "none";
    });
  });
}

// Advanced form field interactions
function initAdvancedFormInteractions() {
  const formCard = document.querySelector("form");
  if (!formCard) return;

  // Add float labels effect
  $$("input, select, textarea").forEach((field) => {
    field.addEventListener("focus", function () {
      this.parentElement.style.background = "rgba(245,158,11,0.02)";
    });

    field.addEventListener("blur", function () {
      this.parentElement.style.background = "";
    });
  });
}

// Mobile optimization
function initMobileOptimizations() {
  const isMobile = window.innerWidth < 768;
  if (isMobile) {
    // Reduce animation duration on mobile for better performance
    document.documentElement.style.setProperty(
      "--transition",
      "150ms cubic-bezier(0.4, 0, 0.2, 1)",
    );
    document.documentElement.style.setProperty(
      "--transition-smooth",
      "200ms cubic-bezier(0.25, 0.46, 0.45, 0.94)",
    );

    // Make buttons larger on mobile
    $$("button").forEach((btn) => {
      btn.style.minHeight = "48px";
    });
  }
}

// Performance optimization - lazy load animations
function initPerformanceOptimizations() {
  // Use requestAnimationFrame for smoother animations
  if ("requestAnimationFrame" in window) {
    let animationFrameId = null;

    window.addEventListener("scroll", () => {
      if (animationFrameId === null) {
        animationFrameId = requestAnimationFrame(() => {
          // Trigger scroll animations
          $$(".scroll-fade-in:not(.visible)").forEach((el) => {
            const rect = el.getBoundingClientRect();
            if (rect.top < window.innerHeight * 0.8) {
              el.classList.add("visible");
            }
          });

          animationFrameId = null;
        });
      }
    });
  }
}

// Document extraction premium experience
function enhanceDocumentExtraction() {
  const form = document.querySelector("#taxForm");
  if (!form) return;

  // Removed auto-extraction loader on file change — only show during actual Next button extraction
}

// Initialize all premium effects
function initPremiumEffects() {
  initScrollAnimations();
  initPremiumFormInteractions();
  initPremiumButtonEffects();
  initAdvancedFormInteractions();
  initMobileOptimizations();
  initPerformanceOptimizations();
  enhanceDocumentExtraction();

  // Monitor referral changes
  $$('[name^="ref_name_"], [name^="ref_phone_"]').forEach((field) => {
    field.addEventListener("change", updateReferralTeaser);
    field.addEventListener("input", () => {
      // Trigger milestone update on input
      setTimeout(updateReferralTeaser, 300);
    });
  });
}

showStep(1);

// Warm up the backend on page load so Step 1 save doesn't hit a cold server
fetch(API + '/health').catch(() => {});

// ── STEP 3: wire auto-extract the moment a file is selected ──────────────────
STEP3_DOCS.forEach(([inputId, docType, statusId]) => {
  const inp = document.getElementById(inputId);
  if (!inp) return;
  inp.addEventListener("change", () => {
    if (!inp.files.length) return;
    _step3Promises[inputId] = extractSectionBg(inputId, docType, statusId);
  });
});

// Initialize premium effects on DOM ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initPremiumEffects);
} else {
  initPremiumEffects();
}

// If page was opened from referral CTA, auto-open the user-details form
(function () {
  try {
    const params = new URLSearchParams(window.location.search);
    if (params.get("start") === "details") {
      setFilingType("regular");
      showStep(1);
      const nameInput = document.querySelector('[name="name"]');
      if (nameInput) {
        nameInput.focus();
        nameInput.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }
  } catch (e) {
    console.warn("start param handling failed", e);
  }
})();
// Adjust page spacing so sticky header/nav do not cover content when scrolling
function updateHeaderSpacing() {
  try {
    const header = document.querySelector("header");
    const nav = document.querySelector(".site-nav");
    let topOffset = 0;
    if (header) topOffset += header.offsetHeight;
    if (nav) topOffset += nav.offsetHeight;
    // Set CSS variables used by style.css to reserve space
    // Only set the spacing variables when header/nav are fixed or sticky
    const headerPos = header ? window.getComputedStyle(header).position : "";
    const navPos = nav ? window.getComputedStyle(nav).position : "";
    if (
      headerPos === "sticky" ||
      headerPos === "fixed" ||
      navPos === "sticky" ||
      navPos === "fixed"
    ) {
      document.documentElement.style.setProperty(
        "--site-top-offset",
        `${topOffset}px`,
      );
      document.documentElement.style.setProperty(
        "--main-top-offset",
        `${topOffset + 12}px`,
      );
    } else {
      document.documentElement.style.setProperty("--site-top-offset", `0px`);
      document.documentElement.style.setProperty("--main-top-offset", `0px`);
    }
  } catch (e) {
    // silently ignore in older browsers
    console.warn("updateHeaderSpacing failed", e);
  }
}

window.addEventListener("load", updateHeaderSpacing);
window.addEventListener("resize", updateHeaderSpacing);
// call once in case DOM is already ready
updateHeaderSpacing();
