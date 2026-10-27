/**
 * Sri Dhanam Motors - Shared Billing Logic
 * Handles Spare Bill, Service Bill, and Vehicle Bill
 */

let availableProducts = [];
let cartItems = [];
let isBuyerTypeLocked = false;
let lockedBuyerType = "Customer";

document.addEventListener("DOMContentLoaded", () => {
    if (window.BILL_CATEGORY === "Spare Parts") {
        activeBillingCategory = "Spare Parts";
    }
    loadProducts();
});

function getVehicleMarginPercent() {
    if (!window.IS_VEHICLE_PAGE) return null;
    const marginInput = document.getElementById("vehicle-profit-margin");
    if (!marginInput) return 0.0;
    const raw = marginInput.value.trim();
    if (raw === "") return 0.0;
    const val = parseFloat(raw);
    return isNaN(val) ? 0.0 : val;
}

let vehicleMarginDebounceTimer = null;
function onVehicleProfitMarginChanged(val) {
    clearTimeout(vehicleMarginDebounceTimer);
    vehicleMarginDebounceTimer = setTimeout(() => {
        loadProducts();
        if (cartItems.length > 0) {
            recalculateCart();
        }
    }, 250);
}

function setVehicleMarginPreset(pct) {
    const marginInput = document.getElementById("vehicle-profit-margin");
    if (marginInput) {
        marginInput.value = pct;
        onVehicleProfitMarginChanged(pct);
    }
}

function updateMarginPresetButtons(margin) {
    // Presets removed, kept as no-op for backward compatibility
}

let activeFilterTab = "all";
let activeBillingCategory = "All";

function setBillingCategoryFilter(cat, btn) {
    activeBillingCategory = cat;
    document.querySelectorAll(".catalog-category-pills-bar .filter-pill").forEach(p => p.classList.remove("active"));
    if (btn) {
        btn.classList.add("active");
    } else {
        const matchingBtn = document.querySelector(`.catalog-category-pills-bar .filter-pill[data-cat="${cat}"]`);
        if (matchingBtn) matchingBtn.classList.add("active");
    }
    renderCatalogTable();
}

function updateCategoryCounts() {
    const allCount = availableProducts.length;
    const spareCount = availableProducts.filter(p => p.category === "Spare Parts").length;
    const serviceCount = availableProducts.filter(p => p.category === "Service").length;
    const vehicleCount = availableProducts.filter(p => p.category === "Vehicle Sales").length;

    const elAll = document.getElementById("count-cat-all");
    if (elAll) elAll.textContent = allCount;
    const elSpare = document.getElementById("count-cat-spare");
    if (elSpare) elSpare.textContent = spareCount;
    const elService = document.getElementById("count-cat-service");
    if (elService) elService.textContent = serviceCount;
    const elVehicle = document.getElementById("count-cat-vehicle");
    if (elVehicle) elVehicle.textContent = vehicleCount;
}

function getCategoryBadgeHtml(cat) {
    if (cat === "Spare Parts") {
        return `<span class="badge-cat badge-cat-spare" title="Spare Parts">🔩 Spare</span>`;
    } else if (cat === "Service") {
        return `<span class="badge-cat badge-cat-service" title="Service">🔧 Service</span>`;
    } else if (cat === "Vehicle Sales") {
        return `<span class="badge-cat badge-cat-vehicle" title="Vehicle Sales">🛵 Vehicle</span>`;
    }
    return cat ? `<span class="badge-cat">${cat}</span>` : "";
}

async function loadProducts(vehicleTypeFilter = null) {
    const buyerType = getSelectedBuyerType();
    const billCat = window.BILL_CATEGORY || "Spare Parts";

    let url = `/api/billing/products?category=All&buyer_type=${encodeURIComponent(buyerType)}&bill_category=${encodeURIComponent(billCat)}`;
    if (vehicleTypeFilter && vehicleTypeFilter !== "All") {
        url += `&vehicle_type=${encodeURIComponent(vehicleTypeFilter)}`;
    }
    if (window.IS_VEHICLE_PAGE) {
        const margin = getVehicleMarginPercent();
        if (margin !== null) {
            url += `&margin_percent=${encodeURIComponent(margin)}`;
        }
    }

    try {
        const res = await fetch(url);
        let products = await res.json();

        // Enforce section filtering rules on client:
        // 1. Spare Bill: no Service, no Vehicle Sales (only Spare Parts)
        // 2. Service Bill: no Vehicle Sales (Service + Spare Parts)
        // 3. Vehicle Bill: no Service (Vehicle Sales + Spare Parts)
        if (billCat === "Spare Parts") {
            products = products.filter(p => p.category === "Spare Parts");
        } else if (billCat === "Service") {
            products = products.filter(p => p.category !== "Vehicle Sales");
        } else if (billCat === "Vehicle Sales" || window.IS_VEHICLE_PAGE) {
            products = products.filter(p => p.category !== "Service");
        }

        availableProducts = products;
        updateCategoryCounts();
        renderCatalogTable();
    } catch (e) {
        showToast("Error loading products catalog: " + e.message, "error");
    }
}

function setProductFilter(tab) {
    activeFilterTab = tab;
    const tabAll = document.getElementById("tab-filter-all");
    const tabTicked = document.getElementById("tab-filter-ticked");
    if (tabAll && tabTicked) {
        if (tab === "all") {
            tabAll.classList.add("active");
            tabTicked.classList.remove("active");
        } else {
            tabAll.classList.remove("active");
            tabTicked.classList.add("active");
        }
    }
    renderCatalogTable();
}

function onSearchInput(val) {
    const clearBtn = document.getElementById("search-clear");
    if (clearBtn) {
        clearBtn.style.display = val.trim().length > 0 ? "block" : "none";
    }
    renderCatalogTable();
}

function clearCatalogSearch() {
    const searchInput = document.getElementById("catalog-search");
    if (searchInput) {
        searchInput.value = "";
    }
    const clearBtn = document.getElementById("search-clear");
    if (clearBtn) {
        clearBtn.style.display = "none";
    }
    renderCatalogTable();
}

function renderCatalogTable() {
    const tbody = document.getElementById("catalog-tbody");
    if (!tbody) return;

    const searchInput = document.getElementById("catalog-search");
    const searchTerm = (searchInput ? searchInput.value : "").trim().toLowerCase();
    const isVeh = window.IS_VEHICLE_PAGE;

    // Update badges
    const allCountElem = document.getElementById("all-products-count");
    if (allCountElem) allCountElem.textContent = availableProducts.length;

    const tickedCountElem = document.getElementById("ticked-products-count");
    if (tickedCountElem) tickedCountElem.textContent = cartItems.length;

    const badgeTextElem = document.getElementById("selected-items-badge-text");
    if (badgeTextElem) {
        badgeTextElem.textContent = `${cartItems.length} items ticked`;
    }

    // Filter products
    const filtered = availableProducts.filter(p => {
        const isTicked = cartItems.some(item => item.part_no === p.part_no);
        if (activeFilterTab === "ticked" && !isTicked) {
            return false;
        }

        // Category filter
        if (activeBillingCategory !== "All") {
            if (p.category !== activeBillingCategory) return false;
        }

        if (searchTerm) {
            const matchPart = (p.part_no || "").toLowerCase().includes(searchTerm);
            const matchName = (p.name || "").toLowerCase().includes(searchTerm);
            const matchCat = (p.category || "").toLowerCase().includes(searchTerm);
            if (!matchPart && !matchName && !matchCat) {
                return false;
            }
        }

        return true;
    });

    if (filtered.length === 0) {
        const msg = activeFilterTab === "ticked"
            ? "No items ticked in bill yet. Switch to 'All' and tick items to add."
            : (searchTerm ? `No matches found for "${searchTerm}".` : "No products available in this category.");
        tbody.innerHTML = `<tr><td colspan="${isVeh ? 6 : 7}" class="text-center text-muted" style="padding: 24px;">${msg}</td></tr>`;
        return;
    }

    tbody.innerHTML = "";
    filtered.forEach(p => {
        const isTicked = cartItems.some(i => i.part_no === p.part_no);
        const cartItem = cartItems.find(i => i.part_no === p.part_no);
        const currentQty = isTicked ? cartItem.qty : 1;
        const isOutOfStock = p.stock_qty <= 0;

        let stockBadgeHtml = "";
        if (isOutOfStock) {
            stockBadgeHtml = `<span class="badge-stock badge-out-stock">Out of Stock</span>`;
        } else if (p.stock_qty <= 3) {
            stockBadgeHtml = `<span class="badge-stock badge-low-stock">${p.stock_qty} (Low)</span>`;
        } else {
            stockBadgeHtml = `<span class="badge-stock badge-in-stock">${p.stock_qty} in stock</span>`;
        }

        const lineTotalText = isTicked ? formatINR(p.selling_price * currentQty) : "—";

        const tr = document.createElement("tr");
        if (isTicked) tr.classList.add("row-ticked");
        if (isOutOfStock) tr.classList.add("row-out-of-stock");

        tr.onclick = (e) => onRowClicked(p.part_no, e);

        if (isVeh) {
            tr.innerHTML = `
                <td class="tick-box-cell" onclick="event.stopPropagation()">
                    <input type="checkbox" class="tick-case" id="tick-${p.part_no}" 
                        ${isTicked ? "checked" : ""} 
                        ${isOutOfStock ? "disabled" : ""} 
                        onchange="onToggleTick('${p.part_no}', this.checked)"
                        title="${isOutOfStock ? 'Out of stock' : 'Tick to add to bill'}">
                </td>
                <td>
                    <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
                        <strong style="font-size: 1.05rem;">${p.name}</strong>
                        ${getCategoryBadgeHtml(p.category)}
                    </div>
                    ${p.part_no && p.part_no !== p.name ? `<div style="font-size: 11px; color: #64748b; margin-top: 2px;">${p.part_no} | GST: ${p.gst_percent}%</div>` : ""}
                </td>
                <td class="text-center">${stockBadgeHtml}</td>
                <td class="text-right">${formatINR(p.selling_price)}</td>
                <td class="text-center" onclick="event.stopPropagation()">
                    <div class="qty-stepper ${!isTicked ? 'disabled' : ''}">
                        <button type="button" class="btn-qty" onclick="stepQty('${p.part_no}', -1)" ${!isTicked || currentQty <= 1 ? "disabled" : ""}>-</button>
                        <input type="number" class="input-qty" id="qty-input-${p.part_no}" value="${currentQty}" min="1" max="${p.stock_qty}" ${!isTicked ? "disabled" : ""} onchange="onQtyInputChange('${p.part_no}', this.value)">
                        <button type="button" class="btn-qty" onclick="stepQty('${p.part_no}', 1)" ${!isTicked || currentQty >= p.stock_qty ? "disabled" : ""}>+</button>
                    </div>
                </td>
                <td class="text-right" style="font-weight: 700; color: ${isTicked ? 'var(--brand-green)' : 'inherit'};">${lineTotalText}</td>
            `;
        } else {
            tr.innerHTML = `
                <td class="tick-box-cell" onclick="event.stopPropagation()">
                    <input type="checkbox" class="tick-case" id="tick-${p.part_no}" 
                        ${isTicked ? "checked" : ""} 
                        ${isOutOfStock ? "disabled" : ""} 
                        onchange="onToggleTick('${p.part_no}', this.checked)"
                        title="${isOutOfStock ? 'Out of stock' : 'Tick to add to bill'}">
                </td>
                <td><strong style="color: #1e293b;">${p.part_no}</strong></td>
                <td>
                    <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
                        <strong>${p.name}</strong>
                        ${getCategoryBadgeHtml(p.category)}
                    </div>
                    ${p.hsn ? `<div style="font-size: 11px; color: #64748b; margin-top: 2px;">HSN: ${p.hsn} | GST: ${p.gst_percent}%</div>` : `<div style="font-size: 11px; color: #64748b; margin-top: 2px;">GST: ${p.gst_percent}%</div>`}
                </td>
                <td class="text-center">${stockBadgeHtml}</td>
                <td class="text-right">${formatINR(p.selling_price)}</td>
                <td class="text-center" onclick="event.stopPropagation()">
                    <div class="qty-stepper ${!isTicked ? 'disabled' : ''}">
                        <button type="button" class="btn-qty" onclick="stepQty('${p.part_no}', -1)" ${!isTicked || currentQty <= 1 ? "disabled" : ""}>-</button>
                        <input type="number" class="input-qty" id="qty-input-${p.part_no}" value="${currentQty}" min="1" max="${p.stock_qty}" ${!isTicked ? "disabled" : ""} onchange="onQtyInputChange('${p.part_no}', this.value)">
                        <button type="button" class="btn-qty" onclick="stepQty('${p.part_no}', 1)" ${!isTicked || currentQty >= p.stock_qty ? "disabled" : ""}>+</button>
                    </div>
                </td>
                <td class="text-right" style="font-weight: 700; color: ${isTicked ? 'var(--brand-green)' : 'inherit'};">${lineTotalText}</td>
            `;
        }

        tbody.appendChild(tr);
    });
}

function onRowClicked(partNo, evt) {
    if (evt.target.tagName === "INPUT" || evt.target.tagName === "BUTTON") {
        return;
    }
    const prod = availableProducts.find(p => p.part_no === partNo);
    if (!prod || prod.stock_qty <= 0) return;

    const isTicked = cartItems.some(i => i.part_no === partNo);
    onToggleTick(partNo, !isTicked);
}

function onToggleTick(partNo, isChecked) {
    const prod = availableProducts.find(p => p.part_no === partNo);
    if (!prod) return;

    if (isChecked) {
        const billCat = window.BILL_CATEGORY || "Spare Parts";
        if (billCat === "Spare Parts" && prod.category !== "Spare Parts") {
            showToast("Spare bills can only contain Spare Parts.", "error");
            renderCatalogTable();
            return;
        }
        if (billCat === "Service" && prod.category === "Vehicle Sales") {
            showToast("Service bills cannot contain Vehicle Sales items.", "error");
            renderCatalogTable();
            return;
        }
        if ((billCat === "Vehicle Sales" || window.IS_VEHICLE_PAGE) && prod.category === "Service") {
            showToast("Vehicle bills cannot contain Service items.", "error");
            renderCatalogTable();
            return;
        }

        if (prod.stock_qty <= 0) {
            showToast(`'${prod.name}' is OUT OF STOCK!`, "error");
            renderCatalogTable();
            return;
        }

        if (!cartItems.some(i => i.part_no === partNo)) {
            cartItems.push({
                part_no: prod.part_no,
                product_name: prod.name,
                cost_price: prod.cost_price,
                gst_percent: prod.gst_percent,
                category: prod.category || "",
                vehicle_type: prod.vehicle_type || "",
                qty: 1
            });
            showToast(`Added '${prod.name}' to bill`, "success");
        }

        if (!isBuyerTypeLocked) {
            lockBuyerType();
        }
    } else {
        const idx = cartItems.findIndex(i => i.part_no === partNo);
        if (idx > -1) {
            cartItems.splice(idx, 1);
            showToast(`Removed '${prod.name}' from bill`, "info");
        }

        if (cartItems.length === 0) {
            unlockBuyerType();
        }
    }

    renderCatalogTable();
    recalculateCart();
}

function stepQty(partNo, delta) {
    const prod = availableProducts.find(p => p.part_no === partNo);
    const cartItem = cartItems.find(i => i.part_no === partNo);
    if (!prod || !cartItem) return;

    let newQty = cartItem.qty + delta;
    if (newQty < 1) newQty = 1;
    if (newQty > prod.stock_qty) {
        showToast(`Cannot exceed available stock of ${prod.stock_qty}`, "warning");
        newQty = prod.stock_qty;
    }

    cartItem.qty = newQty;
    renderCatalogTable();
    recalculateCart();
}

function onQtyInputChange(partNo, val) {
    const prod = availableProducts.find(p => p.part_no === partNo);
    const cartItem = cartItems.find(i => i.part_no === partNo);
    if (!prod || !cartItem) return;

    let parsed = parseInt(val) || 1;
    if (parsed < 1) parsed = 1;
    if (parsed > prod.stock_qty) {
        showToast(`Cannot exceed available stock of ${prod.stock_qty}`, "warning");
        parsed = prod.stock_qty;
    }

    cartItem.qty = parsed;
    renderCatalogTable();
    recalculateCart();
}

function getSelectedBuyerType() {
    if (isBuyerTypeLocked) return lockedBuyerType;
    const selected = document.querySelector('input[name="buyer_type"]:checked');
    if (selected) return selected.value;
    const hidden = document.querySelector('input[name="buyer_type"]');
    return hidden ? hidden.value : "Customer";
}

function onBuyerTypeChanged(newType) {
    if (isBuyerTypeLocked) return;
    loadProducts();
}

function onGstModeChanged() {
    recalculateCart();
}

function onVehicleTypeFilter(vehicleType) {
    renderCatalogTable();
}

function lockBuyerType() {
    isBuyerTypeLocked = true;
    lockedBuyerType = getSelectedBuyerType();

    const radios = document.querySelectorAll('input[type="radio"][name="buyer_type"]');
    radios.forEach(r => r.disabled = true);

    const lockHint = document.getElementById("buyer-type-lock-hint");
    if (lockHint) lockHint.style.display = "block";
}

function unlockBuyerType() {
    isBuyerTypeLocked = false;
    const radios = document.querySelectorAll('input[type="radio"][name="buyer_type"]');
    radios.forEach(r => r.disabled = false);

    const lockHint = document.getElementById("buyer-type-lock-hint");
    if (lockHint) lockHint.style.display = "none";
}

function removeCartItem(index) {
    cartItems.splice(index, 1);
    if (cartItems.length === 0) {
        unlockBuyerType();
    }
    renderCatalogTable();
    recalculateCart();
}

function clearCart() {
    cartItems = [];
    unlockBuyerType();
    renderCatalogTable();
    recalculateCart();
}

async function recalculateCart() {
    const tbody = document.getElementById("cart-tbody");
    const countBadge = document.getElementById("cart-item-count");
    countBadge.textContent = cartItems.length;

    if (cartItems.length === 0) {
        tbody.innerHTML = `<tr class="empty-row"><td colspan="${window.IS_VEHICLE_PAGE ? 9 : 10}" class="text-center text-muted">No items ticked yet. Tick products above to add to bill.</td></tr>`;
        document.getElementById("tot-subtotal").textContent = "₹ 0.00";
        document.getElementById("tot-gst").textContent = "₹ 0.00";
        document.getElementById("tot-grand").textContent = "₹ 0.00";
        return;
    }

    const gstModeElem = document.getElementById("gst-mode");
    const gstMode = gstModeElem ? gstModeElem.value : "With GST (Tax Invoice)";
    const buyerType = getSelectedBuyerType();
    const marginPercent = getVehicleMarginPercent();

    try {
        const payload = {
            items: cartItems,
            buyer_type: buyerType,
            gst_mode: gstMode
        };
        if (marginPercent !== null) {
            payload.margin_percent = marginPercent;
        }

        const res = await fetch("/api/billing/calculate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        renderCartRows(data.items);

        // Update totals
        document.getElementById("tot-subtotal").textContent = formatINR(data.totals.base_total);
        document.getElementById("tot-gst").textContent = formatINR(data.totals.gst_amount);
        document.getElementById("tot-grand").textContent = formatINR(data.totals.grand_total);

        // Cache calculated data on window
        window.currentCartCalculated = data;
    } catch (e) {
        showToast("Error calculating cart totals: " + e.message, "error");
    }
}

function renderCartRows(items) {
    const tbody = document.getElementById("cart-tbody");
    tbody.innerHTML = "";

    const isVeh = window.IS_VEHICLE_PAGE;

    items.forEach((item, idx) => {
        const tr = document.createElement("tr");

        if (isVeh) {
            tr.innerHTML = `
                <td class="text-center"><strong>${idx + 1}</strong></td>
                <td>
                    <strong>${item.product_name}</strong>
                    ${getCategoryBadgeHtml(item.category)}
                </td>
                <td class="text-right">${formatINR(item.unit_price)}</td>
                <td class="text-center"><strong>${item.qty}</strong></td>
                <td class="text-right">${formatINR(item.subtotal)}</td>
                <td class="text-center">${item.gst_percent}%</td>
                <td class="text-right">${formatINR(item.gst_amount)}</td>
                <td class="text-right"><strong>${formatINR(item.total)}</strong></td>
                <td class="text-center">
                    <button type="button" class="btn btn-xs btn-outline-danger" onclick="removeCartItem(${idx})">🗑️</button>
                </td>
            `;
        } else {
            tr.innerHTML = `
                <td class="text-center"><strong>${idx + 1}</strong></td>
                <td><strong>${item.part_no}</strong></td>
                <td>
                    ${item.product_name}
                    ${getCategoryBadgeHtml(item.category)}
                </td>
                <td class="text-right">${formatINR(item.unit_price)}</td>
                <td class="text-center"><strong>${item.qty}</strong></td>
                <td class="text-right">${formatINR(item.subtotal)}</td>
                <td class="text-center">${item.gst_percent}%</td>
                <td class="text-right">${formatINR(item.gst_amount)}</td>
                <td class="text-right"><strong>${formatINR(item.total)}</strong></td>
                <td class="text-center">
                    <button type="button" class="btn btn-xs btn-outline-danger" onclick="removeCartItem(${idx})">🗑️</button>
                </td>
            `;
        }
        tbody.appendChild(tr);
    });
}

function validateCustomerInputs() {
    const name = document.getElementById("cust-name").value.trim();
    const mobile = document.getElementById("cust-mobile").value.trim();
    const gstin = document.getElementById("cust-gstin").value.trim().toUpperCase();

    if (!name) {
        showToast("Customer / Dealer Name is required", "error");
        document.getElementById("cust-name").focus();
        return null;
    }

    const cleanMobile = mobile.replace(/\D/g, "");
    if (cleanMobile.length < 10) {
        showToast("Mobile number must be at least 10 digits", "error");
        document.getElementById("cust-mobile").focus();
        return null;
    }

    if (gstin && gstin.length !== 15) {
        showToast("GSTIN must be 15 characters if provided", "warning");
    }

    if (window.IS_VEHICLE_PAGE) {
        const marginInput = document.getElementById("vehicle-profit-margin");
        if (!marginInput || marginInput.value.trim() === "") {
            showToast("Profit margin (%) is required", "error");
            if (marginInput) marginInput.focus();
            return null;
        }
        const mVal = parseFloat(marginInput.value);
        if (isNaN(mVal) || mVal < 0) {
            showToast("Please enter a valid profit margin (%)", "error");
            if (marginInput) marginInput.focus();
            return null;
        }
    }

    if (cartItems.length === 0) {
        showToast("Cart is empty. Please add at least one product.", "error");
        return null;
    }

    const billCat = window.BILL_CATEGORY || "Spare Parts";
    for (const item of cartItems) {
        if (billCat === "Spare Parts" && item.category !== "Spare Parts") {
            showToast("Spare bills can only contain Spare Parts.", "error");
            return null;
        }
        if (billCat === "Service" && item.category === "Vehicle Sales") {
            showToast("Service bills cannot contain Vehicle Sales items.", "error");
            return null;
        }
        if ((billCat === "Vehicle Sales" || window.IS_VEHICLE_PAGE) && item.category === "Service") {
            showToast("Vehicle bills cannot contain Service items.", "error");
            return null;
        }
    }

    return {
        customer_name: name,
        mobile: cleanMobile.slice(-10),
        address: document.getElementById("cust-address").value.trim(),
        gstin: gstin
    };
}

async function saveAndPrint() {
    const cust = validateCustomerInputs();
    if (!cust) return;

    const gstModeElem = document.getElementById("gst-mode");
    const gstMode = gstModeElem ? gstModeElem.value : "With GST (Tax Invoice)";
    const marginPercent = getVehicleMarginPercent();

    const payload = {
        category: window.BILL_CATEGORY || "Spare Parts",
        buyer_type: getSelectedBuyerType(),
        gst_mode: gstMode,
        margin_percent: marginPercent,
        customer_name: cust.customer_name,
        mobile: cust.mobile,
        address: cust.address,
        gstin: cust.gstin,
        items: window.currentCartCalculated.items.map(i => ({
            part_no: i.part_no,
            product_name: i.product_name,
            price: i.unit_price,
            qty: i.qty,
            subtotal: i.subtotal,
            gst_percent: i.gst_percent,
            gst_amount: i.gst_amount,
            total: i.total
        }))
    };

    showToast("Saving invoice and updating inventory...", "info");

    try {
        const res = await fetch("/api/billing/save", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (res.ok && data.success) {
            showToast(`Invoice ${data.invoice_no} saved! Opening print dialog...`, "success");
            printUrlSilently(`/invoice/${encodeURIComponent(data.invoice_no)}/print`);
            resetForm();
            refreshNextInvoiceNo();
            loadProducts();
        } else {
            let errText = "Error saving invoice";
            if (typeof data.detail === "string") {
                errText = data.detail;
            } else if (Array.isArray(data.detail)) {
                errText = data.detail.map(e => e.msg).join(", ");
            }
            showToast("Failed to save: " + errText, "error");
            loadProducts();
        }
    } catch (e) {
        showToast("Save error: " + e.message, "error");
    }
}

async function saveAndShareWhatsApp() {
    const cust = validateCustomerInputs();
    if (!cust) return;

    const gstModeElem = document.getElementById("gst-mode");
    const gstMode = gstModeElem ? gstModeElem.value : "With GST (Tax Invoice)";
    const marginPercent = getVehicleMarginPercent();

    const payload = {
        category: window.BILL_CATEGORY || "Spare Parts",
        buyer_type: getSelectedBuyerType(),
        gst_mode: gstMode,
        margin_percent: marginPercent,
        customer_name: cust.customer_name,
        mobile: cust.mobile,
        address: cust.address,
        gstin: cust.gstin,
        items: window.currentCartCalculated.items.map(i => ({
            part_no: i.part_no,
            product_name: i.product_name,
            price: i.unit_price,
            qty: i.qty,
            subtotal: i.subtotal,
            gst_percent: i.gst_percent,
            gst_amount: i.gst_amount,
            total: i.total
        }))
    };

    showToast("Saving invoice for WhatsApp...", "info");

    try {
        const res = await fetch("/api/billing/save", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (res.ok && data.success) {
            showToast("Bill saved! Opening WhatsApp...", "success");

            const msg = `Hello ${data.customer_name},\nThank you for shopping at Sri Dhanam Motors!\nInvoice No: ${data.invoice_no}\nGrand Total: ₹ ${data.grand_total.toFixed(2)}\nVisit us again!`;
            const waUrl = `https://wa.me/91${data.mobile}?text=${encodeURIComponent(msg)}`;

            window.open(waUrl, "_blank");
            resetForm();
            refreshNextInvoiceNo();
            loadProducts();
        } else {
            let errText = "Error saving invoice";
            if (typeof data.detail === "string") {
                errText = data.detail;
            } else if (Array.isArray(data.detail)) {
                errText = data.detail.map(e => e.msg).join(", ");
            }
            showToast("Save error: " + errText, "error");
            loadProducts();
        }
    } catch (e) {
        showToast("WhatsApp save error: " + e.message, "error");
    }
}

async function printEstimate() {
    if (cartItems.length === 0) {
        showToast("Cart is empty. Add items to print estimate.", "warning");
        return;
    }

    const name = document.getElementById("cust-name").value.trim() || "Customer";
    const mobile = document.getElementById("cust-mobile").value.trim();
    const address = document.getElementById("cust-address").value.trim();
    const gstin = document.getElementById("cust-gstin").value.trim();

    const payload = {
        category: window.BILL_CATEGORY || "Spare Parts",
        customer_name: name,
        mobile: mobile,
        address: address,
        gstin: gstin,
        invoice_no: "ESTIMATE-" + Date.now().toString().slice(-4),
        items: window.currentCartCalculated ? window.currentCartCalculated.items : [],
        totals: window.currentCartCalculated ? window.currentCartCalculated.totals : {}
    };

    showToast("Opening Estimate...", "info");

    try {
        const res = await fetch("/estimate/print", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            const html = await res.text();
            printHtmlSilently(html);
        } else {
            showToast("Failed to render estimate", "error");
        }
    } catch (e) {
        showToast("Error printing estimate: " + e.message, "error");
    }
}

function resetForm() {
    document.getElementById("cust-name").value = "";
    document.getElementById("cust-mobile").value = "";
    document.getElementById("cust-address").value = "";
    document.getElementById("cust-gstin").value = "";
    if (window.IS_VEHICLE_PAGE) {
        const marginInput = document.getElementById("vehicle-profit-margin");
        if (marginInput) {
            marginInput.value = "";
        }
    }
    clearCatalogSearch();
    activeFilterTab = "all";
    if (window.BILL_CATEGORY === "Spare Parts") {
        activeBillingCategory = "Spare Parts";
    } else {
        activeBillingCategory = "All";
    }
    document.querySelectorAll(".catalog-category-pills-bar .filter-pill").forEach(p => p.classList.remove("active"));
    const defaultPill = document.querySelector(`.catalog-category-pills-bar .filter-pill[data-cat="${activeBillingCategory}"]`);
    if (defaultPill) defaultPill.classList.add("active");

    const tabAll = document.getElementById("tab-filter-all");
    const tabTicked = document.getElementById("tab-filter-ticked");
    if (tabAll && tabTicked) {
        tabAll.classList.add("active");
        tabTicked.classList.remove("active");
    }
    clearCart();
    showToast("Form reset", "info");
}

async function refreshNextInvoiceNo() {
    const category = window.BILL_CATEGORY || "Spare Parts";
    try {
        const res = await fetch(`/api/billing/next-invoice-no?category=${encodeURIComponent(category)}`);
        const data = await res.json();
        const display = document.getElementById("bill-inv-no-display");
        if (display && data.invoice_no) {
            display.textContent = data.invoice_no;
        }
    } catch (e) {
        console.error(e);
    }
}
