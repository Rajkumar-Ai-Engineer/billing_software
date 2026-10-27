/**
 * Sri Dhanam Motors - Product & Stock Master Management
 */

let activeCategory = "All";
let pendingUploadItems = [];

function setCategoryFilter(cat, btn) {
    activeCategory = cat;
    document.querySelectorAll(".filter-pills-wrap .filter-pill").forEach(p => p.classList.remove("active"));
    if (btn) btn.classList.add("active");
    filterProductRows();
}

function onSearchProducts(query) {
    filterProductRows();
}

function filterProductRows() {
    const q = document.getElementById("product-search-input").value.toLowerCase().trim();
    const rows = document.querySelectorAll("#products-tbody tr");

    rows.forEach(row => {
        if (row.classList.contains("empty-row")) return;
        const cat = row.dataset.cat || "";
        const text = row.innerText.toLowerCase();

        const matchesCat = (activeCategory === "All" || cat === activeCategory);
        const matchesQuery = (!q || text.includes(q));

        row.style.display = (matchesCat && matchesQuery) ? "" : "none";
    });
}

function toggleSelectAll(checked) {
    document.querySelectorAll(".prod-checkbox").forEach(cb => {
        const row = cb.closest("tr");
        if (row && row.style.display !== "none") {
            cb.checked = checked;
        }
    });
}

// Inline Editing
function enableInlineEdit(cell, field, partNo) {
    if (cell.querySelector("input")) return; // Already editing

    const originalValue = cell.innerText.trim().replace("%", "");
    const input = document.createElement("input");
    input.type = (field === "cost_price" || field === "gst_percent") ? "number" : "text";
    if (field === "cost_price" || field === "gst_percent") input.step = "0.01";
    input.value = originalValue;
    input.className = "input-ctrl-sm";
    input.style.width = "100%";

    cell.innerHTML = "";
    cell.appendChild(input);
    input.focus();

    async function saveEdit() {
        const newVal = input.value.trim();
        if (newVal === originalValue) {
            cell.innerText = (field === "gst_percent") ? `${originalValue}%` : originalValue;
            return;
        }

        const payload = {};
        if (field === "cost_price") payload.cost_price = parseFloat(newVal);
        else if (field === "gst_percent") payload.gst_percent = parseFloat(newVal);
        else payload[field] = newVal;

        try {
            const res = await fetch(`/api/products/${encodeURIComponent(partNo)}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (data.success) {
                showToast("Product updated", "success");
                cell.innerText = (field === "gst_percent") ? `${newVal}%` : newVal;
            } else {
                showToast("Update failed", "error");
                cell.innerText = (field === "gst_percent") ? `${originalValue}%` : originalValue;
            }
        } catch (e) {
            showToast("Network error: " + e.message, "error");
            cell.innerText = (field === "gst_percent") ? `${originalValue}%` : originalValue;
        }
    }

    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") saveEdit();
        if (e.key === "Escape") cell.innerText = (field === "gst_percent") ? `${originalValue}%` : originalValue;
    });

    input.addEventListener("blur", saveEdit);
}

// New Product Modal
function openNewProductModal() {
    openModal("new-product-modal");
}

function onNewCatChange(cat) {
    // Category changed
}

async function submitNewProduct() {
    const payload = {
        part_no: document.getElementById("new-p-part").value.trim(),
        name: document.getElementById("new-p-name").value.trim(),
        category: document.getElementById("new-p-cat").value,
        vehicle_type: null,
        hsn: document.getElementById("new-p-hsn").value.trim(),
        cost_price: parseFloat(document.getElementById("new-p-cost").value) || 0,
        gst_percent: parseFloat(document.getElementById("new-p-gst").value) || 18,
        stock_qty: parseInt(document.getElementById("new-p-stock").value) || 0
    };

    try {
        const res = await fetch("/api/products", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            showToast("New product created and saved to Excel file!", "success");
            closeModal("new-product-modal");
            setTimeout(() => window.location.reload(), 800);
        } else {
            showToast("Failed to create product: " + (data.detail || "Error"), "error");
        }
    } catch (e) {
        showToast("Network error: " + e.message, "error");
    }
}

// Quick Add to Store & Excel
function openQuickAddModal(partNo, name, currentStock) {
    document.getElementById("qa-prod-name").textContent = name;
    document.getElementById("qa-part-no-display").textContent = partNo;
    document.getElementById("qa-part-no").value = partNo;
    document.getElementById("qa-curr-stock").textContent = currentStock;
    document.getElementById("qa-qty").value = 1;
    document.getElementById("qa-reason").value = "Added to Store";
    openModal("quick-add-modal");
    setTimeout(() => {
        const inp = document.getElementById("qa-qty");
        if (inp) { inp.focus(); inp.select(); }
    }, 150);
}

function setQuickAddQty(qty) {
    const inp = document.getElementById("qa-qty");
    if (inp) {
        inp.value = qty;
        inp.focus();
    }
}

function switchModalToReduce() {
    const partNo = document.getElementById("qa-part-no").value;
    const name = document.getElementById("qa-prod-name").textContent;
    const currentStock = parseInt(document.getElementById("qa-curr-stock").textContent) || 0;
    closeModal("quick-add-modal");
    openQuickReduceModal(partNo, name, currentStock);
}

function switchModalToAdd() {
    const partNo = document.getElementById("qr-part-no").value;
    const name = document.getElementById("qr-prod-name").textContent;
    const currentStock = parseInt(document.getElementById("qr-curr-stock").textContent) || 0;
    closeModal("quick-reduce-modal");
    openQuickAddModal(partNo, name, currentStock);
}

async function submitQuickAdd() {
    const partNo = document.getElementById("qa-part-no").value;
    const qty = parseInt(document.getElementById("qa-qty").value);
    const reason = document.getElementById("qa-reason").value.trim() || "Added to Store";
    const btn = document.getElementById("btn-submit-quick-add");

    if (isNaN(qty) || qty <= 0) {
        showToast("Please enter a valid quantity greater than zero", "warning");
        document.getElementById("qa-qty").focus();
        return;
    }

    if (btn) btn.disabled = true;

    try {
        const res = await fetch("/api/products/quick-add", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ part_no: partNo, change: qty, reason: reason })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`➕ Added ${data.added} to ${data.part_no}! Total Stock: ${data.stock_qty}. Saved to Excel.`, "success");
            closeModal("quick-add-modal");

            // Update row in table immediately without needing full page reload
            const row = document.getElementById(`row-${partNo}`);
            if (row) {
                const stockCell = row.querySelector(".stock-cell");
                if (stockCell) {
                    stockCell.innerHTML = `<strong>${data.stock_qty}</strong>`;
                    if (data.stock_qty > 3) {
                        stockCell.classList.remove("stock-low");
                    }
                }
                // Highlight row briefly
                row.style.transition = "background-color 0.4s ease";
                row.style.backgroundColor = "#dcfce7";
                setTimeout(() => { row.style.backgroundColor = ""; }, 1200);

                // Update onclick handlers with new stock
                const safeName = (data.name || "").replace(/'/g, "\\'");
                const stockBtn = row.querySelector("button[title='Adjust Stock']");
                if (stockBtn) {
                    stockBtn.setAttribute("onclick", `openStockAdjustModal('${partNo}', '${safeName}', ${data.stock_qty})`);
                }
                const addBtn = row.querySelector(".btn-add-stock");
                if (addBtn) {
                    addBtn.setAttribute("onclick", `openQuickAddModal('${partNo}', '${safeName}', ${data.stock_qty})`);
                }
                const reduceBtn = row.querySelector(".btn-reduce-stock");
                if (reduceBtn) {
                    reduceBtn.setAttribute("onclick", `openQuickReduceModal('${partNo}', '${safeName}', ${data.stock_qty})`);
                }
            }
        } else {
            showToast("Failed to add stock: " + (data.detail || "Error"), "error");
        }
    } catch (e) {
        showToast("Error adding stock: " + e.message, "error");
    } finally {
        if (btn) btn.disabled = false;
    }
}

// Quick Reduce / Remove Stock from Store & Excel
let currentReduceMaxStock = 0;

function openQuickReduceModal(partNo, name, currentStock) {
    currentReduceMaxStock = parseInt(currentStock) || 0;
    document.getElementById("qr-prod-name").textContent = name;
    document.getElementById("qr-part-no-display").textContent = partNo;
    document.getElementById("qr-part-no").value = partNo;
    document.getElementById("qr-curr-stock").textContent = currentStock;
    document.getElementById("qr-reason").value = "Reduced from Store";

    const qtyInp = document.getElementById("qr-qty");
    const zeroAlert = document.getElementById("qr-zero-stock-alert");
    const submitBtn = document.getElementById("btn-submit-quick-reduce");

    if (currentReduceMaxStock <= 0) {
        zeroAlert.style.display = "block";
        qtyInp.value = 0;
        qtyInp.disabled = true;
        submitBtn.disabled = true;
    } else {
        zeroAlert.style.display = "none";
        qtyInp.disabled = false;
        qtyInp.value = 1;
        qtyInp.max = currentReduceMaxStock;
        submitBtn.disabled = false;
    }

    openModal("quick-reduce-modal");
    setTimeout(() => {
        if (!qtyInp.disabled) {
            qtyInp.focus();
            qtyInp.select();
        }
    }, 150);
}

function setQuickReduceQty(qty) {
    const inp = document.getElementById("qr-qty");
    if (!inp || inp.disabled) return;
    if (qty === 'all') {
        inp.value = Math.max(1, currentReduceMaxStock);
    } else {
        const val = parseInt(qty);
        inp.value = (currentReduceMaxStock > 0 && val > currentReduceMaxStock) ? currentReduceMaxStock : val;
    }
    inp.focus();
}

async function submitQuickReduce() {
    const partNo = document.getElementById("qr-part-no").value;
    const qty = parseInt(document.getElementById("qr-qty").value);
    const reason = document.getElementById("qr-reason").value.trim() || "Reduced from Store";
    const btn = document.getElementById("btn-submit-quick-reduce");

    if (isNaN(qty) || qty <= 0) {
        showToast("Please enter a valid quantity greater than zero", "warning");
        document.getElementById("qr-qty").focus();
        return;
    }

    if (qty > currentReduceMaxStock) {
        showToast(`Cannot reduce by ${qty}. Current stock is only ${currentReduceMaxStock}.`, "warning");
        document.getElementById("qr-qty").focus();
        return;
    }

    if (btn) btn.disabled = true;

    try {
        const res = await fetch("/api/products/quick-reduce", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ part_no: partNo, change: qty, reason: reason })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`➖ Reduced ${data.reduced} from ${data.part_no}! Total Stock: ${data.stock_qty}. Saved to Excel.`, "success");
            closeModal("quick-reduce-modal");

            // Update row in table immediately without needing full page reload
            const row = document.getElementById(`row-${partNo}`);
            if (row) {
                const stockCell = row.querySelector(".stock-cell");
                if (stockCell) {
                    stockCell.innerHTML = `<strong>${data.stock_qty}</strong>`;
                    if (data.stock_qty <= 3) {
                        stockCell.classList.add("stock-low");
                    } else {
                        stockCell.classList.remove("stock-low");
                    }
                }
                // Highlight row briefly
                row.style.transition = "background-color 0.4s ease";
                row.style.backgroundColor = "#fee2e2";
                setTimeout(() => { row.style.backgroundColor = ""; }, 1200);

                // Update onclick handlers with new stock
                const safeName = (data.name || "").replace(/'/g, "\\'");
                const stockBtn = row.querySelector("button[title='Adjust Stock']");
                if (stockBtn) {
                    stockBtn.setAttribute("onclick", `openStockAdjustModal('${partNo}', '${safeName}', ${data.stock_qty})`);
                }
                const addBtn = row.querySelector(".btn-add-stock");
                if (addBtn) {
                    addBtn.setAttribute("onclick", `openQuickAddModal('${partNo}', '${safeName}', ${data.stock_qty})`);
                }
                const reduceBtn = row.querySelector(".btn-reduce-stock");
                if (reduceBtn) {
                    reduceBtn.setAttribute("onclick", `openQuickReduceModal('${partNo}', '${safeName}', ${data.stock_qty})`);
                }
            }
        } else {
            showToast("Failed to reduce stock: " + (data.detail || "Error"), "error");
        }
    } catch (e) {
        showToast("Error reducing stock: " + e.message, "error");
    } finally {
        if (btn) btn.disabled = false;
    }
}

// Delete Product
async function confirmDeleteProduct(partNo) {
    if (!confirm(`Are you sure you want to delete product '${partNo}'?`)) return;

    try {
        const res = await fetch(`/api/products/${encodeURIComponent(partNo)}`, {
            method: "DELETE"
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, "success");
            const row = document.getElementById(`row-${partNo}`);
            if (row) row.remove();
        } else {
            showToast("Failed to delete: " + data.detail, "error");
        }
    } catch (e) {
        showToast("Delete error: " + e.message, "error");
    }
}

// Stock Adjustment
function openStockAdjustModal(partNo, name, currentStock, currentPrice) {
    document.getElementById("adj-prod-display").value = `${partNo} - ${name} (Current: ${currentStock})`;
    document.getElementById("adj-part-no").value = partNo;
    document.getElementById("adj-change").value = "";
    document.getElementById("adj-price").value = (currentPrice !== undefined && currentPrice !== null) ? currentPrice : "";
    openModal("stock-adjust-modal");
    setTimeout(() => {
        const inp = document.getElementById("adj-change");
        if (inp) inp.focus();
    }, 150);
}

function toggleStockAdjustSign(sign) {
    const inp = document.getElementById("adj-change");
    if (!inp) return;
    let val = parseInt(inp.value);
    if (isNaN(val) || val === 0) {
        inp.value = sign === '-' ? -1 : 1;
    } else {
        inp.value = sign === '-' ? -Math.abs(val) : Math.abs(val);
    }
    inp.focus();
}

async function submitStockAdjust() {
    const partNo = document.getElementById("adj-part-no").value;
    const change = parseInt(document.getElementById("adj-change").value);
    const priceVal = document.getElementById("adj-price").value.trim();
    const price = priceVal !== "" ? parseFloat(priceVal) : null;

    if (isNaN(change) || change === 0) {
        showToast("Adjustment quantity must be non-zero", "warning");
        return;
    }

    const payload = {
        part_no: partNo,
        change: change,
        reason: "Stock Adjustment"
    };
    if (price !== null && !isNaN(price)) {
        payload.price = price;
    }

    try {
        const res = await fetch("/api/products/stock-adjust", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            let msg = `Stock updated to ${data.stock_qty}!`;
            if (data.cost_price !== undefined) {
                msg += ` (Price: ₹${data.cost_price.toFixed(2)})`;
            }
            showToast(msg + " Saved to Excel.", "success");
            closeModal("stock-adjust-modal");
            setTimeout(() => window.location.reload(), 800);
        } else {
            showToast("Adjustment failed: " + data.detail, "error");
        }
    } catch (e) {
        showToast("Error: " + e.message, "error");
    }
}

// Upload CSV/Excel
function openUploadModal() {
    pendingUploadItems = [];
    document.getElementById("upload-file-input").value = "";
    document.getElementById("upload-preview-area").style.display = "none";
    document.getElementById("btn-commit-upload").style.display = "none";
    openModal("upload-modal");
}

async function previewUploadedFile(file) {
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    showToast("Analyzing file contents...", "info");

    try {
        const res = await fetch("/api/products/upload-preview", {
            method: "POST",
            body: formData
        });
        const data = await res.json();

        pendingUploadItems = data.items;
        document.getElementById("upload-count").textContent = data.total_items;

        const errBox = document.getElementById("upload-errors-list");
        const errBadge = document.getElementById("upload-errors-badge");

        if (data.errors && data.errors.length > 0) {
            errBadge.style.display = "inline-block";
            errBox.style.display = "block";
            errBox.innerHTML = `<strong>Validation Notes (${data.errors.length}):</strong><br>` + data.errors.slice(0, 5).join("<br>");
        } else {
            errBadge.style.display = "none";
            errBox.style.display = "none";
        }

        const tbody = document.getElementById("upload-preview-table").querySelector("tbody");
        tbody.innerHTML = "";
        data.items.slice(0, 50).forEach(item => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td><strong>${item.part_no}</strong></td>
                <td>${item.name}</td>
                <td>₹ ${item.cost_price}</td>
                <td>${item.gst_percent}%</td>
                <td>${item.category}</td>
                <td>${item.stock_qty}</td>
            `;
            tbody.appendChild(tr);
        });

        document.getElementById("upload-preview-area").style.display = "block";
        document.getElementById("btn-commit-upload").style.display = "inline-block";
    } catch (e) {
        showToast("Upload preview failed: " + e.message, "error");
    }
}

async function commitUpload() {
    if (!pendingUploadItems || pendingUploadItems.length === 0) return;

    showToast("Committing imported products to database...", "info");

    try {
        const res = await fetch("/api/products/upload-commit", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ items: pendingUploadItems })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Imported: ${data.result.inserted} added, ${data.result.updated} updated!`, "success");
            closeModal("upload-modal");
            setTimeout(() => window.location.reload(), 1200);
        } else {
            showToast("Commit error", "error");
        }
    } catch (e) {
        showToast("Commit network error: " + e.message, "error");
    }
}

// Export Dropdown
function toggleExportMenu() {
    const menu = document.getElementById("export-dropdown");
    menu.style.display = (menu.style.display === "none") ? "block" : "none";
}

function openInvoiceExportModal() {
    toggleExportMenu();
    openModal("invoice-export-modal");
}

function triggerInvoiceExport() {
    const start = document.getElementById("exp-start-date").value;
    const end = document.getElementById("exp-end-date").value;
    const format = document.getElementById("exp-format").value;

    let url = `/api/invoices/export?format=${format}`;
    if (start) url += `&start_date=${start}`;
    if (end) url += `&end_date=${end}`;

    window.location.href = url;
    closeModal("invoice-export-modal");
}

// Label Printing
function openProductPrintModal(partNo, name, costPrice) {
    openUniversalLabelModal({
        type: "product",
        part_no: partNo,
        name: name,
        product_name: name,
        cost_price: costPrice,
        price: costPrice * 1.80, // Customer price
        show_price: false
    });
}

function printBulkProductLabels() {
    const checked = Array.from(document.querySelectorAll(".prod-checkbox:checked")).map(cb => cb.value);
    if (checked.length === 0) {
        showToast("Please select at least one product using checkboxes.", "warning");
        return;
    }

    const items = [];
    checked.forEach(partNo => {
        const row = document.getElementById("row-" + partNo);
        let name = partNo;
        let costPrice = 0;
        if (row) {
            const cells = row.querySelectorAll("td");
            if (cells.length > 2) name = cells[2].innerText.trim();
            if (cells.length > 4) {
                const costText = cells[4].innerText.replace(/[^0-9.]/g, '');
                costPrice = parseFloat(costText) || 0;
            }
        }
        items.push({
            type: "product",
            part_no: partNo,
            name: name,
            product_name: name,
            cost_price: costPrice,
            price: costPrice * 1.80,
            show_price: false
        });
    });

    openUniversalLabelModal({
        type: "product",
        part_no: checked[0],
        name: `${checked.length} Selected Products`,
        product_name: `${checked.length} Selected Products`,
        copies: 1,
        items: items
    });
}
