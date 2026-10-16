# RabbitMQ 4.1.0: Selective Message Move/Purge by ID Architecture & Technical Report

This document delivers the technical investigation, feasibility assessment, ordering guarantee analysis, failure-recovery strategy, and API design for selectively moving or deleting (purging) a specific message from a RabbitMQ 4.1.0 queue by its message ID while preserving the original relative order of all remaining messages.

---

## 1. Feasibility Assessment & RabbitMQ 4.1.0 Realities

### 1.1 Can RabbitMQ Randomly Access Messages by ID?
**No.** RabbitMQ queues are strictly FIFO data structures (with priority or quorum variants). Neither the AMQP protocol (0-9-1, 1.0) nor the RabbitMQ Management HTTP API provides an index or random-access delete/fetch operation by `message_id`.

To locate and operate on a message by ID without draining manually, an application must inspect messages from the queue head sequentially.

### 1.2 Behavior and Side Effects of the Management HTTP API
The Management HTTP API exposes:
```http
POST /api/queues/{vhost}/{name}/get
```
Key behaviors and limitations:
1. **`ackmode: ack_requeue_true`**: Fetches up to $N$ messages, but requeues them immediately back into the queue.
   - *Limitation:* It cannot selectively acknowledge one message while leaving others intact within the same HTTP request.
   - *Side effect:* Requeued messages return to the head of classic queues, but if consumers are active, requeueing can alter concurrent processing order.
2. **`ackmode: ack_requeue_false`**: Consumes messages destructively from the queue.
   - *Limitation:* If an HTTP connection drops mid-flight or the application crashes before republishing, consumed messages are permanently lost.
3. **HTTP Overhead & Payload Limits:** Fetching large batches via HTTP encodes payloads as Base64, inflating memory and CPU consumption on the Erlang VM. It is not designed for streaming queue migration.

### 1.3 Queue Types Comparison in RabbitMQ 4.1.0

| Feature | Classic Queues | Quorum Queues (Raft) | Streams |
| :--- | :--- | :--- | :--- |
| **Storage Engine** | Mnesia / Khepri + message store | Raft log (replicated consensus) | Append-only commit log |
| **Selective Delete** | Supported via temp queue shuffle | Supported via temp queue shuffle | **Impossible** (immutable log) |
| **Requeue Behavior** | Requeues to head | Requeues to tail/head based on redelivery | Read-only offset pointer |
| **Poison Message Handling** | Manual | `x-delivery-limit` (dead-letters after $N$ attempts) | Not applicable |
| **Recommended Strategy** | Temporary queue drain + restore | Temporary queue drain + restore | Offset consumer group filtering |

---

## 2. Recommended Solution Architecture

To address the constraints of RabbitMQ 4.1.0, the solution adopts a **Hybrid Control Plane (HTTP Management API) + High-Performance Data Plane (AMQP 0-9-1 Streaming Client)**:

```
┌────────────────────────────────────────────────────────┐
│                   Web Interface (React)                │
│    - Real-time Stage Stepper & SSE Event Log           │
│    - Interactive Queue & Message ID Inspector          │
└──────────────────────────┬─────────────────────────────┘
                           │ SSE & REST JSON
┌──────────────────────────▼─────────────────────────────┐
│             FastAPI Backend Orchestrator               │
│  - Distributed Mutex Lock per queue                    │
│  - Write-Ahead Journal (Crash & Rollback State)        │
│  - AMQP Worker with Publisher Confirms                 │
│  - RabbitMQ Management API Client                      │
└──────────────┬───────────────────────────┬─────────────┘
               │ HTTP Mgmt API             │ AMQP 0-9-1 (Confirmed)
┌──────────────▼───────────────────────────▼─────────────┐
│                    RabbitMQ 4.1.0                      │
│                                                        │
│  Phase 1: Divert live producers -> [Ingress Buffer]    │
│  Phase 2: [Source Queue]   ───(drain)───> [Temp 1]     │
│  Phase 3: [Temp 1] ───(filter by ID)───> [Temp 2]      │
│                     └──(target match)───> [Destination]│
│  Phase 4: [Temp 2]         ──(restore)──> [Source]     │
│  Phase 5: [Ingress Buffer] ──(append)───> [Source]     │
└────────────────────────────────────────────────────────┘
```

### 2.1 The 4-Phase Temporary Queue Strategy + Live Traffic Buffer

#### Phase 1: Ingress Isolation & Preparation
1. The orchestrator acquires a mutex lock on the `source_queue` (and `destination_queue` if Move) in the journal.
2. Temporary queues are declared:
   - `rmq_tmp1_{op_id}` (durable)
   - `rmq_tmp2_{op_id}` (durable)
   - `rmq_buf_{op_id}` (durable, ingress buffer)
3. If live producers are active, existing exchange bindings to `source_queue` are cloned to `rmq_buf_{op_id}`, and the source bindings are temporarily suspended. New incoming messages accumulate safely in `rmq_buf_{op_id}` without interleaving.

#### Phase 2: Draining Source to Temp 1
- The AMQP worker drains all messages from `source_queue` into `rmq_tmp1_{op_id}` sequentially.
- **Zero Loss Invariant:** Each message is published to `rmq_tmp1_{op_id}` with `delivery_mode=2` (persistent) and publisher confirm received before the source delivery tag is acknowledged (`basic.ack`).

#### Phase 3: Filtering & Routing from Temp 1 to Temp 2
- The worker reads from `rmq_tmp1_{op_id}` in FIFO sequence.
- For each message, its identifier is inspected against `target_message_id` (checking `properties.message_id`, custom header keys, correlation ID, or JSON payload `id`).
- **If Target ID matches:**
  - **DELETE operation:** The message is acknowledged from `rmq_tmp1_{op_id}` without publishing.
  - **MOVE operation:** The message is published to `destination_queue`, publisher confirm is verified, and then acknowledged from `rmq_tmp1_{op_id}`.
- **If Non-target:** The message is published to `rmq_tmp2_{op_id}`, confirmed, and acknowledged.

#### Phase 4: Restoring Source Queue
- All messages in `rmq_tmp2_{op_id}` are transferred back into `source_queue` in exact FIFO sequence with publisher confirms.

#### Phase 5: Flushing Buffer & Restoring Bindings
- Original exchange bindings are restored to `source_queue`.
- All messages accumulated in `rmq_buf_{op_id}` are drained into `source_queue` (appended after the restored messages).
- Temporary queues (`rmq_tmp1_{op_id}`, `rmq_tmp2_{op_id}`, `rmq_buf_{op_id}`) are deleted.
- Operation lock is released.

---

## 3. Failure-Recovery & Resilience Strategy

### 3.1 Crash Scenarios & Rollback Invariants

| Failure Point | State on Crash | Recovery Procedure |
| :--- | :--- | :--- |
| **Crash during Phase 2 (Draining)** | Part of messages in `source`, part in `Temp 1`. Unacked message is redelivered to `source`. | Rollback drains `Temp 1` back into `source`. Zero message loss. |
| **Crash during Phase 3 (Filtering)** | Target message may or may not be processed yet. Non-targets are in `Temp 2`, remaining in `Temp 1`. | Rollback drains both `Temp 1` and `Temp 2` back into `source`. |
| **Crash during Phase 4 (Restoring)** | Part of messages restored in `source`, remainder in `Temp 2`. | Rollback resumes draining remainder from `Temp 2` into `source`. |
| **Server Restart with Interrupted Ops** | Journal detects operations with `status: RUNNING`. | Marks operation as `RECOVERY_REQUIRED`, maintains queue locks, alerts user on UI with 1-click **Rollback to Source**. |

---

## 4. Ordering Guarantees

### What RabbitMQ Guarantees:
- **FIFO within a single channel:** RabbitMQ guarantees that messages published on a single channel to an exchange and routed to a single queue will arrive in the same order.
- **Single active consumer:** Messages delivered to a single consumer on a queue are delivered in strict FIFO order.

### What the Implementation Guarantees:
- **Deterministic ordering:** Because a single AMQP channel and consumer drains `source -> Temp 1 -> Temp 2 -> source`, relative ordering among all non-target messages is strictly preserved.
- **No interleaving:** The ingress buffer queue ensures that concurrent producer messages are not mixed in the middle of the restored batch, but appended immediately after.

### Potential Ordering Caveats:
- **Active competing consumers:** If external consumers consume from `source_queue` while it is being drained, they will consume arbitrary subsets of messages before the target is reached. **Requirement:** Pause external consumers before executing the operation.
- **Queue priority:** Classic queues configured with `x-max-priority` re-order messages by priority. Priority ordering is maintained because messages are re-published with their original `priority` properties intact.

---

## 5. API-Level Implementation Specification

### 5.1 Management HTTP API Endpoints Used
- `GET /api/overview`: Health & cluster discovery.
- `GET /api/queues/{vhost}`: Queue metrics, consumer count, type.
- `GET /api/queues/{vhost}/{name}`: Queue details and state.
- `POST /api/queues/{vhost}/{name}/get`: Non-destructive sample inspection (`ackmode: ack_requeue_true`).
- `PUT /api/queues/{vhost}/{name}`: Declare temporary queues.
- `DELETE /api/queues/{vhost}/{name}`: Clean up temporary queues.
- `GET /api/queues/{vhost}/{name}/bindings`: Extract exchange bindings for traffic isolation.
- `POST /api/bindings/{vhost}/e/{exchange}/q/{queue}`: Divert/restore bindings.
- `DELETE /api/bindings/{vhost}/e/{exchange}/q/{queue}/{props_hash}`: Remove bindings during buffer phase.

### 5.2 Application Backend REST & SSE Endpoints
- `GET /api/config`: Retrieve current RabbitMQ configuration.
- `PUT /api/config`: Update RabbitMQ host/credentials.
- `POST /api/config/test`: Test HTTP and AMQP broker connections.
- `GET /api/queues`: List queues with message counts, lock status, consumer warnings.
- `GET /api/queues/{queue}/sample`: Non-destructive head inspection.
- `POST /api/operations`: Trigger Move or Delete operation.
- `GET /api/operations`: List historical operations.
- `GET /api/operations/{op_id}`: Get operation status and live metrics.
- `GET /api/operations/{op_id}/events`: Server-Sent Events (SSE) live progress stream.
- `POST /api/operations/{op_id}/recover`: Trigger manual Rollback or Discard.
- `GET /api/system/status`: Broker health, locked queues, pending recoveries.
