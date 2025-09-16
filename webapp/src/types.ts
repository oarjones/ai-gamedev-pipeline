// ============================================
// Core Models (from gateway/app/models/core.py)
// ============================================

export enum EventType {
    // Basic events
    CHAT = "chat",
    ACTION = "action",
    UPDATE = "update",
    SCENE = "scene",
    TIMELINE = "timeline",
    LOG = "log",
    ERROR = "error",
    PROJECT = "project",

    // Plan events
    PLAN_GENERATED = "plan.generated",
    PLAN_REFINED = "plan.refined",
    PLAN_ACCEPTED = "plan.accepted",
    PLAN_EDITED = "plan.edited",

    // Task events
    TASK_STARTED = "task.started",
    TASK_PROGRESS = "task.progress",
    TASK_BLOCKED = "task.blocked",
    TASK_COMPLETED = "task.completed",

    // Context events
    CONTEXT_UPDATED = "context.updated",
    CONTEXT_GENERATED = "context.generated",

    // Artifact events
    ARTIFACT_CREATED = "artifact.created",
    ARTIFACT_VALIDATED = "artifact.validated"
}

export interface Envelope {
    id: string;
    type: EventType;
    project_id?: string;
    payload: Record<string, any>;
    correlation_id?: string;
    timestamp: string;
}

export interface Project {
    id: string;
    name: string;
    description?: string;
    status: string;
    created_at: string;
    updated_at: string;
    settings: Record<string, any>;
}

export interface CreateProject {
    name: string;
    description?: string;
    settings?: Record<string, any>;
}

// ============================================
// Task & Plan Models (from schemas.py & api_responses.py)
// ============================================

export interface Task {
    id?: string | number;
    code: string;
    title: string;
    description: string;
    dependencies: string[];
    status?: 'pending' | 'in_progress' | 'done' | 'blocked';
    priority?: number;
    mcp_tools?: string[];
    deliverables?: string[];
    acceptance_criteria?: string[];
    estimates?: Record<string, number>;
    tags?: string[];
}

export interface TaskSchema {
    code: string; // Pattern: T-XXX
    title: string;
    description: string;
    dependencies: string[];
    mcp_tools: string[];
    deliverables: string[];
    acceptance_criteria: string[];
    estimates: Record<string, number>;
    priority: number;
    tags: string[];
}

export interface TaskPlan {
    id: number;
    version: number;
    status: string;
    summary: string;
    created_by: string;
    created_at: string;
    stats?: {
        total: number;
        completed: number;
        blocked: number;
        progress: number;
    };
    tasks: Task[];
}

export interface TaskPlanSchema {
    plan_version: number;
    summary: string;
    tasks: TaskSchema[];
}

// ============================================
// Context Models
// ============================================

export interface Context {
    version: number;
    current_task: string | null;
    done_tasks: string[];
    pending_tasks: number;
    summary: string;
    decisions: string[];
    open_questions: string[];
    risks: string[];
    last_update?: string;
}

export interface TaskContext {
    task_code: string;
    summary: string;
}

export interface HistoryItem {
    id: number | string;
    version: number;
    created_at: string;
    created_by: string;
}

// ============================================
// Request Models (from router files)
// ============================================

export interface SendRequest {
    text: string;
}

export interface ChatSendRequest {
    text: string;
}

export interface AskOneShotRequest {
    sessionId: string;
    question: string;
}

export interface RefineRequest {
    instructions: string;
}

export interface EditPlanRequest {
    add?: Record<string, any>[];
    remove?: string[];
    update?: Record<string, any>[];
}

export interface ApplyChangesRequest {
    tasks?: Record<string, any>[];
    add?: Record<string, any>[];
    remove?: string[];
    update?: Record<string, any>[];
}

export interface ExecuteRequest {
    toolId: string;
    input: Record<string, any>;
}

export interface RegisterArtifactRequest {
    artifact_type: string;
    path: string;
    meta: Record<string, any>;
    category?: string;
}

export interface CreateContextRequest {
    content: Record<string, any>;
    scope: string;
    task_id?: number;
}

// ============================================
// Response Models
// ============================================

export interface ArtifactResponse {
    id: number;
    type: string;
    category?: string;
    path: string;
    size_bytes?: number;
    validation_status: string;
    meta: Record<string, any>;
    created_at: string;
}

// ============================================
// Tool Models
// ============================================

export interface ToolMeta {
    id: string;
    name: string;
    category: string;
    description?: string;
    schema: Record<string, any>;
}

export interface ToolSpec {
    name: string;
    description: string;
    parameters: Record<string, any>;
    examples: string[];
    safety: string[];
}

// ============================================
// Database Models (for reference)
// ============================================

export interface ChatMessage {
    id?: number;
    msg_id: string;
    project_id: string;
    role: string;
    content: string;
    created_at: string;
}

export interface TimelineEvent {
    id?: number;
    project_id: string;
    step_index: number;
    tool: string;
    args_json: string;
    status: string;
    result_json?: string;
    correlation_id?: string;
    started_at: string;
    finished_at?: string;
}

export interface Session {
    id?: number;
    project_id: string;
    provider: string;
    started_at: string;
    ended_at?: string;
    summary_text?: string;
}

export interface AgentMessage {
    id?: number;
    session_id: number;
    role: string;
    content: string;
    ts: string;
    tool_name?: string;
    tool_args_json?: string;
    tool_result_json?: string;
}

export interface Artifact {
    id?: number;
    session_id?: number;
    type: string;
    path: string;
    meta_json?: string;
    ts: string;
    task_id?: number;
    category?: string;
    validation_status: string;
    size_bytes?: number;
}

// ============================================
// Service Models
// ============================================

export interface ComponentStatus {
    name: string;
    running: boolean;
    endpoint_ok: boolean;
    detail: string;
}

export interface RunnerStatus {
    running: boolean;
    pid?: number;
    cwd?: string;
    agentType?: string;
    lastError?: string;
}

export interface StreamEvent {
    kind: string;
    data: Record<string, any>;
}

// ============================================
// UI Component Props (keep existing)
// ============================================

export interface EditableListProps {
    title: string;
    items: string[];
    isEditing: boolean;
    onChange: (newItems: string[]) => void;
    itemClass?: string;
}

// ============================================
// Configuration Models
// ============================================

export interface ServerConfig {
    host: string;
    port: number;
    reload: boolean;
}

export interface CorsConfig {
    allow_origins: string[];
    allow_credentials: boolean;
    allow_methods: string[];
    allow_headers: string[];
}

export interface ChatConfig {
    max_message_length: number;
    history_limit_default: number;
}

// ============================================
// WebSocket Message Types
// ============================================

export interface WSMessage {
    type: EventType;
    payload: any;
    project_id?: string;
    correlation_id?: string;
}

// ============================================
// Manifest Types
// ============================================

export interface ProjectManifest {
    name: string;
    description?: string;
    genre?: string;
    platform?: string;
    art_style?: string;
    target_audience?: string;
    core_mechanics?: string[];
    technical_requirements?: string[];
    scope?: string;
    [key: string]: any;
}