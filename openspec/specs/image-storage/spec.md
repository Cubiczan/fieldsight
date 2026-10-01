# image-storage Specification

## Purpose

Keep every inspection photo in an S3-shaped location so the local demo and an AWS deploy share one path.

## Requirements

### Requirement: Store the inspected photo
The system MUST store each inspected image and return an `s3://` URI that the clearance note also records.

#### Scenario: No cloud credentials
- **WHEN** an inspection runs without an S3 bucket and access key configured
- **THEN** the image bytes are written to local disk and the URI uses the local bucket name

#### Scenario: Credentials configured
- **WHEN** an S3 bucket and access key are configured
- **THEN** the image is uploaded to that bucket and the URI names that bucket

### Requirement: Result object beside an S3 upload
A production object-created handler MUST run the same inspection on a new photo and write a JSON result next to that object.

#### Scenario: Result object is not reprocessed
- **WHEN** the created object key already ends in the inspection result suffix
- **THEN** the handler skips it
