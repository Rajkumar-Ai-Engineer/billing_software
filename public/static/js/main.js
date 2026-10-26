/**
 * Sri Dhanam Motors - Core Client Utilities
 */

// Toast Notifications
function showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.textContent = message;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// Modal Helpers
function openModal(id) {
    const el = document.getElementById(id);
    if (el) el.style.display = "flex";
}

function closeModal(id) {
    const el = document.getElementById(id);
    if (el) el.style.display = "none";
}

// Currency Formatter
function formatINR(val) {
    const num = parseFloat(val) || 0;
    return "₹ " + num.toLocaleString("en-IN", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

// Global Label Print Modal Handling
let currentLabelOptions = null;

function openUniversalLabelModal(options) {
    currentLabelOptions = options;
    document.getElementById("modal-lbl-type").value = options.type.toUpperCase();
    document.getElementById("modal-lbl-copies").value = options.copies || 1;

    const priceBox = document.getElementById("modal-lbl-price-toggle-box");
    if (options.type === "product") {
        priceBox.style.display = "block";
        document.getElementById("modal-lbl-show-price").checked = options.show_price || false;
    } else {
        priceBox.style.display = "none";
    }

    renderLabelPreview();
    openModal("global-label-modal");
}

function closeLabelModal() {
    closeModal("global-label-modal");
    currentLabelOptions = null;
}

function renderLabelPreview() {
    if (!currentLabelOptions) return;
    const previewDiv = document.getElementById("modal-lbl-preview");
    const opt = currentLabelOptions;
    const showPrice = document.getElementById("modal-lbl-show-price").checked;

    let html = `<div style="padding: 6px; text-align: left; font-family: Arial; border: 1px dashed #475569; background: #fff;">`;
    html += `<div style="font-size: 10px; font-weight: bold; color: #2E7D32;">SRI DHANAM MOTORS</div>`;

    if (opt.type === "battery") {
        html += `<div style="font-size: 14px; font-weight: bold;">${opt.serial || "SDM0001"}</div>`;
        html += `<div style="font-size: 10px;">${opt.battery_type || "LFP"} ${opt.voltage || 48}V ${opt.ah || 30}Ah</div>`;
        html += `<div style="font-size: 9px; color: #64748b; margin-top: 4px;">[QR Code + Code128 Barcode]</div>`;
    } else if (opt.type === "invoice") {
        html += `<div style="font-size: 13px; font-weight: bold;">INV: ${opt.invoice_no || "INV-001"}</div>`;
        html += `<div style="font-size: 9px; color: #64748b; margin-top: 4px;">[Invoice Barcode]</div>`;
    } else {
        html += `<div style="font-size: 10px; font-weight: bold;">${opt.name || "Product Name"}</div>`;
        html += `<div style="font-size: 11px; font-weight: bold; letter-spacing: 1px;">||||||||||||||||||||</div>`;
        html += `<div style="font-size: 9px;">${opt.part_no || "SDM-PART"}</div>`;
        if (showPrice && opt.price) {
            html += `<div style="font-size: 11px; font-weight: bold; color: #000;">MRP: ${formatINR(opt.price)}</div>`;
        }
    }
    html += `</div>`;
    previewDiv.innerHTML = html;
}

document.addEventListener("DOMContentLoaded", () => {
    const priceToggle = document.getElementById("modal-lbl-show-price");
    if (priceToggle) {
        priceToggle.addEventListener("change", renderLabelPreview);
    }
});

async function submitLabelPrint() {
    if (!currentLabelOptions) return;

    const mode = document.getElementById("modal-lbl-mode").value;
    const copies = parseInt(document.getElementById("modal-lbl-copies").value) || 1;
    const preset = document.getElementById("modal-lbl-preset").value;
    const showPrice = document.getElementById("modal-lbl-show-price").checked;

    let [w, h] = [50, 30];
    if (preset === "38x25") [w, h] = [38, 25];
    else if (preset === "50x25") [w, h] = [50, 25];
    else if (preset === "100x50") [w, h] = [100, 50];

    const opt = currentLabelOptions;
    opt.copies = copies;
    opt.show_price = showPrice;

    if (mode === "driver_html") {
        // Open printable HTML view directly in page without new tab
        const displayName = opt.product_name || opt.name || "";
        let url = `/labels/preview?type=${encodeURIComponent(opt.type)}&width_mm=${w}&height_mm=${h}&copies=${copies}`;
        if (opt.part_no) url += `&part_no=${encodeURIComponent(opt.part_no)}`;
        if (displayName) url += `&name=${encodeURIComponent(displayName)}`;
        if (opt.price) url += `&price=${opt.price}`;
        if (showPrice) url += `&show_price=true`;
        if (opt.serial) url += `&serial=${encodeURIComponent(opt.serial)}`;
        if (opt.battery_type) url += `&battery_type=${encodeURIComponent(opt.battery_type)}`;
        if (opt.voltage) url += `&voltage=${opt.voltage}`;
        if (opt.ah) url += `&ah=${opt.ah}`;
        if (opt.invoice_no) url += `&invoice_no=${encodeURIComponent(opt.invoice_no)}`;

        showToast("Opening label print dialog...", "info");
        printUrlSilently(url);
        closeLabelModal();
    } else {
        // RAW mode via backend API to TVS LP 46
        showToast("Sending label directly to TVS LP 46 printer...", "info");
        try {
            let itemsToSend = [opt];
            if (opt.items && opt.items.length > 0) {
                itemsToSend = opt.items.map(it => ({
                    ...it,
                    copies: copies,
                    show_price: showPrice
                }));
            } else {
                opt.copies = copies;
                opt.show_price = showPrice;
                itemsToSend = [opt];
            }

            const res = await fetch("/api/labels/print", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    mode: "raw",
                    width_mm: w,
                    height_mm: h,
                    copies: copies,
                    items: itemsToSend
                })
            });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.success) {
                showToast("Sent to printer successfully!", "success");
                closeLabelModal();
            } else {
                const errDetail = data.message || data.detail || (typeof data === "string" ? data : "Print failed");
                showToast("Printer Error: " + errDetail, "error");
            }
        } catch (e) {
            showToast("Failed to print: " + e.message, "error");
        }
    }
}

// Silent in-page printing utilities (No extra browser tabs)
function printUrlSilently(url) {
    let iframe = document.getElementById("app-silent-print-frame");
    if (iframe) {
        iframe.remove();
    }
    iframe = document.createElement("iframe");
    iframe.id = "app-silent-print-frame";
    iframe.style.position = "fixed";
    iframe.style.bottom = "-10000px";
    iframe.style.right = "-10000px";
    iframe.style.width = "1024px";
    iframe.style.height = "1024px";
    iframe.style.border = "0";
    iframe.style.opacity = "0.01";
    iframe.style.pointerEvents = "none";
    document.body.appendChild(iframe);

    iframe.onload = function() {
        setTimeout(() => {
            try {
                iframe.contentWindow.focus();
                iframe.contentWindow.print();
            } catch (err) {
                console.error("Print error:", err);
            }
        }, 300);
    };
    iframe.src = url;
}

function printHtmlSilently(htmlContent) {
    let iframe = document.getElementById("app-silent-print-frame");
    if (iframe) {
        iframe.remove();
    }
    iframe = document.createElement("iframe");
    iframe.id = "app-silent-print-frame";
    iframe.style.position = "fixed";
    iframe.style.bottom = "-10000px";
    iframe.style.right = "-10000px";
    iframe.style.width = "1024px";
    iframe.style.height = "1024px";
    iframe.style.border = "0";
    iframe.style.opacity = "0.01";
    iframe.style.pointerEvents = "none";
    document.body.appendChild(iframe);

    const doc = iframe.contentWindow.document;
    doc.open();
    doc.write(htmlContent);
    doc.close();

    setTimeout(() => {
        try {
            iframe.contentWindow.focus();
            iframe.contentWindow.print();
        } catch (err) {
            console.error("Print error:", err);
        }
    }, 300);
}
