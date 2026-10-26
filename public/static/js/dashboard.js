/**
 * Sri Dhanam Motors - Dashboard Analytics & Reporting
 */

let currentPeriod = "daily";
let salesTrendChartInstance = null;
let categoryPieChartInstance = null;

document.addEventListener("DOMContentLoaded", () => {
    fetchDashboardData();
});

function changePeriod(period) {
    currentPeriod = period;
    document.querySelectorAll(".period-switch-group .btn-toggle").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.period === period);
    });
    fetchDashboardData();
}

function onDateChanged() {
    fetchDashboardData();
}

async function fetchDashboardData() {
    const targetDate = document.getElementById("dash-date").value;
    const url = `/api/dashboard?period=${encodeURIComponent(currentPeriod)}&target_date=${encodeURIComponent(targetDate)}`;

    try {
        const res = await fetch(url);
        const data = await res.json();
        updateDashboardUI(data);
    } catch (e) {
        showToast("Error fetching dashboard reports: " + e.message, "error");
    }
}

function updateDashboardUI(data) {
    // 1. Metric Cards
    document.getElementById("val-total-sales").textContent = formatINR(data.total_sales);
    document.getElementById("val-invoice-count").textContent = `${data.count_invoices} Invoices`;
    document.getElementById("val-total-gst").textContent = formatINR(data.total_gst);

    const cats = data.categories;
    if (cats["Spare Parts"]) {
        document.getElementById("val-spare-sales").textContent = formatINR(cats["Spare Parts"].sales);
        document.getElementById("val-spare-count").textContent = `${cats["Spare Parts"].count} Bills`;
    }
    if (cats["Service"]) {
        document.getElementById("val-service-sales").textContent = formatINR(cats["Service"].sales);
        document.getElementById("val-service-count").textContent = `${cats["Service"].count} Bills`;
    }
    if (cats["Vehicle Sales"]) {
        document.getElementById("val-vehicle-sales").textContent = formatINR(cats["Vehicle Sales"].sales);
        document.getElementById("val-vehicle-count").textContent = `${cats["Vehicle Sales"].count} Bills`;
    }

    const expElem = document.getElementById("val-total-expenses");
    if (expElem) {
        expElem.textContent = formatINR(data.total_expenses || 0);
    }
    const purElem = document.getElementById("val-total-purchases");
    if (purElem) {
        purElem.textContent = formatINR(data.total_purchases || 0);
    }

    const badge = document.getElementById("chart-period-badge");
    badge.textContent = `${data.start_date} to ${data.end_date}`;

    // 2. Trend Line Chart
    renderTrendChart(data.chart);

    // 3. Category Doughnut Chart
    renderPieChart(data.chart.category_pie);

    // 4. Recent Invoices
    renderRecentInvoices(data.recent_invoices);

    // 5. Low Stock Alert
    renderLowStock(data.low_stock);
}

function renderTrendChart(chartData) {
    const ctx = document.getElementById("salesTrendChart").getContext("2d");

    if (salesTrendChartInstance) {
        salesTrendChartInstance.destroy();
    }

    salesTrendChartInstance = new Chart(ctx, {
        type: "line",
        data: {
            labels: chartData.labels,
            datasets: chartData.datasets.map(ds => ({
                ...ds,
                tension: 0.3,
                fill: false,
                borderWidth: 2,
                pointRadius: 4,
                pointHoverRadius: 6
            }))
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: "top" },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return context.dataset.label + ": ₹ " + context.parsed.y.toLocaleString("en-IN");
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: val => "₹ " + val.toLocaleString("en-IN")
                    }
                }
            }
        }
    });
}

function renderPieChart(pieData) {
    const ctx = document.getElementById("categoryPieChart").getContext("2d");

    if (categoryPieChartInstance) {
        categoryPieChartInstance.destroy();
    }

    categoryPieChartInstance = new Chart(ctx, {
        type: "doughnut",
        data: {
            labels: pieData.labels,
            datasets: [{
                data: pieData.data,
                backgroundColor: ["#2E7D32", "#2B6CB0", "#E53E3E"]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: "bottom" },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return context.label + ": ₹ " + context.parsed.toLocaleString("en-IN");
                        }
                    }
                }
            }
        }
    });
}

function renderRecentInvoices(invoices) {
    const tbody = document.getElementById("recent-invoices-tbody");
    if (!tbody) return;

    if (!invoices || invoices.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">No invoices found for this time period.</td></tr>`;
        return;
    }

    tbody.innerHTML = "";
    invoices.forEach(inv => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><strong>${inv.invoice_no}</strong></td>
            <td>${inv.date}</td>
            <td><span class="badge-pill">${inv.category}</span></td>
            <td>${inv.customer}</td>
            <td><strong>${formatINR(inv.grand_total)}</strong></td>
            <td>
                <button type="button" class="btn btn-xs btn-outline-primary" onclick="printUrlSilently('/invoice/${encodeURIComponent(inv.invoice_no)}/print')">Reprint</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function renderLowStock(items) {
    const tbody = document.getElementById("low-stock-tbody");
    if (!tbody) return;

    if (!items || items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="3" class="text-center text-muted">All stock levels healthy!</td></tr>`;
        return;
    }

    tbody.innerHTML = "";
    items.forEach(p => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><strong>${p.part_no}</strong></td>
            <td>${p.name}</td>
            <td class="stock-low"><strong>${p.stock_qty}</strong></td>
        `;
        tbody.appendChild(tr);
    });
}
