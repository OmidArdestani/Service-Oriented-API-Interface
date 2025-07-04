# Multi-Provider Discovery System

This implementation allows multiple service providers to run on the same computer by implementing a provider registration and notification system.

## How It Works

### Primary Provider
- The first service provider to start successfully binds to the UDP discovery port
- Acts as the "discovery coordinator" for all providers on the machine
- Maintains a registry of secondary providers
- When receiving client discovery requests:
  1. Responds with its own service information
  2. Notifies all registered secondary providers
  3. Each secondary provider sends its own response directly to the client

### Secondary Providers
- When a provider cannot bind to the discovery port, it becomes a secondary provider
- Discovers and registers with the primary provider
- Listens for notifications from the primary provider
- When notified of a client discovery request, responds directly to the client
- Sends periodic heartbeats to maintain registration

## Message Types

New message types added for multi-provider support:

- `PROVIDER_DISCOVERY_REQUEST`: Secondary provider looking for primary
- `PROVIDER_DISCOVERY_RESPONSE`: Primary provider responding to discovery
- `PROVIDER_REGISTRATION`: Secondary provider registering with primary
- `PROVIDER_NOTIFICATION`: Primary notifying secondary of client request
- `PROVIDER_HEARTBEAT`: Secondary provider sending heartbeat to primary

## Key Features

1. **Automatic Fallback**: If port binding fails, automatically tries to register as secondary
2. **Health Monitoring**: Heartbeat system keeps track of active providers
3. **Direct Response**: Each provider responds directly to clients (no proxy)
4. **Fault Tolerance**: Stale providers are automatically cleaned up
5. **Transparent to Clients**: Clients use the same discovery mechanism

## Testing

### Running Multiple Providers
```bash
python test_multi_provider.py
```

This script will:
- Start 4 test service providers
- Show which one becomes primary and which register as secondary
- Display the status of all providers
- Keep running until interrupted

### Testing Discovery
```bash
python test_discovery_client.py
```

This script will:
- Send discovery requests like a real client
- Show all providers that respond
- Repeat the test multiple times

## Architecture Benefits

1. **Scalability**: Any number of providers can run on the same machine
2. **Resilience**: If primary provider shuts down, others remain functional (though discovery may be affected)
3. **Zero Client Changes**: Existing clients work without modification
4. **Autonomous Providers**: Each provider maintains control over its own responses
5. **Clean Separation**: Primary provider only coordinates, doesn't proxy data

## Implementation Details

### Provider Registration Flow
1. Secondary provider sends `PROVIDER_DISCOVERY_REQUEST` broadcast
2. Primary provider responds with `PROVIDER_DISCOVERY_RESPONSE`
3. Secondary provider sends `PROVIDER_REGISTRATION` to primary
4. Primary provider adds secondary to its registry

### Client Discovery Flow
1. Client sends `CLIENT_DISCOVERY_REQUEST` broadcast
2. Primary provider receives request
3. Primary provider sends its own `SERVICE_ADVERTISEMENT` to client
4. Primary provider sends `PROVIDER_NOTIFICATION` to all registered secondaries
5. Each secondary provider sends its own `SERVICE_ADVERTISEMENT` to client

### Health Monitoring
- Secondary providers send `PROVIDER_HEARTBEAT` every 30 seconds
- Primary provider removes providers that haven't sent heartbeat in 60 seconds
- This prevents stale registrations from accumulating

## Error Handling

- Socket binding failures are gracefully handled
- Network timeouts are managed appropriately
- Stale provider cleanup prevents memory leaks
- Graceful shutdown with proper unregistration
