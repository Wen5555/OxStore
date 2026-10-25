# OxStore API negative checks

Run these checks against a locally running OxStore backend:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File tests\api-negative\verify-api-negative.ps1
```

Override the backend URL when needed:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File tests\api-negative\verify-api-negative.ps1 `
  -BaseUrl http://127.0.0.1:8080
```

The script checks missing and malformed JWTs, rejected invalid buyer input,
unknown intent tokens for query/modify/cancel, and unsupported HTTP methods. It
uses only rejected requests and read-only endpoints; it does not create or
modify business records.

Scenarios that require changing product state (no active product or a frozen/
sold product) are intentionally not included. Run those against a separate,
disposable test database with explicitly prepared product states.
