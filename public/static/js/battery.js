/**
 * Sri Dhanam Motors - Battery Serial & QR Handling
 */

let lastGeneratedBattery = null;

async function generateBattery() {
    const bType = document.getElementById("battery-type").value;
    const voltage = parseFloat(document.getElementById("battery-voltage").value);
    const ah = parseFloat(document.getElementById("battery-ah").value);
    const createProd = document.getElementById("battery-create-product").checked;

    if (isNaN(voltage) || voltage <= 0 || isNaN(ah) || ah <= 0) {
        showToast("Please enter valid Voltage and Ah numbers", "warning");
        return;
    }

    showToast("Generating Battery Serial & QR Codes...", "info");

    try {
        const res = await fetch("/api/batteries/generate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                type: bType,
                voltage: voltage,
                ah: ah,
                create_product: createProd
            })
        });

        const data = await res.json();
        if (data.success) {
            lastGeneratedBattery = data;
            showToast(`Generated serial: ${data.serial}`, "success");

            // Display in Preview Card
            document.getElementById("res-serial-badge").textContent = data.serial;
            document.getElementById("res-spec-line").textContent = `${data.type} ${data.voltage}V ${data.ah}Ah`;
            document.getElementById("res-qr-img").src = `data:image/png;base64,${data.qr_base64}`;
            document.getElementById("res-bc-img").src = `data:image/png;base64,${data.barcode_base64}`;
            document.getElementById("battery-result-card").style.display = "block";

            // Update Next Projected Serial badge
            const num = parseInt(data.serial.replace("SDM", "")) + 1;
            document.getElementById("next-serial-badge").textContent = `SDM${String(num).padStart(4, "0")}`;

            // Refresh table dynamically
            prependBatteryRow(data.battery);
        } else {
            showToast("Failed to generate battery serial", "error");
        }
    } catch (e) {
        showToast("Network error generating QR: " + e.message, "error");
    }
}

function prependBatteryRow(b) {
    const tbody = document.getElementById("batteries-tbody");
    if (!tbody) return;

    const tr = document.createElement("tr");
    tr.innerHTML = `
        <td><strong>${b.serial}</strong></td>
        <td><span class="badge-pill">${b.type}</span></td>
        <td>${b.voltage}V</td>
        <td>${b.ah}Ah</td>
        <td>${b.created_at}</td>
        <td><span class="badge-available">In Stock</span></td>
        <td>
            <button type="button" class="btn btn-sm btn-outline-primary" onclick="openBatteryPrintModal('${b.serial}', '${b.type}', ${b.voltage}, ${b.ah})">🏷️ Print</button>
        </td>
    `;

    tbody.insertBefore(tr, tbody.firstChild);
}

function printGeneratedBatteryLabel() {
    if (!lastGeneratedBattery) return;
    openBatteryPrintModal(
        lastGeneratedBattery.serial,
        lastGeneratedBattery.type,
        lastGeneratedBattery.voltage,
        lastGeneratedBattery.ah
    );
}

function openBatteryPrintModal(serial, bType, voltage, ah) {
    openUniversalLabelModal({
        type: "battery",
        serial: serial,
        battery_type: bType,
        voltage: voltage,
        ah: ah,
        copies: 1
    });
}

function filterBatteryTable(query) {
    const q = query.toLowerCase().trim();
    const rows = document.querySelectorAll("#batteries-tbody tr");
    rows.forEach(r => {
        const text = r.innerText.toLowerCase();
        r.style.display = (!q || text.includes(q)) ? "" : "none";
    });
}
