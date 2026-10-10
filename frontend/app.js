// Telegram Mini App Controller
(function() {
  const tg = window.Telegram?.WebApp;

  function updateTheme() {
    let isDark = false;
    if (tg) {
      if (tg.colorScheme === 'dark') {
        isDark = true;
      } else if (tg.themeParams && tg.themeParams.bg_color) {
        const hex = tg.themeParams.bg_color.replace('#', '');
        if (hex.length === 6) {
          const r = parseInt(hex.substring(0, 2), 16);
          const g = parseInt(hex.substring(2, 4), 16);
          const b = parseInt(hex.substring(4, 6), 16);
          const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
          if (luminance < 0.5) isDark = true;
        }
      }
    }
    if (!isDark && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      isDark = true;
    }

    if (isDark) {
      document.body.classList.add('dark');
      document.body.classList.add('tg-dark');
    } else {
      document.body.classList.remove('dark');
      document.body.classList.remove('tg-dark');
    }
  }

  if (tg) {
    tg.ready();
    tg.expand();
    document.body.classList.add('tg-theme');
    tg.onEvent('themeChanged', updateTheme);
  }

  updateTheme();
  if (window.matchMedia) {
    try {
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', updateTheme);
    } catch (e) {
      // Older WebKit support
      window.matchMedia('(prefers-color-scheme: dark)').addListener(updateTheme);
    }
  }

  // State
  let currentBillId = null;
  let currentUser = {
    id: 10001,
    name: 'Андрей',
    username: 'andrey',
    is_nondrinker: false
  };
  let billData = null;
  let splitData = null;

  // DOM Elements
  const billTitleEl = document.getElementById('billTitle');
  const billMetaEl = document.getElementById('billMeta');
  const billTotalEl = document.getElementById('billTotal');
  const billStatusEl = document.getElementById('billStatus');
  const userAvatarEl = document.getElementById('userAvatar');
  const userNameEl = document.getElementById('userName');
  const toggleNondrinkerBtn = document.getElementById('toggleNondrinkerBtn');
  const participantsListEl = document.getElementById('participantsList');
  const itemsContainerEl = document.getElementById('itemsContainer');
  const itemsCountEl = document.getElementById('itemsCount');
  const myShareAmountEl = document.getElementById('myShareAmount');

  // Payer DOM
  const headerPayerNameEl = document.getElementById('headerPayerName');
  const headerPayerPhoneEl = document.getElementById('headerPayerPhone');
  const openChangePayerModalBtn = document.getElementById('openChangePayerModalBtn');
  const changePayerModal = document.getElementById('changePayerModal');
  const closeChangePayerModalBtn = document.getElementById('closeChangePayerModalBtn');
  const payerSelectEl = document.getElementById('payerSelect');
  const payerPhoneInputEl = document.getElementById('payerPhoneInput');
  const payerBankInputEl = document.getElementById('payerBankInput');
  const savePayerBtn = document.getElementById('savePayerBtn');

  // Edit Name DOM
  const openEditNameModalBtn = document.getElementById('openEditNameModalBtn');
  const editNameModal = document.getElementById('editNameModal');
  const closeEditNameModalBtn = document.getElementById('closeEditNameModalBtn');
  const editUserNameInput = document.getElementById('editUserNameInput');
  const saveEditNameBtn = document.getElementById('saveEditNameBtn');

  // Friends DOM
  const openAddFriendModalBtn = document.getElementById('openAddFriendModalBtn');
  const addFriendModal = document.getElementById('addFriendModal');
  const closeAddFriendModalBtn = document.getElementById('closeAddFriendModalBtn');
  const newFriendNameInput = document.getElementById('newFriendName');
  const newFriendNondrinkerInput = document.getElementById('newFriendNondrinker');
  const saveNewFriendBtn = document.getElementById('saveNewFriendBtn');
  const shareBillBtn = document.getElementById('shareBillBtn');

  // Items Modals
  const addItemModal = document.getElementById('addItemModal');
  const openAddItemModalBtn = document.getElementById('openAddItemModalBtn');
  const closeAddItemModalBtn = document.getElementById('closeAddItemModalBtn');
  const saveNewItemBtn = document.getElementById('saveNewItemBtn');

  // Settle Modal
  const settleModal = document.getElementById('settleModal');
  const openSettleModalBtn = document.getElementById('openSettleModalBtn');
  const closeSettleModalBtn = document.getElementById('closeSettleModalBtn');
  const closeSettleModalBottomBtn = document.getElementById('closeSettleModalBottomBtn');
  const sendToChatBtn = document.getElementById('sendToChatBtn');
  const settlePayerBox = document.getElementById('settlePayerBox');
  const sharesBreakdownList = document.getElementById('sharesBreakdownList');
  const transfersList = document.getElementById('transfersList');

  // Bills List & Banner DOM
  const newBillBanner = document.getElementById('newBillBanner');
  const newBillBannerInfo = document.getElementById('newBillBannerInfo');
  const switchToNewBillBtn = document.getElementById('switchToNewBillBtn');
  let latestDetectedBillId = null;

  const openBillsListBtn = document.getElementById('openBillsListBtn');
  const billsModal = document.getElementById('billsModal');
  const closeBillsModalBtn = document.getElementById('closeBillsModalBtn');
  const billsListContainer = document.getElementById('billsListContainer');
  const clearAllBillsBtn = document.getElementById('clearAllBillsBtn');
  const emptyState = document.getElementById('emptyState');
  const mainHeader = document.getElementById('mainHeader');
  const mainContent = document.querySelector('.main-content');
  const bottomBar = document.querySelector('.bottom-bar');
  const createDemoBillBtn = document.getElementById('createDemoBillBtn');

  // 1. Initialize User & Bill ID
  async function init() {
    // Determine Telegram User
    if (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) {
      const u = tg.initDataUnsafe.user;
      currentUser.id = u.id;
      currentUser.name = u.first_name + (u.last_name ? ' ' + u.last_name : '');
      currentUser.username = u.username || '';
    } else {
      const savedUser = localStorage.getItem('split_bill_user');
      if (savedUser) {
        try {
          currentUser = JSON.parse(savedUser);
        } catch(e) {}
      } else {
        const promptName = prompt('Введите ваше имя для разделения чека:', currentUser.name);
        if (promptName && promptName.trim()) {
          currentUser.name = promptName.trim();
          currentUser.id = Math.floor(10000 + Math.random() * 90000);
          localStorage.setItem('split_bill_user', JSON.stringify(currentUser));
        }
      }
    }

    // Determine Bill ID
    const urlParams = new URLSearchParams(window.location.search);
    const pathParts = window.location.pathname.split('/').filter(Boolean);

    if (urlParams.get('bill_id')) {
      currentBillId = urlParams.get('bill_id');
    } else if (tg?.initDataUnsafe?.start_param) {
      currentBillId = tg.initDataUnsafe.start_param;
    } else if (pathParts.length > 0 && pathParts[0] === 'bill' && pathParts[1]) {
      currentBillId = pathParts[1];
    } else {
      // Find latest bill or demo
      try {
        const latResp = await fetch(`/api/bill/latest?user_id=${currentUser.id}`);
        if (latResp.ok) {
          const latData = await latResp.json();
          currentBillId = latData.bill.id;
        } else {
          currentBillId = 'demo';
        }
      } catch (e) {
        currentBillId = 'demo';
      }
    }

    // Render User Header
    userNameEl.textContent = currentUser.name;
    userAvatarEl.textContent = currentUser.name.charAt(0).toUpperCase();

    // Setup Event Listeners
    setupEvents();

    // Join and Load Bill
    joinAndLoadBill();
  }

  // 2. Setup Events
  function setupEvents() {
    toggleNondrinkerBtn.addEventListener('click', toggleNondrinker);

    // Edit Name
    if (openEditNameModalBtn) {
      openEditNameModalBtn.addEventListener('click', openEditNameModal);
    }
    userNameEl.style.cursor = 'pointer';
    userNameEl.addEventListener('click', openEditNameModal);
    if (closeEditNameModalBtn) {
      closeEditNameModalBtn.addEventListener('click', () => {
        editNameModal.style.display = 'none';
      });
    }
    if (saveEditNameBtn) {
      saveEditNameBtn.addEventListener('click', saveEditName);
    }

    // Add Item
    openAddItemModalBtn.addEventListener('click', () => {
      addItemModal.style.display = 'flex';
    });
    closeAddItemModalBtn.addEventListener('click', () => {
      addItemModal.style.display = 'none';
    });
    saveNewItemBtn.addEventListener('click', saveNewItem);

    // Change Payer
    openChangePayerModalBtn.addEventListener('click', openChangePayerModal);
    closeChangePayerModalBtn.addEventListener('click', () => {
      changePayerModal.style.display = 'none';
    });
    savePayerBtn.addEventListener('click', savePayer);

    // Add Friend
    openAddFriendModalBtn.addEventListener('click', () => {
      addFriendModal.style.display = 'flex';
    });
    closeAddFriendModalBtn.addEventListener('click', () => {
      addFriendModal.style.display = 'none';
    });
    saveNewFriendBtn.addEventListener('click', saveNewFriend);

    // Share Bill
    shareBillBtn.addEventListener('click', shareBill);

    // Settlement
    openSettleModalBtn.addEventListener('click', openSettleModal);
    closeSettleModalBtn.addEventListener('click', () => {
      settleModal.style.display = 'none';
    });
    closeSettleModalBottomBtn.addEventListener('click', () => {
      settleModal.style.display = 'none';
    });

    sendToChatBtn.addEventListener('click', sendSettlementToChat);

    // Bills List & Banner
    if (switchToNewBillBtn) {
      switchToNewBillBtn.addEventListener('click', () => {
        if (latestDetectedBillId) {
          currentBillId = latestDetectedBillId;
          if (newBillBanner) newBillBanner.style.display = 'none';
          joinAndLoadBill();
        }
      });
    }

    if (openBillsListBtn) {
      openBillsListBtn.addEventListener('click', openBillsModal);
    }
    if (closeBillsModalBtn) {
      closeBillsModalBtn.addEventListener('click', () => {
        billsModal.style.display = 'none';
      });
    }

    if (clearAllBillsBtn) {
      clearAllBillsBtn.addEventListener('click', clearAllBills);
    }
    if (createDemoBillBtn) {
      createDemoBillBtn.addEventListener('click', createDemoBill);
    }
  }

  // 3. API: Join and Fetch
  async function joinAndLoadBill() {
    try {
      if (!currentBillId) {
        const latResp = await fetch(`/api/bill/latest?user_id=${currentUser.id}`);
        if (latResp.ok) {
          const latData = await latResp.json();
          if (latData.bill) {
            currentBillId = latData.bill.id;
            billData = latData.bill;
            splitData = latData.split;
          } else {
            billData = null;
            splitData = null;
          }
        } else {
          billData = null;
          splitData = null;
        }
        renderAll();
        return;
      }

      const joinResp = await fetch(`/api/bill/${currentBillId}/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: currentUser.id,
          name: currentUser.name,
          username: currentUser.username
        })
      });

      if (!joinResp.ok) {
        // Fallback to latest
        const fallbackResp = await fetch(`/api/bill/latest`);
        const fbData = await fallbackResp.json();
        if (fbData.bill) {
          currentBillId = fbData.bill.id;
          billData = fbData.bill;
          splitData = fbData.split;
        } else {
          billData = null;
          splitData = null;
        }
      } else {
        const data = await joinResp.json();
        if (data.empty || !data.bill) {
          billData = null;
          splitData = null;
        } else {
          billData = data.bill;
          splitData = data.split;
        }
      }

      renderAll();
    } catch (err) {
      console.error(err);
      billData = null;
      splitData = null;
      renderAll();
    }
  }

  // 4. Render All Components
  function renderAll() {
    if (!billData || !splitData) {
      if (emptyState) emptyState.style.display = 'flex';
      if (mainHeader) mainHeader.style.display = 'none';
      if (mainContent) mainContent.style.display = 'none';
      if (bottomBar) bottomBar.style.display = 'none';
      if (newBillBanner) newBillBanner.style.display = 'none';
      return;
    }

    if (emptyState) emptyState.style.display = 'none';
    if (mainHeader) mainHeader.style.display = 'flex';
    if (mainContent) mainContent.style.display = 'block';
    if (bottomBar) bottomBar.style.display = 'flex';

    // Header
    billTitleEl.textContent = billData.title || 'Общий чек';
    billMetaEl.textContent = `Создан: ${billData.created_at ? billData.created_at.slice(0, 16) : 'Недавно'}`;
    billTotalEl.textContent = `${parseFloat(billData.total_amount).toFixed(2)} ₽`;

    // Payer Header
    headerPayerNameEl.textContent = billData.payer_name || 'Не выбран';
    if (billData.payer_phone) {
      headerPayerPhoneEl.textContent = `(${billData.payer_phone})`;
    } else {
      headerPayerPhoneEl.textContent = '';
    }

    // My Non-drinker status
    const currentPart = billData.participants.find(p => p.user_id === currentUser.id);
    if (currentPart) {
      currentUser.is_nondrinker = Boolean(currentPart.is_nondrinker);
      if (currentUser.is_nondrinker) {
        toggleNondrinkerBtn.classList.add('active');
        toggleNondrinkerBtn.querySelector('.toggle-text').textContent = 'Не пью (активно)';
      } else {
        toggleNondrinkerBtn.classList.remove('active');
        toggleNondrinkerBtn.querySelector('.toggle-text').textContent = 'Я не пью';
      }
    }

    // Participants
    renderParticipants();

    // Items
    renderItems();

    // My Share in Bottom Bar
    const myShare = splitData.participants.find(p => p.user_id === currentUser.id);
    const amount = myShare ? myShare.total_consumed : 0.0;
    myShareAmountEl.textContent = `${amount.toFixed(2)} ₽`;
  }

  function renderParticipants() {
    participantsListEl.innerHTML = '';
    billData.participants.forEach(p => {
      const chip = document.createElement('div');
      const isMe = p.user_id === currentUser.id;
      const isPayer = p.user_id === billData.payer_user_id;
      chip.className = `chip ${isMe ? 'current-user' : ''}`;
      
      let icon = p.is_nondrinker ? '🥤' : '🍺';
      if (isPayer) icon = '👑';

      chip.innerHTML = `<span>${icon}</span> <span>${escapeHtml(p.name)}</span>`;
      participantsListEl.appendChild(chip);
    });
  }

  function renderItems() {
    itemsCountEl.textContent = `${billData.items.length} поз.`;
    itemsContainerEl.innerHTML = '';

    if (billData.items.length === 0) {
      itemsContainerEl.innerHTML = `
        <div style="background:#fff; border:1px solid var(--border-color); border-radius:12px; padding:20px; text-align:center;">
          <p style="font-size:14px; font-weight:600; margin-bottom:6px;">Чек на сумму ${parseFloat(billData.total_amount).toFixed(2)} ₽</p>
          <p style="font-size:12px; color:var(--text-muted); margin-bottom:14px;">Позиции еще не добавлены. Вы можете добавить алкоголь, общак или покупки по кнопке ниже.</p>
          <button class="btn btn-primary" onclick="document.getElementById('openAddItemModalBtn').click()" style="padding:8px 14px; font-size:13px;">➕ Добавить первую позицию</button>
        </div>
      `;
      return;
    }

    const participantsMap = {};
    billData.participants.forEach(p => { participantsMap[p.user_id] = p; });

    billData.items.forEach(item => {
      const card = document.createElement('div');
      const isAlco = Boolean(item.is_alcohol || item.category === 'alcohol');
      const claimedBy = item.claimed_by || [];
      const isClaimedByMe = claimedBy.includes(currentUser.id);

      card.className = `item-card ${isClaimedByMe ? 'claimed-by-me' : ''} ${isAlco ? 'is-alcohol' : ''}`;

      // Badge
      let badgeHtml = '';
      if (isAlco) {
        badgeHtml = '<span class="category-badge badge-alcohol">🍺 Алкоголь</span>';
      } else if (item.category === 'personal') {
        badgeHtml = '<span class="category-badge badge-personal">👤 Личное</span>';
      } else {
        badgeHtml = '<span class="category-badge badge-shared">🛒 Общак</span>';
      }

      // Quantity info
      const qtyText = item.quantity > 1 ? `${item.quantity} шт × ${item.price.toFixed(2)} ₽` : '';

      // Split hint
      let splitHint = '';
      if (claimedBy.length > 0) {
        const perPerson = (item.total_price / claimedBy.length).toFixed(2);
        splitHint = `по ${perPerson} ₽ (${claimedBy.length} чел.)`;
      } else {
        splitHint = isAlco ? 'Делят все пьющие' : 'Делят все участники';
      }

      // Claimers badges
      let claimersHtml = '';
      if (claimedBy.length > 0) {
        claimedBy.forEach(uId => {
          const p = participantsMap[uId];
          const name = p ? p.name : 'Участник';
          const isMe = uId === currentUser.id;
          claimersHtml += `<span class="claimer-tag ${isMe ? 'is-me' : ''}">${escapeHtml(name)}</span>`;
        });
      } else {
        claimersHtml = `<span style="font-size: 11px; color: var(--text-muted);">Общак</span>`;
      }

      // Claim button status
      const btnText = isClaimedByMe ? '✓ Я скидываюсь' : '🎯 Я скидываюсь';

      card.innerHTML = `
        <div class="item-header">
          <div class="item-title-col">
            ${badgeHtml}
            <div class="item-name">${escapeHtml(item.name)}</div>
            ${qtyText ? `<div class="item-subtext">${qtyText}</div>` : ''}
          </div>
          <div class="item-price-col">
            <div class="item-price">${parseFloat(item.total_price).toFixed(2)} ₽</div>
            <div class="item-split-hint">${splitHint}</div>
          </div>
        </div>
        <div class="item-footer">
          <div class="claimers-list">${claimersHtml}</div>
          <button class="claim-btn ${isClaimedByMe ? 'claimed' : ''}" data-item-id="${item.id}">
            ${btnText}
          </button>
        </div>
      `;

      // Click event for claim button
      const claimBtn = card.querySelector('.claim-btn');
      claimBtn.addEventListener('click', () => toggleClaim(item.id));

      itemsContainerEl.appendChild(card);
    });
  }

  // 5. Actions
  async function toggleClaim(itemId) {
    if (tg?.HapticFeedback) {
      tg.HapticFeedback.impactOccurred('light');
    }

    try {
      const resp = await fetch(`/api/bill/${currentBillId}/claim`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          item_id: itemId,
          user_id: currentUser.id
        })
      });
      if (resp.ok) {
        const data = await resp.json();
        billData = data.bill;
        splitData = data.split;
        renderAll();
      }
    } catch (err) {
      console.error('Claim toggle error:', err);
    }
  }

  async function toggleNondrinker() {
    if (tg?.HapticFeedback) {
      tg.HapticFeedback.impactOccurred('medium');
    }

    try {
      const resp = await fetch(`/api/bill/${currentBillId}/toggle_nondrinker`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: currentUser.id })
      });
      if (resp.ok) {
        const data = await resp.json();
        billData = data.bill;
        splitData = data.split;
        renderAll();
      }
    } catch (err) {
      console.error('Nondrinker toggle error:', err);
    }
  }

  // Edit My Name
  function openEditNameModal() {
    if (editUserNameInput) {
      editUserNameInput.value = currentUser.name;
    }
    if (editNameModal) {
      editNameModal.style.display = 'flex';
      setTimeout(() => {
        if (editUserNameInput) editUserNameInput.focus();
      }, 100);
    }
  }

  async function saveEditName() {
    const newName = editUserNameInput ? editUserNameInput.value.trim() : '';
    if (!newName) {
      alert('Пожалуйста, укажите ваше имя');
      return;
    }

    currentUser.name = newName;
    localStorage.setItem('split_bill_user', JSON.stringify(currentUser));
    userNameEl.textContent = currentUser.name;
    userAvatarEl.textContent = currentUser.name.charAt(0).toUpperCase();

    try {
      const resp = await fetch(`/api/bill/${currentBillId}/update_name`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: currentUser.id,
          name: newName
        })
      });

      if (resp.ok) {
        const data = await resp.json();
        billData = data.bill;
        splitData = data.split;
        renderAll();
      }
    } catch (err) {
      console.error('Update name error:', err);
    }

    if (editNameModal) {
      editNameModal.style.display = 'none';
    }
  }

  // Bills List Modal
  async function openBillsModal() {
    if (!billsListContainer) return;
    billsListContainer.innerHTML = '<p style="text-align:center; padding:15px; color:var(--text-muted); font-size:13px;">Загрузка списка чеков...</p>';
    if (billsModal) billsModal.style.display = 'flex';

    try {
      const resp = await fetch(`/api/bills?user_id=${currentUser.id}`);
      if (!resp.ok) throw new Error('Не удалось загрузить чеки');
      const data = await resp.json();
      renderBillsList(data.bills);
    } catch (err) {
      billsListContainer.innerHTML = `<p style="color:var(--danger); text-align:center; font-size:13px;">${err.message}</p>`;
    }
  }

  function renderBillsList(bills) {
    if (!billsListContainer) return;
    billsListContainer.innerHTML = '';
    if (!bills || bills.length === 0) {
      billsListContainer.innerHTML = '<p style="text-align:center; padding:15px; color:var(--text-muted); font-size:13px;">Чеков пока нет.</p>';
      return;
    }

    bills.forEach(b => {
      const card = document.createElement('div');
      const isCurrent = b.id === currentBillId;
      card.className = `bill-item-card ${isCurrent ? 'active' : ''}`;

      const dateStr = b.created_at ? b.created_at.slice(5, 16) : '';
      const itemsCount = b.items_count || 0;

      card.innerHTML = `
        <div style="flex:1; padding-right:10px;">
          <div class="bill-item-title">${escapeHtml(b.title)}</div>
          <div class="bill-item-sub">
            ${itemsCount} поз. • ${dateStr} • Оплатил: ${escapeHtml(b.payer_name)}
          </div>
          ${isCurrent ? '<span class="bill-item-badge">✓ Текущий чек</span>' : ''}
        </div>
        <div style="display:flex; align-items:center; gap:8px;">
          <div class="bill-item-total">
            ${parseFloat(b.total_amount).toFixed(2)} ₽
          </div>
          <button class="bill-delete-btn" title="Удалить этот чек" data-bill-id="${b.id}">🗑</button>
        </div>
      `;

      card.addEventListener('click', (e) => {
        if (e.target.closest('.bill-delete-btn')) return;
        currentBillId = b.id;
        if (billsModal) billsModal.style.display = 'none';
        if (newBillBanner) newBillBanner.style.display = 'none';
        joinAndLoadBill();
      });

      const delBtn = card.querySelector('.bill-delete-btn');
      if (delBtn) {
        delBtn.addEventListener('click', (e) => deleteSingleBill(b.id, e));
      }

      billsListContainer.appendChild(card);
    });
  }

  async function clearAllBills() {
    if (!confirm('Вы точно хотите удалить ВСЕ чеки? Это действие нельзя отменить.')) {
      return;
    }

    try {
      const resp = await fetch('/api/bills/clear', { method: 'POST' });
      if (resp.ok) {
        billData = null;
        splitData = null;
        currentBillId = null;
        latestDetectedBillId = null;
        if (billsModal) billsModal.style.display = 'none';
        if (newBillBanner) newBillBanner.style.display = 'none';
        renderAll();
      }
    } catch (err) {
      alert('Ошибка при очистке чеков: ' + err.message);
    }
  }

  async function deleteSingleBill(billId, event) {
    if (event) event.stopPropagation();
    if (!confirm('Удалить этот чек из списка?')) return;

    try {
      const resp = await fetch(`/api/bill/${billId}/delete`, { method: 'POST' });
      if (resp.ok) {
        const data = await resp.json();
        if (currentBillId === billId) {
          if (data.latest_bill_id) {
            currentBillId = data.latest_bill_id;
            joinAndLoadBill();
          } else {
            billData = null;
            splitData = null;
            currentBillId = null;
            renderAll();
          }
        }
        openBillsModal(); // refresh list in modal
      }
    } catch (err) {
      alert('Ошибка при удалении чека: ' + err.message);
    }
  }

  async function createDemoBill() {
    try {
      const resp = await fetch('/api/bill/demo/create', { method: 'POST' });
      if (resp.ok) {
        const data = await resp.json();
        currentBillId = data.bill.id;
        billData = data.bill;
        splitData = data.split;
        renderAll();
      }
    } catch (err) {
      alert('Ошибка создания демо-чека: ' + err.message);
    }
  }

  // Change Payer
  function openChangePayerModal() {
    if (!billData) return;

    payerSelectEl.innerHTML = '';
    billData.participants.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.user_id;
      opt.textContent = p.name + (p.user_id === currentUser.id ? ' (Вы)' : '');
      if (p.user_id === billData.payer_user_id) {
        opt.selected = true;
      }
      payerSelectEl.appendChild(opt);
    });

    payerPhoneInputEl.value = billData.payer_phone || '';
    payerBankInputEl.value = billData.payer_bank || '';
    changePayerModal.style.display = 'flex';
  }

  async function savePayer() {
    const selectedUserId = parseInt(payerSelectEl.value);
    const selectedPart = billData.participants.find(p => p.user_id === selectedUserId);
    const payerName = selectedPart ? selectedPart.name : currentUser.name;
    const phone = payerPhoneInputEl.value.trim();
    const bank = payerBankInputEl.value.trim();

    try {
      const resp = await fetch(`/api/bill/${currentBillId}/set_payer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          payer_user_id: selectedUserId,
          payer_name: payerName,
          payer_phone: phone,
          payer_bank: bank
        })
      });

      if (resp.ok) {
        const data = await resp.json();
        billData = data.bill;
        splitData = data.split;
        renderAll();
        changePayerModal.style.display = 'none';
      }
    } catch (err) {
      alert('Ошибка при сохранении плательщика: ' + err.message);
    }
  }

  // Add Manual Friend
  async function saveNewFriend() {
    const name = newFriendNameInput.value.trim();
    const isNondrinker = newFriendNondrinkerInput.checked;

    if (!name) {
      alert('Укажите имя друга');
      return;
    }

    try {
      const resp = await fetch(`/api/bill/${currentBillId}/add_participant`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name,
          is_nondrinker: isNondrinker
        })
      });

      if (resp.ok) {
        const data = await resp.json();
        billData = data.bill;
        splitData = data.split;
        renderAll();

        newFriendNameInput.value = '';
        newFriendNondrinkerInput.checked = false;
        addFriendModal.style.display = 'none';
      }
    } catch (err) {
      alert('Ошибка при добавлении друга: ' + err.message);
    }
  }

  // Share Bill Link
  function shareBill() {
    const tgBotLink = `https://t.me/warok18bot?start=${currentBillId}`;
    const shareText = `Ребята, вот наш чек «${billData?.title || 'Закупка'}» на ${parseFloat(billData?.total_amount || 0).toFixed(2)} ₽! Заходите, вводите свои имена и отмечайте свои позиции:`;
    
    if (tg?.openTelegramLink) {
      const tgShareUrl = `https://t.me/share/url?url=${encodeURIComponent(tgBotLink)}&text=${encodeURIComponent(shareText)}`;
      tg.openTelegramLink(tgShareUrl);
    } else if (navigator.clipboard) {
      navigator.clipboard.writeText(`${shareText}\n${tgBotLink}`);
      alert('Ссылка на чек скопирована! Отправьте её друзьям в чат.');
    } else {
      prompt('Скопируйте ссылку для друзей:', tgBotLink);
    }
  }

  async function saveNewItem() {
    const nameInput = document.getElementById('newItemName');
    const priceInput = document.getElementById('newItemPrice');
    const qtyInput = document.getElementById('newItemQty');
    const catInput = document.getElementById('newItemCategory');

    const name = nameInput.value.trim();
    const price = parseFloat(priceInput.value);
    const qty = parseFloat(qtyInput.value) || 1.0;
    const category = catInput.value;

    if (!name || isNaN(price) || price <= 0) {
      alert('Пожалуйста, укажите корректное название и цену товара');
      return;
    }

    try {
      const resp = await fetch(`/api/bill/${currentBillId}/add_item`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name,
          price: price,
          quantity: qty,
          category: category
        })
      });

      if (resp.ok) {
        const data = await resp.json();
        billData = data.bill;
        splitData = data.split;
        renderAll();

        // Reset & Close
        nameInput.value = '';
        priceInput.value = '';
        qtyInput.value = '1';
        addItemModal.style.display = 'none';
      }
    } catch (err) {
      alert('Ошибка при добавлении товара: ' + err.message);
    }
  }

  function openSettleModal() {
    if (!splitData) return;

    // Payer info
    settlePayerBox.innerHTML = `
      <div>👑 <strong>Оплатил(а):</strong> ${escapeHtml(splitData.payer_name)} на сумму <strong>${splitData.total_amount.toFixed(2)} ₽</strong></div>
      ${splitData.payer_phone ? `<div style="margin-top:4px;">📲 СБП: <code>${splitData.payer_phone}</code> (${splitData.payer_bank || 'Банк'})</div>` : ''}
    `;

    // Breakdown
    sharesBreakdownList.innerHTML = '';
    splitData.participants.forEach(p => {
      const row = document.createElement('div');
      row.className = 'share-row';
      const alcoIcon = p.is_nondrinker ? '🥤 Без алко' : '';
      row.innerHTML = `
        <div>
          <strong>${escapeHtml(p.name)}</strong>
          ${alcoIcon ? `<span style="font-size:11px; color:var(--text-muted); margin-left:4px;">${alcoIcon}</span>` : ''}
        </div>
        <div><strong>${p.total_consumed.toFixed(2)} ₽</strong></div>
      `;
      sharesBreakdownList.appendChild(row);
    });

    // Transfers
    transfersList.innerHTML = '';
    if (splitData.transfers.length === 0) {
      transfersList.innerHTML = '<div style="padding:10px; color:var(--text-muted); font-size:13px;">Никто никому не должен.</div>';
    } else {
      splitData.transfers.forEach(t => {
        const row = document.createElement('div');
        row.className = 'transfer-row';
        row.innerHTML = `
          <div><strong>${escapeHtml(t.from_name)}</strong> ➔ ${escapeHtml(t.to_name)}</div>
          <div><strong style="color:var(--primary);">${t.amount.toFixed(2)} ₽</strong></div>
        `;
        transfersList.appendChild(row);
      });
    }

    settleModal.style.display = 'flex';
  }

  async function sendSettlementToChat() {
    sendToChatBtn.disabled = true;
    sendToChatBtn.textContent = 'Отправка...';

    try {
      const resp = await fetch(`/api/bill/${currentBillId}/notify_chat`, {
        method: 'POST'
      });
      const res = await resp.json();
      if (res.ok) {
        alert('Расчёт успешно отправлен в Telegram чат!');
        if (tg) {
          tg.close();
        }
      } else {
        alert('Сообщение отправлено или чат ожидает команду бота.');
      }
    } catch (err) {
      alert('Ошибка отправки: ' + err.message);
    } finally {
      sendToChatBtn.disabled = false;
      sendToChatBtn.textContent = '📢 Отправить расчет в чат Telegram';
    }
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  // Background live sync (polls every 3.5s so all friends see updates in real-time)
  setInterval(async () => {
    if (!currentBillId || document.hidden) return;

    // Do not re-render if user is typing or modal is open
    const modals = [addItemModal, addFriendModal, changePayerModal, settleModal, editNameModal];
    const isModalOpen = modals.some(m => m && m.style.display === 'flex');
    const isTyping = document.activeElement && (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA');

    if (isModalOpen || isTyping) return;

    try {
      // 1. Check if a newer bill was created in the background
      const latestResp = await fetch(`/api/bill/latest?user_id=${currentUser.id}`);
      if (latestResp.ok) {
        const latestData = await latestResp.json();
        if (latestData.bill && latestData.bill.id !== currentBillId) {
          latestDetectedBillId = latestData.bill.id;
          if (newBillBanner && newBillBannerInfo) {
            newBillBannerInfo.textContent = `${latestData.bill.title} (${parseFloat(latestData.bill.total_amount).toFixed(2)} ₽)`;
            newBillBanner.style.display = 'flex';
          }
        } else if (newBillBanner && !latestDetectedBillId) {
          newBillBanner.style.display = 'none';
        }
      }

      // 2. Sync current bill data
      const resp = await fetch(`/api/bill/${currentBillId}`);
      if (resp.ok) {
        const data = await resp.json();
        const currentP = JSON.stringify(billData?.participants?.map(p => ({ id: p.user_id, n: p.name, nd: p.is_nondrinker })));
        const newP = JSON.stringify(data.bill?.participants?.map(p => ({ id: p.user_id, n: p.name, nd: p.is_nondrinker })));

        const currentC = JSON.stringify(billData?.items?.map(it => it.claimed_by));
        const newC = JSON.stringify(data.bill?.items?.map(it => it.claimed_by));

        const currentItemsCount = billData?.items?.length || 0;
        const newItemsCount = data.bill?.items?.length || 0;

        if (currentP !== newP || currentC !== newC || currentItemsCount !== newItemsCount || billData?.payer_user_id !== data.bill?.payer_user_id) {
          billData = data.bill;
          splitData = data.split;
          renderAll();
        }
      }
    } catch (e) {
      // ignore network blips during polling
    }
  }, 3500);

  // Start
  init();
})();
