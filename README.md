# Architecture Overview

The system consists of four main components:

```markdown

┌─────────────────┐
│ CNC Devices     │
└────────┬────────┘
         │ TCP Packets
         ▼
┌─────────────────┐
│ Async TCP Server│
│ (main.py)       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Decoder Engine  │
│ (decoder.py)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Queue Buffer    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ SQLite WAL DB   │
└────────┬────────┘
         │
         ├────────────► Flask Dashboard
         │                 (dashboard.py)
         │
         └────────────► Reporting & Excel Export
```

## Packet Processing Pipeline

Incoming packets follow the workflow below:

### 1. TCP Connection Establishment

A CNC board connects to the TCP server. The server:

- Registers the connection
- Updates dashboard status
- Marks the board as online
- Tracks active connections per IP

### 2. Stream Buffering

TCP is stream-based and does not guarantee packet boundaries. To avoid corrupted packet parsing:

- Incoming bytes are accumulated in a dedicated buffer.
- The server continuously searches for a valid packet header.
- Partial packets remain in the buffer until enough bytes arrive.

This prevents:

- Packet fragmentation issues
- Incomplete packet decoding
- Stream synchronization errors

### 3. Packet Validation

Each packet is validated using:

- Magic Header
- Packet ID
- Payload Length
- Payload Data

The server calculates the total packet size before processing. Packets are ignored until fully received. This protects against:

- Truncated packets
- Invalid payload lengths
- Network transmission anomalies

### 4. Packet Decoding

Decoded packet types include:

| ID   | Description            |
|------|------------------------|
| 0x01 | Production Start       |
| 0x02 | Production Counter     |
| 0x03 | Machine Stop Event     |
| 0x04 | Scrap/Rework Report    |
| 0x05 | Forms Information      |

The decoder extracts structured information from raw binary payloads and converts them into JSON-compatible objects.

### 5. Dashboard Update

After decoding:

- Device status is updated
- Last packet type is recorded
- Last activity timestamp is refreshed
- Session logs are updated

Dashboard data remains completely independent from database operations.

### 6. Queue-Based Persistence

Instead of writing directly to the database:

```text
Packet
   ↓
Memory Queue
   ↓
Background DB Worker
   ↓
SQLite
```

This design prevents database operations from blocking packet reception.

**Benefits:**

- Higher throughput
- Lower latency
- Better scalability
- Reduced packet loss risk

### 7. Batch Database Writes

The DB worker collects up to 100 records before insertion.

**Benefits:**

- Fewer disk operations
- Faster database performance
- Reduced SQLite locking

## Reliability and Fault-Tolerance Mechanisms

### Connection Health Monitoring

A periodic health checker runs every second. The checker:

- Sends keep-alive bytes
- Detects dead sockets
- Removes disconnected clients
- Updates dashboard status

This prevents stale connections from remaining active.

### Multi-Connection IP Tracking

The system maintains a connection counter per IP address. A device is considered offline only when:

```
Active Connections = 0
```

This avoids false disconnect events when multiple sockets are used by the same board.

### Stream Re-Synchronization

If a valid packet header is not found:

- Old bytes are discarded
- The last possible header bytes are retained

This mechanism allows automatic recovery from:

- Corrupted streams
- Noise bytes
- Misaligned packets

...without restarting the server.

### SQLite WAL Mode

The database operates in:

```sql
PRAGMA journal_mode=WAL;
```

**Advantages:**

- Better concurrent access
- Faster writes
- Reduced locking
- Improved crash recovery

### Producer-Consumer Pattern

The application implements a Producer-Consumer architecture:

- **Producer:** TCP Server
- **Consumer:** Database Worker Thread

**Benefits:**

- Decoupled processing
- Stable performance under burst traffic
- Improved responsiveness

### Thread Isolation

The application separates critical workloads:

| Component          | Execution Model     |
|--------------------|---------------------|
| TCP Server         | AsyncIO             |
| Dashboard          | Dedicated Thread    |
| Database Worker    | Dedicated Thread    |
| Network Watchdog   | Independent Process |

This prevents one subsystem from blocking another.

## Network Watchdog

The project includes an independent network monitoring service.

**Responsibilities:**

- Periodically ping all CNC boards
- Detect large-scale network outages
- Detect network recovery events
- Insert recovery markers into the database

### Outage Detection Strategy

The watchdog does not require every device to be online. Instead, configurable thresholds are used.

```
If many boards become unreachable:
    Network = DOWN

If enough boards return:
    Network = UP
```

This approach avoids false alarms caused by:

- Individual machine shutdowns
- Maintenance operations
- Device reboots

### Recovery Marker Injection

When network connectivity is restored:

```
Packet ID = 400
```

is automatically inserted into the database. This marker can later be used by analytics and reporting systems to:

- Detect communication gaps
- Rebuild production timelines
- Handle delayed packets correctly

## Performance Characteristics

- **Non-Blocking Architecture:** The server never waits for database operations while receiving packets.
- **Asynchronous Networking:** Uses Python AsyncIO for handling multiple CNC devices simultaneously.
- **Batched Persistence:** Database writes are grouped to minimize I/O overhead.
- **Memory-Based Queueing:** Temporary spikes in incoming traffic can be absorbed without packet loss.

## Known Limitations

- SQLite may become a bottleneck under very high throughput.
- Database path is currently hardcoded.
- Device IP list in the watchdog is manually maintained.
- No authentication layer is currently implemented for TCP clients.
- No TLS encryption is used for CNC communications.
