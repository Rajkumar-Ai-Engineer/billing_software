# Sri Dhanam Motors - Billing & Inventory Application

The complete FastAPI web application has been built in the [`sdm_billing/`](./sdm_billing) directory according to the specifications in [`website_build_prompt.md`](./website_build_prompt.md).

## Quick Start

### 1. Navigate into the application folder:
```bash
cd sdm_billing
```

### 2. Run the application:
```bash
uvicorn main:app --reload
```

### 3. Open in browser:
- Application: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- Interactive API Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 4. Run automated test suite:
```bash
pytest tests -v
```

For full setup details, TVS LP 46 thermal barcode printer installation, calibration, and architecture documentation, see the [sdm_billing/README.md](./sdm_billing/README.md).
