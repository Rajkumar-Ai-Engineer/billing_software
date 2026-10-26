from datetime import datetime, date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models import Invoice, Product, DailyExpense, PurchaseInvoice
import config

router = APIRouter()
templates = Jinja2Templates(directory=str(config.TEMPLATES_DIR))


@router.get("/", response_class=HTMLResponse)
def get_dashboard_page(request: Request, db: Session = Depends(get_db)):
    today_str = date.today().strftime("%Y-%m-%d")
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "active_page": "dashboard",
            "today_date": today_str,
            "shop_name": config.SHOP_NAME,
            "shop_tagline": config.SHOP_TAGLINE
        }
    )


@router.get("/api/dashboard")
def get_dashboard_data(
    period: str = "daily",
    target_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    try:
        ref_date = datetime.strptime(target_date, "%Y-%m-%d").date() if target_date else date.today()
    except ValueError:
        ref_date = date.today()

    if period == "weekly":
        d_start = ref_date - timedelta(days=6)
        d_end = ref_date
    elif period == "monthly":
        d_start = date(ref_date.year, ref_date.month, 1)
        # Next month start minus 1 day
        if ref_date.month == 12:
            next_m = date(ref_date.year + 1, 1, 1)
        else:
            next_m = date(ref_date.year, ref_date.month + 1, 1)
        d_end = next_m - timedelta(days=1)
    elif period == "custom" and start_date and end_date:
        try:
            d_start = datetime.strptime(start_date, "%Y-%m-%d").date()
            d_end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            d_start = ref_date
            d_end = ref_date
    else:  # daily
        d_start = ref_date
        d_end = ref_date

    invoices = (
        db.query(Invoice)
        .filter(Invoice.date >= d_start, Invoice.date <= d_end)
        .order_by(Invoice.date.desc(), Invoice.id.desc())
        .all()
    )

    total_sales = 0.0
    total_gst = 0.0
    count_invoices = len(invoices)

    cat_stats = {
        "Spare Parts": {"sales": 0.0, "gst": 0.0, "count": 0},
        "Service": {"sales": 0.0, "gst": 0.0, "count": 0},
        "Vehicle Sales": {"sales": 0.0, "gst": 0.0, "count": 0}
    }

    # Chart timeline setup
    date_points = []
    curr = d_start
    while curr <= d_end:
        date_points.append(curr.strftime("%Y-%m-%d"))
        curr += timedelta(days=1)

    chart_series = {
        "Spare Parts": {d: 0.0 for d in date_points},
        "Service": {d: 0.0 for d in date_points},
        "Vehicle Sales": {d: 0.0 for d in date_points}
    }

    for inv in invoices:
        g_tot = float(inv.grand_total)
        gst_tot = float(inv.gst_amount)
        total_sales += g_tot
        total_gst += gst_tot

        cat = inv.category
        if cat in cat_stats:
            cat_stats[cat]["sales"] += g_tot
            cat_stats[cat]["gst"] += gst_tot
            cat_stats[cat]["count"] += 1

        d_str = inv.date.strftime("%Y-%m-%d")
        if cat in chart_series and d_str in chart_series[cat]:
            chart_series[cat][d_str] += g_tot

    # Format chart data
    chart_data = {
        "labels": date_points,
        "datasets": [
            {
                "label": "Spare Parts",
                "borderColor": "#2E7D32",
                "backgroundColor": "rgba(46, 125, 50, 0.2)",
                "data": [round(chart_series["Spare Parts"][d], 2) for d in date_points]
            },
            {
                "label": "Service",
                "borderColor": "#2B6CB0",
                "backgroundColor": "rgba(43, 108, 176, 0.2)",
                "data": [round(chart_series["Service"][d], 2) for d in date_points]
            },
            {
                "label": "Vehicle Sales",
                "borderColor": "#E53E3E",
                "backgroundColor": "rgba(229, 62, 62, 0.2)",
                "data": [round(chart_series["Vehicle Sales"][d], 2) for d in date_points]
            }
        ],
        "category_pie": {
            "labels": ["Spare Parts", "Service", "Vehicle Sales"],
            "data": [
                round(cat_stats["Spare Parts"]["sales"], 2),
                round(cat_stats["Service"]["sales"], 2),
                round(cat_stats["Vehicle Sales"]["sales"], 2)
            ]
        }
    }

    # Recent Invoices
    recent_invoices = [
        {
            "invoice_no": inv.invoice_no,
            "date": inv.date.strftime("%Y-%m-%d"),
            "category": inv.category,
            "customer": inv.customer_name or "Cash Customer",
            "grand_total": round(float(inv.grand_total), 2),
            "gst_mode": inv.gst_mode
        }
        for inv in invoices[:15]
    ]

    # Low Stock Products (Stock <= 3)
    low_stock = (
        db.query(Product)
        .filter(Product.stock_qty <= 3)
        .order_by(Product.stock_qty.asc())
        .limit(20)
        .all()
    )

    low_stock_list = [p.to_dict() for p in low_stock]

    # Calculate period expenses & inward purchases
    period_expenses = float(
        db.query(func.coalesce(func.sum(DailyExpense.price), 0.0))
        .filter(DailyExpense.date >= d_start, DailyExpense.date <= d_end)
        .scalar() or 0.0
    )
    period_purchases = float(
        db.query(func.coalesce(func.sum(PurchaseInvoice.price), 0.0))
        .filter(PurchaseInvoice.received_date >= d_start, PurchaseInvoice.received_date <= d_end)
        .scalar() or 0.0
    )

    return {
        "period": period,
        "start_date": str(d_start),
        "end_date": str(d_end),
        "total_sales": round(total_sales, 2),
        "total_gst": round(total_gst, 2),
        "total_expenses": round(period_expenses, 2),
        "total_purchases": round(period_purchases, 2),
        "count_invoices": count_invoices,
        "categories": {
            k: {
                "sales": round(v["sales"], 2),
                "gst": round(v["gst"], 2),
                "count": v["count"]
            }
            for k, v in cat_stats.items()
        },
        "chart": chart_data,
        "recent_invoices": recent_invoices,
        "low_stock": low_stock_list
    }
