// Shuddh Seva Foods - Core Storefront Script (with OTP Verification)
const products = window.SHOP_PRODUCTS || [];

// Selected size state per product
let selectedSizes = {};
products.forEach(p => {
  const sizes = Object.keys(p.sizes);
  selectedSizes[p.id] = sizes[0] || '100';
});

// Flip state per product card on the catalog
let flippedCards = {};

// Cart state
let cart = {};
try {
  const savedCart = localStorage.getItem('shuddh_seva_cart');
  if (savedCart) cart = JSON.parse(savedCart);
} catch (e) {
  cart = {};
}

// Active coupon state
let appliedCoupon = null;

// Modal active product
let activeProduct = null;
let activeModalSide = 'front';

// Current logged in user
let currentUser = null;
let pendingCheckout = false;

// OTP state
let otpTargetPhone = '';
let isTargetExistingUser = false;
let resendTimerInterval = null;

function saveCart() {
  try {
    localStorage.setItem('shuddh_seva_cart', JSON.stringify(cart));
  } catch (e) {}
  updateCartBadge();
}

function updateCartBadge() {
  const totalQty = Object.values(cart).reduce((sum, item) => sum + item.qty, 0);
  const badge = document.getElementById('cartBadge');
  if (badge) badge.textContent = totalQty;
}

// Image URL resolver: handles static files, uploaded base64 data URIs, and external URLs
function resolveImgUrl(img) {
  if (!img) return '/static/images/combo_pack.jpg';
  if (typeof img !== 'string') return '/static/images/combo_pack.jpg';
  if (img.startsWith('data:') || img.startsWith('http://') || img.startsWith('https://')) {
    return img;
  }
  if (img.startsWith('/static/')) {
    return img;
  }
  if (img.startsWith('/')) {
    return img;
  }
  return `/static/images/${img}`;
}

// ---------------- USER OTP AUTHENTICATION ---------------- //
async function checkAuthStatus() {
  try {
    const res = await fetch('/api/auth/me');
    const data = await res.json();
    if (data.logged_in && data.user) {
      currentUser = data.user;
      renderUserAuthNav(data.is_admin);
      prefillCustomerForm();
    } else {
      currentUser = null;
      renderUserAuthNav(data.is_admin);
    }
  } catch (e) {
    currentUser = null;
    renderUserAuthNav(false);
  }
}

function renderUserAuthNav(isAdmin = false) {
  const container = document.getElementById('userAuthContainer');
  if (!container) return;

  const adminMenuLink = (isAdmin || (currentUser && currentUser.is_admin))
    ? `<a href="/admin/dashboard" style="color:#c2410c; font-weight:700; background:#fff7ed; padding:6px 12px; display:block; border-bottom:1px solid #fed7aa;">👑 Admin Dashboard</a>`
    : '';

  if (currentUser) {
    container.innerHTML = `
      <div class="user-dropdown">
        <button type="button" class="btn-user-pill" style="display:flex; flex-direction:column; align-items:flex-start; line-height:1.2; padding:5px 12px; background:#fff; border:1px solid #d5d9d9;">
          <small style="font-size:11px; color:#565959;">Hello, ${(currentUser.name || 'User').split(' ')[0]}</small>
          <span style="font-weight:700; font-size:13px; color:#0f1111;">Account & Orders ▾</span>
        </button>
        <div class="user-menu">
          ${adminMenuLink}
          <button type="button" onclick="openMyOrdersModal()">📦 Your Orders</button>
          <a href="/login" style="color:var(--primary);">👤 Switch Account</a>
          <button type="button" onclick="handleLogout()" style="color:#c53030;">⏻ Sign Out</button>
        </div>
      </div>
    `;
  } else {
    container.innerHTML = `
      <a href="/login" class="btn-auth" style="display:inline-flex; flex-direction:column; align-items:flex-start; line-height:1.2; padding:5px 12px; text-decoration:none; background:#fff; border:1px solid #d5d9d9;">
        <small style="font-size:11px; color:#565959;">Hello, sign in</small>
        <span style="font-weight:700; font-size:13px; color:#0f1111;">Account & Lists ▾</span>
      </a>
    `;
  }

  // Update checkout warning banner
  const banner = document.getElementById('checkoutAuthWarning');
  if (banner) {
    banner.style.display = currentUser ? 'none' : 'flex';
  }
}

function prefillCustomerForm() {
  if (!currentUser) return;
  const nameInput = document.getElementById('custName');
  const phoneInput = document.getElementById('custPhone');
  const emailInput = document.getElementById('custEmail');
  const addrInput = document.getElementById('custAddress');
  const landmarkInput = document.getElementById('custLandmark');
  const cityInput = document.getElementById('custCity');
  const stateInput = document.getElementById('custState');
  const pinInput = document.getElementById('custPincode');

  if (nameInput && !nameInput.value) nameInput.value = currentUser.name || '';
  if (phoneInput && !phoneInput.value) phoneInput.value = currentUser.phone || '';
  if (emailInput && !emailInput.value) emailInput.value = currentUser.email || '';
  if (addrInput && !addrInput.value) addrInput.value = currentUser.address || '';
  if (landmarkInput && !landmarkInput.value) landmarkInput.value = currentUser.landmark || '';
  if (cityInput && !cityInput.value) cityInput.value = currentUser.city || 'Jaipur';
  if (stateInput && !stateInput.value) stateInput.value = currentUser.state || 'Rajasthan';
  if (pinInput && !pinInput.value) pinInput.value = currentUser.pincode || '';
}

// Current auth mode in modal ('phone' or 'email')
let modalAuthChannel = 'phone';
let modalAuthTarget = '';

// Language state
let currentLang = localStorage.getItem('shuddh_seva_lang') || 'en';

const i18n = {
  en: {
    langBtn: 'हिंदी',
    navHome: 'Home',
    navSpices: 'Pure Spices',
    navPurity: 'Purity Promise',
    navReviews: 'Customer Reviews',
    navContact: 'Contact & Help',
    heroTag: '🌿 100% PURE & NATURAL SPICES',
    heroTitle: 'Authentic Spices For A<br><span>Healthier Everyday Life</span>',
    heroSlogan: '"हमारा देश से, शुद्धता का वादा • सेहत का साथ"',
    shopNow: 'Shop Pure Spices Now ↓',
    explorePurity: 'Explore Purity Promise →',
    trackOrder: '🔍 Track Order',
    cart: '🛒 Cart',
    helloSignIn: 'Hello, sign in',
    accountLists: 'Account & Lists ▾',
    yourOrders: '📦 Your Orders',
    signOut: '⏻ Sign Out'
  },
  hi: {
    langBtn: 'English',
    navHome: 'मुख्य पृष्ठ',
    navSpices: 'शुद्ध मसाले',
    navPurity: 'शुद्धता का वादा',
    navReviews: 'ग्राहक समीक्षा',
    navContact: 'संपर्क करें',
    heroTag: '🌿 100% शुद्ध और प्राकृतिक मसाले',
    heroTitle: 'सेहतमंद और खुशहाल जीवन के लिए<br><span>असली शुद्ध भारतीय मसाले</span>',
    heroSlogan: '"हमारा देश से, शुद्धता का वादा • सेहत का साथ"',
    shopNow: 'शुद्ध मसाले अभी खरीदें ↓',
    explorePurity: 'शुद्धता का वादा देखें →',
    trackOrder: '🔍 ऑर्डर ट्रैक करें',
    cart: '🛒 कार्ट',
    helloSignIn: 'नमस्ते, लॉगिन करें',
    accountLists: 'खाता और सूचियाँ ▾',
    yourOrders: '📦 आपके ऑर्डर्स',
    signOut: '⏻ लॉगआउट'
  }
};

function toggleLanguage() {
  currentLang = (currentLang === 'en') ? 'hi' : 'en';
  localStorage.setItem('shuddh_seva_lang', currentLang);
  applyLanguage(currentLang);
}

function applyLanguage(lang) {
  const t = i18n[lang] || i18n.en;
  const langLabel = document.getElementById('langLabel');
  if (langLabel) langLabel.textContent = t.langBtn;

  // Nav links
  const navLinks = document.querySelectorAll('.nav-links a');
  if (navLinks.length >= 5) {
    navLinks[0].textContent = t.navHome;
    navLinks[1].textContent = t.navSpices;
    navLinks[2].textContent = t.navPurity;
    navLinks[3].textContent = t.navReviews;
    navLinks[4].textContent = t.navContact;
  }

  // Hero elements
  const heroTag = document.querySelector('.hero-tag');
  if (heroTag) heroTag.textContent = t.heroTag;

  const heroHeading = document.querySelector('.hero-text h2');
  if (heroHeading) heroHeading.innerHTML = t.heroTitle;

  const heroCta = document.querySelector('.hero-btns .btn-cta');
  if (heroCta) heroCta.textContent = t.shopNow;

  const heroSec = document.querySelector('.hero-btns .btn-secondary');
  if (heroSec) heroSec.textContent = t.explorePurity;

  // Track button
  const trackBtn = document.querySelector('.btn-track');
  if (trackBtn) trackBtn.textContent = t.trackOrder;

  renderUserAuthNav();
  renderProducts();
}

function switchModalAuthTab(channel) {
  modalAuthChannel = channel;
  const tabPhone = document.getElementById('modalTabPhone');
  const tabEmail = document.getElementById('modalTabEmail');
  const groupPhone = document.getElementById('modalGroupPhone');
  const groupEmail = document.getElementById('modalGroupEmail');
  const alertBox = document.getElementById('modalAlertBox');

  if (alertBox) {
    alertBox.style.display = 'none';
    alertBox.innerHTML = '';
  }

  if (channel === 'phone') {
    if (tabPhone) { tabPhone.style.borderBottomColor = '#e47911'; tabPhone.style.color = '#4a210f'; }
    if (tabEmail) { tabEmail.style.borderBottomColor = 'transparent'; tabEmail.style.color = '#767676'; }
    if (groupPhone) groupPhone.style.display = 'block';
    if (groupEmail) groupEmail.style.display = 'none';
    document.getElementById('otpPhoneInput')?.focus();
  } else {
    if (tabEmail) { tabEmail.style.borderBottomColor = '#e47911'; tabEmail.style.color = '#4a210f'; }
    if (tabPhone) { tabPhone.style.borderBottomColor = 'transparent'; tabPhone.style.color = '#767676'; }
    if (groupPhone) groupPhone.style.display = 'none';
    if (groupEmail) groupEmail.style.display = 'block';
    document.getElementById('otpEmailInput')?.focus();
  }
}

function openAuthModal(reasonText = '') {
  resetOtpForm();
  const reasonBox = document.getElementById('authReasonBox');
  if (reasonBox) {
    if (reasonText) {
      reasonBox.textContent = reasonText;
      reasonBox.style.display = 'flex';
    } else {
      reasonBox.style.display = 'none';
    }
  }
  document.getElementById('authModal').classList.add('show');
}

function closeAuthModal() {
  document.getElementById('authModal').classList.remove('show');
  clearInterval(resendTimerInterval);
}

function resetOtpForm() {
  document.getElementById('otpStepSend').style.display = 'block';
  document.getElementById('otpStepVerify').style.display = 'none';
  const pInput = document.getElementById('otpPhoneInput');
  const eInput = document.getElementById('otpEmailInput');
  const dInput = document.getElementById('otpDigitInput');
  if (pInput) pInput.value = '';
  if (eInput) eInput.value = '';
  if (dInput) dInput.value = '';

  const alert1 = document.getElementById('modalAlertBox');
  const alert2 = document.getElementById('modalVerifyAlertBox');
  if (alert1) alert1.style.display = 'none';
  if (alert2) alert2.style.display = 'none';

  clearInterval(resendTimerInterval);
}

// Step 1: Send OTP
async function handleSendOtp(e) {
  if (e) e.preventDefault();
  const alertBox = document.getElementById('modalAlertBox');
  if (alertBox) alertBox.style.display = 'none';

  let targetVal = '';
  if (modalAuthChannel === 'phone') {
    targetVal = (document.getElementById('otpPhoneInput')?.value || '').trim();
    targetVal = targetVal.replace(/\D/g, '');
    if (targetVal.length > 10 && targetVal.startsWith('91')) targetVal = targetVal.slice(-10);
    if (targetVal.length !== 10) {
      alert('Please enter a valid 10-digit Indian mobile number.');
      return;
    }
  } else {
    targetVal = (document.getElementById('otpEmailInput')?.value || '').trim();
    if (!targetVal || !targetVal.includes('@') || !targetVal.includes('.')) {
      alert('Please enter a valid email address.');
      return;
    }
  }

  modalAuthTarget = targetVal;
  const btn = document.getElementById('sendOtpBtn');
  btn.disabled = true;
  btn.textContent = 'Sending OTP...';

  try {
    const res = await fetch('/api/auth/send-otp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target: modalAuthTarget,
        type: modalAuthChannel
      })
    });
    const data = await res.json();

    if (data.success) {
      isTargetExistingUser = data.is_existing;

      // Transition to Step 2
      document.getElementById('otpStepSend').style.display = 'none';
      document.getElementById('otpStepVerify').style.display = 'block';
      document.getElementById('displayTargetPhone').textContent = data.target_masked || modalAuthTarget;

      // Show/hide new user fields
      const newFields = document.getElementById('newUserFields');
      if (isTargetExistingUser) {
        if (newFields) newFields.style.display = 'none';
        document.getElementById('verifyOtpHeading').textContent = `Welcome back, ${data.user_name || 'Customer'}!`;
      } else {
        if (newFields) newFields.style.display = 'block';
        document.getElementById('verifyOtpHeading').textContent = 'Enter OTP & Details to Complete Signup';
      }

      // Auto-fill OTP field if in demo/instant mode (e.g., initial Vercel deploy)
      if (data.demo_mode && data.demo_otp) {
        const dInput = document.getElementById('otpDigitInput');
        if (dInput) dInput.value = data.demo_otp;
      }

      const vAlert = document.getElementById('modalVerifyAlertBox');
      if (vAlert) {
        vAlert.style.display = 'block';
        vAlert.style.background = '#f0fdf4';
        vAlert.style.border = '1px solid #86efac';
        vAlert.style.color = '#166534';
        let alertHtml = `✓ ${data.message}`;
        if (data.demo_mode && data.demo_otp) {
          alertHtml = `⚡ <b>Verification Code:</b> <span style="font-size:16px; font-weight:800; letter-spacing:2px; background:#fff; padding:2px 8px; border-radius:4px; border:1px solid #86efac; color:#15803d;">${data.demo_otp}</span> <small style="display:block; color:#166534; margin-top:3px;">(Auto-filled for instant verification on Vercel)</small>`;
        }
        if (data.is_admin) {
          alertHtml += `<div style="margin-top:8px; padding:6px 10px; background:#fff7ed; border:1px solid #fed7aa; border-radius:6px; font-size:12px; color:#9a3412;">👑 <b>Store Owner:</b> <a href="/admin/login" style="color:#c2410c; font-weight:700; text-decoration:underline;">Click here to Direct Login with Password</a></div>`;
        }
        vAlert.innerHTML = alertHtml;
      }

      startResendCountdown();
    } else {
      if (data.provider_unconfigured) {
        if (alertBox) {
          alertBox.style.display = 'block';
          alertBox.style.background = '#f0f9ff';
          alertBox.style.border = '1px solid #bae6fd';
          alertBox.style.color = '#0369a1';
          alertBox.innerHTML = `⚙️ <b>Provider Notice:</b> ${data.error}`;
        } else {
          alert(`Provider Notice: ${data.error}`);
        }
      } else {
        alert(data.error || 'Failed to send OTP.');
      }
    }
  } catch (err) {
    alert('Network error sending OTP. Please check your connection.');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Send OTP';
  }
}

function startResendCountdown() {
  let seconds = 45;
  const resendBtn = document.getElementById('resendOtpBtn');
  const timerSpan = document.getElementById('resendTimer');
  if (resendBtn) {
    resendBtn.style.pointerEvents = 'none';
    resendBtn.style.color = '#767676';
  }

  clearInterval(resendTimerInterval);
  resendTimerInterval = setInterval(() => {
    seconds--;
    if (seconds > 0) {
      if (timerSpan) timerSpan.textContent = `(${seconds}s)`;
    } else {
      clearInterval(resendTimerInterval);
      if (timerSpan) timerSpan.textContent = '';
      if (resendBtn) {
        resendBtn.style.pointerEvents = 'auto';
        resendBtn.style.color = '#007185';
      }
    }
  }, 1000);
}

// Step 2: Verify OTP & Login/Signup
async function handleVerifyOtp(e) {
  if (e) e.preventDefault();
  const otpCode = document.getElementById('otpDigitInput').value.trim();
  const name = document.getElementById('newUserName')?.value.trim() || '';

  if (otpCode.length !== 6 || !/^\d+$/.test(otpCode)) {
    alert('Please enter the 6-digit numeric OTP code.');
    return;
  }

  if (!isTargetExistingUser && !name) {
    alert('Please enter your Full Name to complete signup.');
    return;
  }

  const btn = document.getElementById('verifyOtpBtn');
  btn.disabled = true;
  btn.textContent = 'Verifying...';

  try {
    const res = await fetch('/api/auth/verify-otp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target: modalAuthTarget,
        type: modalAuthChannel,
        otp_code: otpCode,
        name: name
      })
    });
    const data = await res.json();

    if (data.success) {
      currentUser = data.user;
      renderUserAuthNav();
      prefillCustomerForm();
      closeAuthModal();
      showToast(`🎉 Verified successfully! Welcome ${currentUser.name}!`);

      if (pendingCheckout) {
        pendingCheckout = false;
        openCart();
      }
    } else {
      alert(data.error || 'Invalid OTP code.');
    }
  } catch (err) {
    alert('Network error verifying OTP.');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Verify & Continue';
  }
}

async function handleLogout() {
  try {
    await fetch('/api/auth/logout', { method: 'POST' });
    currentUser = null;
    renderUserAuthNav();
    showToast('🚪 Logged out successfully.');
  } catch (e) {
    currentUser = null;
    renderUserAuthNav();
  }
}

// ---------------- MY ORDERS MODAL ---------------- //
async function openMyOrdersModal() {
  if (!currentUser) {
    openAuthModal('Please login via OTP to view orders.');
    return;
  }
  const modal = document.getElementById('myOrdersModal');
  const container = document.getElementById('myOrdersContainer');
  container.innerHTML = '<p style="text-align:center; padding:20px;">Loading your orders...</p>';
  modal.classList.add('show');

  try {
    const res = await fetch('/api/user/orders');
    const data = await res.json();

    if (data.success && data.orders && data.orders.length) {
      container.innerHTML = data.orders.map(o => {
        const dateStr = new Date(o.created_at).toLocaleDateString('en-IN', {
          day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'
        });
        const itemsText = o.items.map(i => `• ${i.name} (${i.size}g) × ${i.qty}`).join('<br>');
        return `
          <div class="my-order-card">
            <div class="my-order-header">
              <div>
                <strong style="color:var(--primary); font-size:15px;">Order #${o.order_id}</strong>
                <div style="font-size:12px; color:var(--muted);">${dateStr}</div>
              </div>
              <span class="badge" style="background:#e8f5e9; color:#1b5e20; font-weight:800; padding:4px 10px; border-radius:12px;">
                ${o.order_status}
              </span>
            </div>
            <div style="font-size:13px; line-height:1.5; margin-bottom:8px;">
              ${itemsText}
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center; border-top:1px dashed var(--border); padding-top:8px; margin-top:8px;">
              <strong style="color:var(--primary); font-size:15px;">Total: ₹${Math.round(o.total_amount)} (${o.payment_method})</strong>
              <a href="/admin/invoice/${o.order_id}" target="_blank" style="color:var(--primary); font-size:12px; font-weight:700; text-decoration:underline;">
                🖨️ View Bill
              </a>
            </div>
          </div>
        `;
      }).join('');
    } else {
      container.innerHTML = `
        <div style="text-align:center; padding:40px 10px; color:var(--muted);">
          <p style="font-size:36px;">📦</p>
          <p style="font-weight:700; font-size:15px;">No orders found</p>
          <p style="font-size:13px;">You have not placed any spice orders yet.</p>
        </div>
      `;
    }
  } catch (err) {
    container.innerHTML = '<p style="color:#c53030; text-align:center;">Failed to load orders.</p>';
  }
}

function closeMyOrdersModal() {
  document.getElementById('myOrdersModal').classList.remove('show');
}

// ---------------- PRODUCTS CATALOG ---------------- //
function renderProducts() {
  const grid = document.getElementById('productGrid');
  if (!grid) return;

  const search = (document.getElementById('searchInput')?.value || '').toLowerCase().trim();
  const filterCat = document.getElementById('categoryFilter')?.value || 'all';

  const filtered = products.filter(p => {
    const matchesSearch = p.name.toLowerCase().includes(search) || 
                          p.hindi.includes(search) || 
                          p.tagline.toLowerCase().includes(search);
    const matchesCategory = (filterCat === 'all' || p.category === filterCat);
    return matchesSearch && matchesCategory;
  });

  if (!filtered.length) {
    grid.innerHTML = `
      <div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--muted);">
        <p style="font-size: 32px;">🔍</p>
        <h3>No spices found matching your search.</h3>
        <p>Try searching for "haldi", "chilli", "coriander" or "combo".</p>
      </div>
    `;
    return;
  }

  grid.innerHTML = filtered.map(p => {
    const currentSize = selectedSizes[p.id];
    const sizeData = p.sizes[currentSize] || p.sizes[Object.keys(p.sizes)[0]];
    const isFlipped = !!flippedCards[p.id];

    const sizePills = Object.keys(p.sizes).map(s => {
      const activeClass = (s === currentSize) ? 'active' : '';
      return `<button type="button" class="size-pill ${activeClass}" onclick="selectSize('${p.id}', '${s}', event)">${s}g</button>`;
    }).join('');

    return `
      <article class="product-card" id="card-${p.id}">
        <span class="badge-tag">${p.badge || '100% Pure'}</span>
        
        <div class="card-media-wrapper">
          <div class="card-flipper ${isFlipped ? 'flipped' : ''}" id="flipper-${p.id}">
            <!-- Front Face -->
            <div class="card-face card-face-front" onclick="openQuickView('${p.id}')" title="Click to view full packaging details">
              <img src="${resolveImgUrl(p.front)}" alt="${p.name} Front Packaging">
            </div>
            <!-- Back Face -->
            <div class="card-face card-face-back" onclick="openQuickView('${p.id}')" title="Click to view full back label details">
              <img src="${resolveImgUrl(p.back)}" alt="${p.name} Back Packaging">
            </div>
          </div>
          <!-- 3D Flip Button -->
          <button type="button" class="btn-flip-toggle" onclick="toggleCardFlip('${p.id}', event)">
            🔄 ${isFlipped ? 'Show Front' : 'Show Back'}
          </button>
        </div>

        <div class="card-content">
          <h3 class="card-title">${p.name}</h3>
          <div class="card-hindi">${p.hindi} • <span style="color:var(--accent); font-weight:700;">${p.tagline}</span></div>
          
          <div class="card-rating">
            <span>⭐⭐⭐⭐⭐</span>
            <span>${p.rating} (${p.reviews_count} reviews)</span>
          </div>

          <p class="card-desc">${p.short_desc || p.description}</p>

          <div class="size-selector">
            ${sizePills}
          </div>

          <div class="price-row">
            <span class="price-main">₹${sizeData.price}</span>
            <span class="price-mrp">₹${sizeData.mrp}</span>
            <span class="price-save">${sizeData.save || 'SAVE'}</span>
          </div>

          <div class="card-actions">
            <button type="button" class="btn-add-cart" onclick="addToCart('${p.id}', '${currentSize}')">
              🛒 Add to Cart
            </button>
            <button type="button" class="btn-view-details" onclick="openQuickView('${p.id}')">
              👁️ View Front & Back Details
            </button>
          </div>
        </div>
      </article>
    `;
  }).join('');
}

function toggleCardFlip(productId, event) {
  if (event) event.stopPropagation();
  flippedCards[productId] = !flippedCards[productId];
  const flipper = document.getElementById(`flipper-${productId}`);
  if (flipper) {
    if (flippedCards[productId]) {
      flipper.classList.add('flipped');
    } else {
      flipper.classList.remove('flipped');
    }
  }
  const btn = event?.currentTarget;
  if (btn) {
    btn.innerHTML = flippedCards[productId] ? '🔄 Show Front' : '🔄 Show Back';
  }
}

function selectSize(productId, size, event) {
  if (event) event.stopPropagation();
  selectedSizes[productId] = size;
  renderProducts();
}

function addToCart(productId, size, customQty = 1) {
  const p = products.find(x => x.id === productId);
  if (!p) return;

  const key = `${productId}-${size}`;
  const priceData = p.sizes[size];

  if (cart[key]) {
    cart[key].qty += customQty;
  } else {
    cart[key] = {
      id: p.id,
      name: p.name,
      hindi: p.hindi,
      front: p.front,
      back: p.back,
      size: size,
      price: priceData.price,
      mrp: priceData.mrp,
      qty: customQty
    };
  }

  saveCart();
  showToast(`✅ Added ${p.name} (${size}g) to cart!`);
}

function showToast(msg) {
  let toast = document.getElementById('appToast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'appToast';
    toast.style.position = 'fixed';
    toast.style.bottom = '30px';
    toast.style.left = '50%';
    toast.style.transform = 'translateX(-50%)';
    toast.style.background = '#301407';
    toast.style.color = '#fff';
    toast.style.padding = '12px 24px';
    toast.style.borderRadius = '30px';
    toast.style.fontWeight = '700';
    toast.style.fontSize = '14px';
    toast.style.boxShadow = '0 10px 25px rgba(0,0,0,0.3)';
    toast.style.zIndex = '9999';
    toast.style.transition = 'opacity 0.3s';
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.style.opacity = '1';
  clearTimeout(window.toastTimer);
  window.toastTimer = setTimeout(() => {
    toast.style.opacity = '0';
  }, 2500);
}

// Quick View Modal
function openQuickView(productId) {
  const p = products.find(x => x.id === productId);
  if (!p) return;
  activeProduct = p;
  activeModalSide = 'front';

  const modal = document.getElementById('quickViewModal');
  const size = selectedSizes[p.id];
  const sizeData = p.sizes[size];

  document.getElementById('qvTitle').textContent = p.name;
  document.getElementById('qvHindi').textContent = `${p.hindi} • ${p.tagline}`;
  document.getElementById('qvImage').src = resolveImgUrl(p.front);
  document.getElementById('qvPrice').textContent = `₹${sizeData.price}`;
  document.getElementById('qvMrp').textContent = `₹${sizeData.mrp}`;
  document.getElementById('qvSave').textContent = sizeData.save || 'Best Value';
  document.getElementById('qvQtyInput').value = 1;

  document.getElementById('qvFrontBtn').classList.add('active');
  document.getElementById('qvBackBtn').classList.remove('active');

  const qvSizesContainer = document.getElementById('qvSizes');
  qvSizesContainer.innerHTML = Object.keys(p.sizes).map(s => `
    <button type="button" class="size-pill ${s === size ? 'active' : ''}" onclick="selectQvSize('${s}')">${s}g</button>
  `).join('');

  setQvTab('overview');
  modal.classList.add('show');
}

function switchQvImage(side) {
  if (!activeProduct) return;
  activeModalSide = side;
  const img = document.getElementById('qvImage');
  const frontBtn = document.getElementById('qvFrontBtn');
  const backBtn = document.getElementById('qvBackBtn');

  if (side === 'front') {
    img.src = resolveImgUrl(activeProduct.front);
    frontBtn.classList.add('active');
    backBtn.classList.remove('active');
  } else {
    img.src = resolveImgUrl(activeProduct.back);
    backBtn.classList.add('active');
    frontBtn.classList.remove('active');
  }
}

function selectQvSize(size) {
  if (!activeProduct) return;
  selectedSizes[activeProduct.id] = size;
  const sizeData = activeProduct.sizes[size];
  document.getElementById('qvPrice').textContent = `₹${sizeData.price}`;
  document.getElementById('qvMrp').textContent = `₹${sizeData.mrp}`;
  document.getElementById('qvSave').textContent = sizeData.save || '';

  document.querySelectorAll('#qvSizes .size-pill').forEach(btn => {
    btn.classList.toggle('active', btn.textContent.trim() === `${size}g`);
  });

  renderProducts();
}

function setQvTab(tabName) {
  if (!activeProduct) return;
  document.querySelectorAll('.qv-tab').forEach(b => b.classList.remove('active'));
  const targetBtn = document.getElementById(`tabBtn-${tabName}`);
  if (targetBtn) targetBtn.classList.add('active');

  const contentDiv = document.getElementById('qvTabContent');
  if (tabName === 'overview') {
    contentDiv.innerHTML = `<p>${activeProduct.description}</p>`;
  } else if (tabName === 'ingredients') {
    contentDiv.innerHTML = `
      <p><strong>Ingredients:</strong> ${activeProduct.ingredients}</p>
      <p style="margin-top:6px; color:var(--accent); font-weight:700;">✓ 100% Natural • No Added Preservatives • No Synthetic Colours</p>
    `;
  } else if (tabName === 'usage') {
    contentDiv.innerHTML = `
      <p><strong>Usage Suggestions:</strong> ${activeProduct.usage}</p>
      <p style="margin-top:6px;"><strong>Storage Instructions:</strong> ${activeProduct.storage}</p>
    `;
  } else if (tabName === 'legal') {
    contentDiv.innerHTML = `
      <p><strong>FSSAI Lic. No:</strong> ${activeProduct.fssai}</p>
      <p><strong>Packed & Marketed by:</strong> ${activeProduct.manufacturer}</p>
      <p><strong>Customer Care:</strong> ${activeProduct.customer_care}</p>
      <p><strong>Barcode:</strong> ${activeProduct.barcode}</p>
    `;
  }
}

function closeQuickView() {
  document.getElementById('quickViewModal').classList.remove('show');
}

function addFromQuickView() {
  if (!activeProduct) return;
  const size = selectedSizes[activeProduct.id];
  const qty = parseInt(document.getElementById('qvQtyInput').value) || 1;
  addToCart(activeProduct.id, size, qty);
  closeQuickView();
}

// ---------------- CART & CHECKOUT ---------------- //
function openCart() {
  renderCartModal();
  document.getElementById('cartModal').classList.add('show');
}

function closeCart() {
  document.getElementById('cartModal').classList.remove('show');
}

function renderCartModal() {
  const container = document.getElementById('cartItemsList');
  const items = Object.values(cart);

  if (!items.length) {
    container.innerHTML = `
      <div style="text-align: center; padding: 40px 10px; color: var(--muted);">
        <p style="font-size: 36px;">🛒</p>
        <p style="font-size: 16px; font-weight: 700;">Your Cart is Empty</p>
        <p style="font-size: 13px;">Add pure, aromatic spices to get started!</p>
      </div>
    `;
    document.getElementById('cartSummaryArea').style.display = 'none';
    document.getElementById('checkoutFormArea').style.display = 'none';
    return;
  }

  document.getElementById('cartSummaryArea').style.display = 'block';
  document.getElementById('checkoutFormArea').style.display = 'block';

  prefillCustomerForm();

  const warning = document.getElementById('checkoutAuthWarning');
  if (warning) {
    warning.style.display = currentUser ? 'none' : 'flex';
  }

  container.innerHTML = items.map(item => {
    const key = `${item.id}-${item.size}`;
    return `
      <div class="cart-item-row">
        <div style="width: 50px; height: 50px; background:#f7f2e7; border-radius:8px; display:grid; place-items:center;">
          <img src="${resolveImgUrl(item.front)}" style="max-height: 42px; object-fit: contain;">
        </div>
        <div class="cart-item-info" style="flex:1;">
          <strong>${item.name}</strong>
          <small>${item.size}g • ₹${item.price} each</small>
        </div>
        <div class="qty-stepper">
          <button type="button" onclick="changeCartQty('${key}', -1)">-</button>
          <span>${item.qty}</span>
          <button type="button" onclick="changeCartQty('${key}', 1)">+</button>
        </div>
        <div style="text-align: right; min-width: 60px;">
          <strong style="color:var(--primary);">₹${item.price * item.qty}</strong>
          <div><button type="button" class="btn-remove" onclick="removeCartItem('${key}')" title="Remove item">🗑️</button></div>
        </div>
      </div>
    `;
  }).join('');

  const subtotal = items.reduce((sum, x) => sum + (x.price * x.qty), 0);
  let discount = 0;
  if (appliedCoupon === 'SHUDDH10') {
    discount = Math.round(subtotal * 0.10);
  } else if (appliedCoupon === 'SEVA50') {
    discount = Math.min(50, subtotal);
  }

  const freeDeliveryThreshold = 499;
  const deliveryFee = (subtotal - discount) >= freeDeliveryThreshold ? 0 : 40;
  const grandTotal = Math.max(0, (subtotal - discount + deliveryFee));

  document.getElementById('cartSubtotal').textContent = `₹${subtotal}`;
  document.getElementById('cartDiscount').textContent = discount > 0 ? `-₹${discount}` : '₹0';
  document.getElementById('cartDelivery').textContent = deliveryFee === 0 ? 'FREE' : `₹${deliveryFee}`;
  document.getElementById('cartTotal').textContent = `₹${grandTotal}`;

  const freeNotice = document.getElementById('freeDeliveryNotice');
  if (freeNotice) {
    if (subtotal >= freeDeliveryThreshold) {
      freeNotice.innerHTML = `🎉 <b>Congratulations!</b> You've unlocked FREE Home Delivery!`;
      freeNotice.style.background = '#e8f5e9';
      freeNotice.style.color = '#1b5e20';
    } else {
      const needed = freeDeliveryThreshold - subtotal;
      freeNotice.innerHTML = `🚚 Add <b>₹${needed}</b> more to get <b>FREE Home Delivery</b>!`;
      freeNotice.style.background = '#fff8e1';
      freeNotice.style.color = '#b78103';
    }
  }

  const qrImg = document.getElementById('upiQrCode');
  if (qrImg) {
    const upiUri = `upi://pay?pa=6350474290@paytm&pn=ShuddhSevaFoods&am=${grandTotal}&cu=INR&tn=OrderPayment`;
    qrImg.src = `https://api.qrserver.com/com/create-qr-code/?size=180x180&data=${encodeURIComponent(upiUri)}`;
  }
}

function changeCartQty(key, delta) {
  if (cart[key]) {
    cart[key].qty += delta;
    if (cart[key].qty <= 0) {
      delete cart[key];
    }
    saveCart();
    renderCartModal();
  }
}

function removeCartItem(key) {
  delete cart[key];
  saveCart();
  renderCartModal();
}

function applyCoupon() {
  const code = (document.getElementById('couponInput')?.value || '').trim().toUpperCase();
  if (code === 'SHUDDH10') {
    appliedCoupon = 'SHUDDH10';
    showToast('🎉 Coupon SHUDDH10 Applied (10% OFF)!');
  } else if (code === 'SEVA50') {
    appliedCoupon = 'SEVA50';
    showToast('🎉 Coupon SEVA50 Applied (₹50 OFF)!');
  } else {
    showToast('❌ Invalid coupon code');
  }
  renderCartModal();
}

function selectPaymentMethod(method) {
  document.querySelectorAll('.payment-method-card').forEach(c => c.classList.remove('selected'));
  const card = document.getElementById(`pay-${method}`);
  if (card) card.classList.add('selected');

  const upiBox = document.getElementById('upiDetailsBox');
  if (method === 'UPI') {
    upiBox.classList.add('show');
  } else {
    upiBox.classList.remove('show');
  }
}

// Submit Order (MANDATORY OTP AUTH CHECK)
async function submitOrder(e) {
  e.preventDefault();

  if (!currentUser) {
    pendingCheckout = true;
    closeCart();
    openAuthModal('⚠️ Order karne ke liye Mobile OTP verification jaruri hai.');
    return;
  }

  const items = Object.values(cart);
  if (!items.length) {
    alert('Your cart is empty.');
    return;
  }

  const name = document.getElementById('custName').value.trim();
  const phone = document.getElementById('custPhone').value.trim();
  const sameAsPhone = document.getElementById('sameAsPhoneCheckbox')?.checked;
  const whatsapp = sameAsPhone ? phone : (document.getElementById('custWhatsapp')?.value.trim() || phone);
  const email = document.getElementById('custEmail').value.trim();
  const address = document.getElementById('custAddress').value.trim();
  const landmark = document.getElementById('custLandmark').value.trim();
  const city = document.getElementById('custCity').value.trim();
  const state = document.getElementById('custState').value.trim();
  const pincode = document.getElementById('custPincode').value.trim();
  const notes = document.getElementById('custNotes').value.trim();

  const isUpi = document.getElementById('pay-UPI')?.classList.contains('selected');
  const paymentMethod = isUpi ? 'UPI' : 'COD';

  const subtotal = items.reduce((sum, x) => sum + (x.price * x.qty), 0);
  let discount = 0;
  if (appliedCoupon === 'SHUDDH10') discount = Math.round(subtotal * 0.10);
  else if (appliedCoupon === 'SEVA50') discount = Math.min(50, subtotal);
  const deliveryFee = (subtotal - discount) >= 499 ? 0 : 40;
  const total = Math.max(0, subtotal - discount + deliveryFee);

  const orderPayload = {
    name, phone, whatsapp, email,
    address, landmark, city, state, pincode,
    items, subtotal, discount, delivery_fee: deliveryFee, total,
    payment_method: paymentMethod, notes
  };

  const submitBtn = document.getElementById('placeOrderBtn');
  submitBtn.disabled = true;
  submitBtn.textContent = 'Processing Order...';

  try {
    const res = await fetch('/api/order', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(orderPayload)
    });
    const data = await res.json();

    if (data.success) {
      cart = {};
      appliedCoupon = null;
      saveCart();
      closeCart();

      showOrderConfirmation(data.order, data.whatsapp_message, data.admin_phone);
    } else {
      if (data.requires_auth) {
        pendingCheckout = true;
        closeCart();
        openAuthModal('⚠️ Order karne ke liye Mobile OTP verification jaruri hai.');
      } else {
        alert('Error placing order: ' + (data.error || 'Please try again.'));
      }
    }
  } catch (err) {
    alert('Network error while placing order. Please try again.');
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Place Order →';
  }
}

function showOrderConfirmation(order, waMessage, adminPhone) {
  const modal = document.getElementById('orderConfirmModal');
  document.getElementById('confirmOrderId').textContent = `#${order.order_id}`;
  document.getElementById('confirmCustName').textContent = order.customer_name;
  document.getElementById('confirmTotal').textContent = `₹${Math.round(order.total_amount)}`;
  document.getElementById('confirmAddress').textContent = `${order.address}, ${order.city}, ${order.state} - ${order.pincode}`;

  const waBtn = document.getElementById('confirmWaBtn');
  const targetPhone = adminPhone || '6350474290';
  waBtn.href = `https://wa.me/91${targetPhone}?text=${encodeURIComponent(waMessage)}`;

  const printBtn = document.getElementById('confirmPrintBtn');
  if (printBtn) printBtn.href = `/admin/invoice/${order.order_id}`;

  modal.classList.add('show');
}

function closeOrderConfirmation() {
  document.getElementById('orderConfirmModal').classList.remove('show');
}

// ---------------- ORDER TRACKING ---------------- //
function openTrackModal() {
  document.getElementById('trackModal').classList.add('show');
}

function closeTrackModal() {
  document.getElementById('trackModal').classList.remove('show');
}

async function searchTrackOrder(e) {
  e.preventDefault();
  const query = document.getElementById('trackQueryInput').value.trim();
  if (!query) return;

  const resultBox = document.getElementById('trackResultBox');
  resultBox.innerHTML = '<p>Searching order records...</p>';

  try {
    const res = await fetch(`/api/track?query=${encodeURIComponent(query)}`);
    const data = await res.json();

    if (data.success && data.order) {
      const o = data.order;
      const status = o.order_status;
      const date = new Date(o.created_at).toLocaleDateString('en-IN', { day:'numeric', month:'short', year:'numeric' });

      const steps = [
        { label: 'Order Received', desc: 'Order details verified', done: true },
        { label: 'Packed & Quality Checked', desc: 'Hygienically packaged', done: ['Confirmed', 'Shipped', 'Delivered'].includes(status) },
        { label: 'Dispatched from Jaipur', desc: 'On its way to you', done: ['Shipped', 'Delivered'].includes(status) },
        { label: 'Delivered', desc: 'Enjoy authentic spices!', done: status === 'Delivered' }
      ];

      resultBox.innerHTML = `
        <div style="background:#faf6ee; border-radius:12px; padding:18px; border:1px solid var(--border); margin-top:14px;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <div>
              <h4 style="color:var(--primary); font-size:16px;">Order #${o.order_id}</h4>
              <small style="color:var(--muted)">Placed on ${date}</small>
            </div>
            <span class="badge" style="background:#e8f5e9; color:#1b5e20; font-weight:800; padding:6px 12px; border-radius:14px;">
              ${status}
            </span>
          </div>

          <div style="margin:16px 0;">
            ${steps.map((s, idx) => `
              <div style="display:flex; gap:12px; margin-bottom:12px; align-items:flex-start;">
                <div style="width:24px; height:24px; border-radius:50%; background:${s.done ? '#176b3b' : '#ddd'}; color:#fff; display:grid; place-items:center; font-size:12px; font-weight:800;">
                  ${s.done ? '✓' : idx + 1}
                </div>
                <div>
                  <strong style="color:${s.done ? '#176b3b' : '#777'}; font-size:13.5px;">${s.label}</strong>
                  <div style="font-size:12px; color:var(--muted);">${s.desc}</div>
                </div>
              </div>
            `).join('')}
          </div>

          <p style="font-size:13px; border-top:1px solid #ebd9b8; padding-top:10px; margin-top:10px;">
            <b>Delivering to:</b> ${o.customer_name}, ${o.city}, ${o.state} (${o.pincode})
          </p>
        </div>
      `;
    } else {
      resultBox.innerHTML = `<p style="color:#c53030; margin-top:12px;">⚠️ ${data.error || 'Order not found.'}</p>`;
    }
  } catch (err) {
    resultBox.innerHTML = `<p style="color:#c53030; margin-top:12px;">⚠️ Network error searching order.</p>`;
  }
}

// ---------------- CONTACT FORM ---------------- //
async function submitContactForm(e) {
  e.preventDefault();
  const name = document.getElementById('contactName').value.trim();
  const phone = document.getElementById('contactPhone').value.trim();
  const email = document.getElementById('contactEmail').value.trim();
  const subject = document.getElementById('contactSubject').value;
  const message = document.getElementById('contactMessage').value.trim();

  const btn = document.getElementById('contactSubmitBtn');
  btn.disabled = true;
  btn.textContent = 'Sending Message...';

  try {
    const res = await fetch('/api/inquiry', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, phone, email, subject, message })
    });
    const data = await res.json();
    if (data.success) {
      alert('Thank you! Your message has been sent to our team. We will get in touch shortly.');
      document.getElementById('contactForm').reset();
    } else {
      alert('Failed: ' + (data.error || 'Please try again.'));
    }
  } catch (err) {
    alert('Network error. Please try again.');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Send Inquiry →';
  }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  renderProducts();
  updateCartBadge();
  checkAuthStatus();
  if (currentLang && currentLang !== 'en') {
    applyLanguage(currentLang);
  }

  document.getElementById('searchInput')?.addEventListener('input', renderProducts);
  document.getElementById('categoryFilter')?.addEventListener('change', renderProducts);
  document.getElementById('cartOpenBtn')?.addEventListener('click', openCart);

  document.getElementById('qvQtyMinus')?.addEventListener('click', () => {
    const input = document.getElementById('qvQtyInput');
    let val = parseInt(input.value) || 1;
    if (val > 1) input.value = val - 1;
  });
  document.getElementById('qvQtyPlus')?.addEventListener('click', () => {
    const input = document.getElementById('qvQtyInput');
    let val = parseInt(input.value) || 1;
    input.value = val + 1;
  });

  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        overlay.classList.remove('show');
      }
    });
  });
});
