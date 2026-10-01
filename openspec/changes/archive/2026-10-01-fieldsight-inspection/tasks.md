# Tasks

## 1. Measurements and agent

- [x] 1.1 Measure vest coverage, panel edge density, and warning-label regions with OpenCV 5, and verify fixture photos produce the expected CLEAR, HOLD, and ESCALATE decisions in pytest
- [x] 1.2 Branch ticket creation, SMS text, and the clearance note from those measurements, and verify a unit test flips the tool list when coverage or edge density changes

## 2. Storage and API

- [x] 2.1 Store each photo on a local S3 mock and behind boto3 when credentials exist, and verify the upload test writes bytes and returns an s3:// URI
- [x] 2.2 Expose health, sample list, sample inspect, and upload endpoints, and verify the API test covers a bad upload and an unknown sample

## 3. Demo UI and report

- [x] 3.1 Show fixtures, upload, overlay, metrics, and the tool trace in the Next.js app, and verify the page calls the proxied inspection API
- [x] 3.2 Write README, REPORT.md, and the MIT license, and verify the report covers problem, users, architecture, OpenCV, AWS, eval, limitations, and responsible use
