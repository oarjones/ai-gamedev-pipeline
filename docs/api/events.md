# Events over WebSocket

The gateway pushes real-time events to clients via WebSocket, segmented by project rooms.

- Endpoint: `/ws/events?project_id=<id>`
- Filtering: Connections must include `project_id`; events are only delivered for that project.
- Envelope contract:
  - `id: string (uuid)`
  - `type: "chat" | "action" | "update" | "scene" | "timeline" | "log" | "error"`
  - `project_id: string`
  - `payload: object` (type-specific)
  - `correlationId?: string` (optional tracing id)
  - `timestamp: string (ISO-8601)` (aka `ts`)

Examples

- Chat (agent):
```json
{
  "id": "...",
  "type": "chat",
  "project_id": "test-api-project",
  "payload": {"role": "agent", "content": "Hello", "msgId": "...", "correlationId": "..."},
  "correlationId": "...",
  "timestamp": "2025-01-01T12:00:00Z"
}
```

- Timeline step:
```json
{
  "id": "...",
  "type": "timeline",
  "project_id": "test-api-project",
  "payload": {"index": 0, "tool": "blender.export_fbx", "status": "success", "result": {"exported": "..."}, "correlationId": "..."},
  "correlationId": "...",
  "timestamp": "2025-01-01T12:00:01Z"
}
```

Notes
- Clients without `project_id` are rejected.
- `correlationId` helps tie together inputs and derived events.
- `timestamp` may be referenced as `ts` informally in docs; the field name is `timestamp`.

