# Contract Tests

---

## Contract Test 1

**Given** a valid request payload is sent to the API endpoint
**When** the consumer submits a POST request with all required fields
**Then** the provider returns a `201 Created` status code with the expected response schema containing the required fields

---

## Contract Test 2

**Given** the consumer expects a specific response structure from the provider
**When** a GET request is made to retrieve a resource by ID
**Then** the provider returns a `200 OK` response with a body that matches the agreed-upon JSON schema, including all mandatory fields and correct data types

---

## Contract Test 3

**Given** an invalid or malformed request is sent to the provider
**When** the consumer submits a request with missing required fields
**Then** the provider returns a `400 Bad Request` status code with an error response body matching the agreed error schema

---

## Contract Test 4

**Given** a resource does not exist on the provider side
**When** the consumer sends a GET request for a non-existent resource ID
**Then** the provider returns a `404 Not Found` status code with an error message body conforming to the agreed contract

---

## Contract Test 5

**Given** the consumer is authenticated with a valid token
**When** a DELETE request is made to remove an existing resource
**Then** the provider returns a `204 No Content` status code with no response body, confirming the deletion contract is honored