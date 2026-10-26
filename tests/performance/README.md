# OxStore JMeter API load test

This plan exercises the backend API directly (not the browser/frontend): read
the current product, submit a uniquely named buyer intent, then query it back.
The assertions verify the API success envelope, required active product,
extracted token, and persisted `QUEUING` intent.

The plan writes test intents and does not cancel them. Use only a disposable
OxStore test database, never production or a shared development database.
The initial profile is intentionally small: 5 virtual users, 10-second ramp-up,
5 iterations per user (25 submitted intents; 75 API samples). Check server and
database health while it runs.

## Prerequisites

- Java 17 or newer
- Apache JMeter 5.6.3 or later
- OxStore backend started against a dedicated MySQL 8 test database
- One current product in `ONLINE` or `RESTORED_ONLINE` state
- No other load test or user flow changing the product/intent queue during the run

JMeter is a separate application from Maven and Selenium. On Windows, download
the binary ZIP from the official [Apache JMeter download page](https://jmeter.apache.org/download_jmeter.cgi),
extract it (for example, to `C:\tools\apache-jmeter-5.6.3`), and use its `bin\jmeter.bat`.
No Docker is required. JMeter does not need a database password for this plan.

## Prepare the test application

The successful Selenium smoke flow sells its test product. Before running this
plan, start the backend with the disposable test database and publish a fresh
test product using the seller UI. Confirm the public current-product API returns
an object, not `data: null`:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/api/products/current
```

Expected shape: `code` is `0` and `data` contains the product. If `data` is
`null`, publish a test product before starting JMeter.

The test database must already contain the OxStore schema and initialized
seller. Do not point JMeter at a database containing real business data.

## Run a small GUI test

Open PowerShell from the repository root (adjust the extracted JMeter path):

```powershell
& "C:\tools\apache-jmeter-5.6.3\bin\jmeter.bat" `
  -t "tests\performance\oxstore-api-load.jmx" `
  -Jhost=127.0.0.1 -Jport=8080 -Jprotocol=http `
  -Jthreads=5 -Jramp=10 -Jloops=5
```

JMeter starts in GUI mode and opens the test plan. Click the green **Start**
button. Watch **Summary Report** and **View Results Tree** is intentionally not
included to avoid retaining every response in memory. The JMX plan includes a
Summary Report listener; request details are checked through assertion errors
and can be inspected by adding a temporary View Results Tree only for a single
virtual user and one loop.

## Run non-GUI and create an HTML report

For repeatable measurements, use non-GUI mode. Choose a new, empty output
directory for each run:

```powershell
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$results = "outputs\jmeter-$stamp.jtl"
$report = "outputs\jmeter-report-$stamp"

& "C:\tools\apache-jmeter-5.6.3\bin\jmeter.bat" `
  -n -t "tests\performance\oxstore-api-load.jmx" `
  -Jhost=127.0.0.1 -Jport=8080 -Jprotocol=http `
  -Jthreads=5 -Jramp=10 -Jloops=5 `
  -l $results -e -o $report

if ($LASTEXITCODE -ne 0) { throw "JMeter failed with exit code $LASTEXITCODE. Inspect the JTL and JMeter log." }
```

The HTML report is written under the new `outputs\jmeter-report-<timestamp>`
directory; the raw sample results are in the `.jtl` file. Keep both if you need
to submit or compare the result. Never reuse a non-empty HTML report directory.

## Safe staged load

Begin with the 5-user profile. If the app and MySQL remain healthy and there are
no assertion or HTTP errors, use a **fresh test database** for each higher-load
run (for example, 10 users × 5 loops, then 20 × 5). Only change one parameter
at a time. Stop increasing load if errors appear, response times rise sharply,
or the database/server shows resource pressure.

Each run creates `threads × loops` intents and leaves them in the queue. Create
a new dedicated database/schema and publish a fresh product before another run;
do not repeatedly grow the same test queue. The current-product invariant
allows only one active product.

## Interpret results

Review the HTML report's throughput, error percentage, and response-time
percentiles (especially p95), and compare them with backend logs and MySQL CPU,
connections, and resource use. `0` failed assertions/requests is a functional
prerequisite, not a universal performance SLA. Set explicit latency, throughput,
and error-rate acceptance targets before claiming a performance pass; the
appropriate values depend on the deployment resources and expected traffic.

## Agreed acceptance targets

For this local test profile, the agreed initial targets are:

| Sampler | p95 limit | Maximum error rate |
| --- | ---: | ---: |
| Browse current product | 300 ms | 0% |
| Submit unique buyer intent | 1000 ms | 0% |
| Query submitted intent | 500 ms | 0% |

These are local test acceptance values, not a production capacity guarantee.
Validate a generated report with:

```powershell
powershell -ExecutionPolicy Bypass -File tests\performance\validate-jmeter-sla.ps1 `
  -ReportDirectory "outputs\jmeter-report-<timestamp>"
```

The validator reads JMeter `statistics.json`, checks the per-sampler p95 and
error-rate targets, prints sample counts/mean/p95/p99, and exits non-zero when
a target fails or an expected sampler is absent.

## Concurrent queue correctness check

This scenario verifies that 20 simultaneous unique buyer submissions all
succeed, can be queried back by their own returned tokens, and are persisted as
20 `QUEUING` intents with unique contiguous queue sequence values. It uses the
same JMX flow, but uses a fresh dedicated database with exactly one active
product and no pre-existing purchase intents.

Use a **separate fresh test database** for this correctness scenario. The
previous load runs have already added intents to their database; do not run
this exact-count check against that database.

1. Initialize a fresh OxStore test schema and start the backend against it.
2. Publish one test product. Confirm the active product API is successful.
3. From the repository root run the JMX with 20 threads, no ramp delay, and one
   iteration (one submission per virtual user):

   ```powershell
   $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
   $results = "outputs\jmeter-concurrency-$stamp.jtl"
   $report = "outputs\jmeter-concurrency-report-$stamp"

   & "C:\tools\apache-jmeter-5.6.3\bin\jmeter.bat" `
     -n -t "tests\performance\oxstore-api-load.jmx" `
     -Jthreads=20 -Jramp=0 -Jloops=1 `
     -l $results -e -o $report

   if ($LASTEXITCODE -ne 0) { throw "JMeter concurrency run failed: $LASTEXITCODE" }
   ```

   Require exactly 60 samples (20 users × 1 iteration × 3 requests) and 0
   errors in the JMeter summary. The response assertions require every product
   read, submission, and token-based read-back to succeed.
4. With the MySQL command-line client, query the same fresh database:

   ```powershell
   cmd /c "mysql -u root -p --default-character-set=utf8mb4 <database_name> < tests\performance\concurrency-invariants.sql"
   ```

   Require exactly one result row with `intent_count=20`,
   `distinct_queue_sequences=20`, `first_queue_sequence=1`,
   `last_queue_sequence=20`, `non_queuing_intents=0`, and
   `invariant_result=PASS`.

The scenario writes 20 intents and does not clean them up. Retain this database
as evidence or discard it after confirming its name and that no data needs to
be kept. Never run the fixed-count SQL invariant against a reused database.
