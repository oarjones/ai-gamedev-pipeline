export interface Task {
    id: string | number;
    code: string;
    title: string;
    description: string;
    dependencies: string[];
    status: 'pending' | 'in_progress' | 'done' | 'blocked';
}

export interface TaskPlan {
    id: number;
    version: number;
    status: string;
    summary: string;
    created_by: string;
    created_at: string;
    stats: {
        total: number;
        completed: number;
        blocked: number;
        progress: number;
    };
    tasks: Task[];
}