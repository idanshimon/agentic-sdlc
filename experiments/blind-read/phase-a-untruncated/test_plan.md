# Contract Tests for Architecture

Since no specific architecture details were provided, I'll create 5 contract tests based on a **common microservices architecture** pattern (API Gateway → Service → Database). Please share your specific architecture for tailored tests.

---

## Contract Test 1: API Gateway → User Service

**Given** the API Gateway sends a `GET /users/{id}` request with a valid user ID and a valid Bearer token in the Authorization header

**When** the User Service receives the request

**Then** the User Service must return HTTP `200` with a JSON body containing `id` (string), `email` (string), `name` (string), and `createdAt` (ISO 8601 timestamp)

---

## Contract Test 2: API Gateway → User Service (Not Found)

**Given** the API Gateway sends a `GET /users/{id}` request with a user ID that does not exist in the system

**When** the User Service processes the request

**Then** the User Service must return HTTP `404` with a JSON body containing `error` (string) and `message` (string) — never a `500` or empty body

---

## Contract Test 3: Service → Database Write Contract

**Given** the Order Service constructs a valid order payload with `orderId`, `userId`, `items[]`, and `totalAmount`

**When** the Order Service writes the record to the Orders database

**Then** the database must persist all fields without truncation, return the generated `createdAt` timestamp, and confirm the write with no partial-save state

---

## Contract Test 4: Service-to-Service Event