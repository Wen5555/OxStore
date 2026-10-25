# OxStore Selenium UI smoke tests

This is a standalone Java 17 + Selenium + JUnit 5 project. It drives a real
Chrome browser against the running OxStore frontend and backend; it does not
mock API responses.

The end-to-end scenario logs in as the seller, publishes a uniquely named test
product, submits and queries a buyer intent, processes it as the seller, and
checks that the sold product is no longer listed.

## Safety

The scenario changes application data and completes a sale. Run it only against
a disposable OxStore installation backed by an isolated test database. Each
run creates a product and a transaction record; the test does not delete those
records. Discard or recreate the test database after the run.

The test refuses to start unless `UI_SMOKE_ALLOW_MUTATIONS=true` and all
connection credentials are explicitly configured.

## Prerequisites

- JDK 17
- Maven 3.9+
- Chrome or Chromium installed
- A running OxStore frontend, backend, and isolated MySQL database
- A seller account in that database

Selenium Manager resolves the ChromeDriver for the installed browser. The
machine must be able to download the driver on first use, or have a compatible
driver already available.

## Run locally without Docker (Windows)

Docker is not required. The local OxStore backend uses MySQL, so a local MySQL
8 service must be running. Use a new, dedicated test database; do not point this
test at a development or production database. The scenario publishes and sells
a product, and the resulting rows are intentionally not deleted.

### 1. Create a disposable test database

The commands below assume the local MySQL account is `root`; change the
username if your local installation uses a different account. The timestamp
creates a fresh database name; copy the printed name for the backend
configuration below.

In PowerShell from the repository root:

```powershell
$dbName = "oxstore_ui_smoke_" + (Get-Date -Format "yyyyMMdd_HHmmss")
"Test database: $dbName"
mysql -u root -p -e "CREATE DATABASE $dbName CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"
if ($LASTEXITCODE -ne 0) { throw "Could not create the dedicated UI smoke database." }
cmd /c "mysql -u root -p --default-character-set=utf8mb4 $dbName < backend\src\main\resources\db\schema.sql"
if ($LASTEXITCODE -ne 0) { throw "Could not initialize the UI smoke database schema." }
```

MySQL prompts for the local MySQL password. Creating a new database avoids
touching any existing OxStore data.

### 2. Start the backend

Open a PowerShell terminal at the repository root. Enter your local MySQL
password and a new seller password for this disposable database when prompted:

```powershell
$dbPassword = Read-Host "Local MySQL password" -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($dbPassword)
try { $env:DB_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer) }
$env:DB_HOST = "localhost"
$env:DB_PORT = "3306"
$env:DB_NAME = Read-Host "Paste the timestamped test database name printed in step 1"
$env:DB_USERNAME = "root"
$random = [Security.Cryptography.RandomNumberGenerator]::Create()
$jwtBytes = New-Object byte[] 32
$lookupBytes = New-Object byte[] 32
$random.GetBytes($jwtBytes)
$random.GetBytes($lookupBytes)
$env:JWT_SECRET = [Convert]::ToBase64String($jwtBytes)
$env:TOKEN_LOOKUP_KEY = [Convert]::ToBase64String($lookupBytes)
$adminPassword = Read-Host "New test seller password (8-64 chars, letters, numbers, and symbols)" -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($adminPassword)
try { $env:ADMIN_INITIAL_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer) }

cd backend
mvn spring-boot:run
```

Keep this terminal running. On first startup, OxStore creates the `admin`
seller using `ADMIN_INITIAL_PASSWORD`; save that password for the Selenium run.
The frontend/API is not ready until the Spring Boot startup log reports that
the application has started.

### 3. Start the frontend

Open a second PowerShell terminal at the repository root:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev -- --host 127.0.0.1
```

Keep this terminal running. Vite serves the UI at
`http://127.0.0.1:5173` and proxies `/api` requests to the backend on port 8080.
Check readiness with:

```powershell
Invoke-WebRequest http://127.0.0.1:5173/
Invoke-WebRequest http://127.0.0.1:5173/api/products/current
```

### 4. Run the Selenium smoke test

Open a third PowerShell terminal at the repository root and set the same seller
password that was entered when the new database was first initialized:

```powershell
$env:UI_SMOKE_BASE_URL = "http://127.0.0.1:5173"
$env:UI_SMOKE_ADMIN_USERNAME = "admin"
$adminPassword = Read-Host "Test seller password" -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($adminPassword)
try { $env:UI_SMOKE_ADMIN_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer) }
$env:UI_SMOKE_ALLOW_MUTATIONS = "true"
$env:UI_SMOKE_HEADLESS = "false"

cd tests\ui-smoke
mvn test
```

With `UI_SMOKE_HEADLESS=false`, Chrome opens visibly while Selenium runs.
Selenium Manager resolves ChromeDriver automatically; first use requires
network access to download a driver compatible with the installed Chrome.
When the test passes, it reports `BUILD SUCCESS`. Failure screenshots and
browser logs are saved to `target/ui-smoke-artifacts/`.

If a run fails after it has created a product or started a trade, do not run it
again against that database: the interrupted scenario can leave active test
data behind. Initialize a fresh, dedicated test database from `schema.sql`
before retrying.

### If Selenium Manager cannot download ChromeDriver

If Maven stays at `Running ...OxStoreUiSmokeTest` and no test browser opens,
stop that run with Ctrl+C. Download the ChromeDriver whose version matches
the installed Chrome, extract `chromedriver.exe`, then configure its full path
before running Maven:

```powershell
$env:CHROME_DRIVER_PATH = "C:\tools\chromedriver-win64\chromedriver.exe"
mvn test
```

`CHROME_DRIVER_PATH` is optional; when set, it bypasses Selenium Manager.
Do not use a driver for a different Chrome major version.

After testing, stop the frontend and backend with Ctrl+C. Keep or remove the
dedicated database using your MySQL administration tool after confirming its
name and that you no longer need its test data.

## Run with Docker

This separate option is not needed for the local workflow above. If using the
Docker Compose deployment, the frontend is normally available at
`http://localhost`.

In PowerShell, set the required settings in the same terminal that runs Maven:

```powershell
$env:UI_SMOKE_BASE_URL = "http://localhost"
$env:UI_SMOKE_ADMIN_USERNAME = "admin"
$env:UI_SMOKE_ADMIN_PASSWORD = "<test seller password>"
$env:UI_SMOKE_ALLOW_MUTATIONS = "true"
$env:UI_SMOKE_HEADLESS = "true"

cd tests\ui-smoke
mvn test
```

Set `UI_SMOKE_HEADLESS=false` to watch the browser locally. Test artifacts on
failure are written to `tests/ui-smoke/target/ui-smoke-artifacts/`.

## Configuration

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `UI_SMOKE_BASE_URL` | Yes | — | Running frontend origin, e.g. `http://localhost` |
| `UI_SMOKE_ADMIN_PASSWORD` | Yes | — | Seller password for this isolated environment |
| `UI_SMOKE_ALLOW_MUTATIONS` | Yes | — | Must be `true` to enable this data-changing test |
| `UI_SMOKE_ADMIN_USERNAME` | No | `admin` | Seller username |
| `UI_SMOKE_HEADLESS` | No | `true` | Run Chrome headlessly |
| `CHROME_DRIVER_PATH` | No | — | Full path to a matching `chromedriver.exe`; bypasses Selenium Manager |
