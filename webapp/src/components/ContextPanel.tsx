import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiGet, apiPost } from '../lib/api';
import { useWebSocket } from '../hooks/useWebSocket';
import { format } from 'date-fns';
import { Context, TaskContext, HistoryItem, EditableListProps } from '../types';
export function ContextPanel({ project_id }: { project_id: string }) {
  const [activeTab, setActiveTab] = useState<'global' | 'task' | 'history'>('global');
  const [isEditing, setIsEditing] = useState(false);
  const [editedContext, setEditedContext] = useState<Context | null>(null);
  const queryClient = useQueryClient();

  const { data: globalContext, refetch } = useQuery<Context>({
    queryKey: ['context', project_id, 'global'],
    queryFn: () => apiGet(`/api/v1/context?project_id=${project_id}&scope=global`)
  });

  const { data: taskContext } = useQuery<TaskContext>({
    queryKey: ['context', project_id, 'task'],
    queryFn: () => apiGet(`/api/v1/context?project_id=${project_id}&scope=task`),
    enabled: !!globalContext?.current_task
  });

  const { data: contextHistory } = useQuery<HistoryItem[]>({
    queryKey: ['context-history', project_id],
    queryFn: () => apiGet(`/api/v1/context/history?project_id=${project_id}`),
    enabled: activeTab === 'history'
  });

  const { lastMessage } = useWebSocket(`/ws/events?project_id=${project_id}`);

  useEffect(() => {
    if (lastMessage?.type === 'context.updated' || lastMessage?.type === 'context.generated') {
      refetch();
    }
  }, [lastMessage, refetch]);

  const saveContext = useMutation({
    mutationFn: (context: Context) => 
      apiPost(`/api/v1/context?project_id=${project_id}`, { 
        content: context,
        scope: 'global'
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['context'] });
      setIsEditing(false);
    }
  });

  const generateContext = useMutation({
    mutationFn: (last_task_id: number) => 
      apiPost(`/api/v1/context/generate?project_id=${project_id}`, { last_task_id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['context'] });
    }
  });

  const handleEdit = () => {
    setEditedContext(globalContext || null);
    setIsEditing(true);
  };

  const handleSave = () => {
    if (editedContext) {
      saveContext.mutate(editedContext);
    }
  };

  const renderGlobalContext = () => {
    const ctx = isEditing ? editedContext : globalContext;
    if (!ctx) return <div>No context available.</div>;

    return (
      <div className="space-y-4">
        <div>
          <h3 className="font-medium text-sm text-gray-600 mb-1">Summary</h3>
          {isEditing ? (
            <textarea
              className="w-full border rounded p-2 h-24"
              value={ctx.summary}
              onChange={(e) => setEditedContext({ ...ctx, summary: e.target.value })}
            />
          ) : (
            <div className="prose prose-sm max-w-none"><pre>{ctx.summary}</pre></div>
          )}
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-green-50 rounded p-3">
            <div className="text-sm text-gray-600">Completed</div>
            <div className="text-2xl font-bold text-green-600">{ctx.done_tasks?.length || 0}</div>
          </div>
          <div className="bg-blue-50 rounded p-3">
            <div className="text-sm text-gray-600">Pending</div>
            <div className="text-2xl font-bold text-blue-600">{ctx.pending_tasks}</div>
          </div>
        </div>
        {ctx.current_task && (
          <div className="bg-yellow-50 border-l-4 border-yellow-400 p-3">
            <div className="text-sm font-medium">Current Task</div>
            <div className="text-lg">{ctx.current_task}</div>
          </div>
        )}
        <EditableList title="Decisions" items={ctx.decisions || []} isEditing={isEditing} onChange={(decisions) => setEditedContext({ ...ctx!, decisions })} />
        <EditableList title="Open Questions" items={ctx.open_questions || []} isEditing={isEditing} onChange={(open_questions) => setEditedContext({ ...ctx!, open_questions })} itemClass="text-orange-600" />
        <EditableList title="Risks" items={ctx.risks || []} isEditing={isEditing} onChange={(risks) => setEditedContext({ ...ctx!, risks })} itemClass="text-red-600" />
        <div className="text-xs text-gray-500 pt-2 border-t">
          <div>Version: {ctx.version}</div>
          {ctx.last_update && <div>Updated: {format(new Date(ctx.last_update), 'dd/MM/yyyy HH:mm')}</div>}
        </div>
      </div>
    );
  };

  return (
    <div className="bg-white rounded-lg shadow h-full flex flex-col">
      <div className="border-b">
        <div className="flex justify-between items-center p-4">
          <h2 className="text-lg font-semibold">Project Context</h2>
          <div className="flex gap-2">
            {!isEditing ? (
              <button className="btn btn-sm btn-secondary" onClick={handleEdit}>Edit</button>
            ) : (
              <>
                <button className="btn btn-sm btn-secondary" onClick={() => setIsEditing(false)}>Cancel</button>
                <button className="btn btn-sm btn-primary" onClick={handleSave}>Save</button>
              </>
            )}
          </div>
        </div>
        <div className="flex border-t">
          {(['global', 'task', 'history'] as const).map(tab => (
            <button key={tab} className={`px-4 py-2 text-sm font-medium capitalize ${activeTab === tab ? 'border-b-2 border-blue-500 text-blue-600' : 'text-gray-600 hover:text-gray-900'}`} onClick={() => setActiveTab(tab)}>
              {tab === 'global' ? 'Global' : tab === 'task' ? 'Current Task' : 'History'}
            </button>
          ))}
        </div>
      </div>
      <div className="flex-1 overflow-auto p-4">
        {activeTab === 'global' && renderGlobalContext()}
        {activeTab === 'task' && <TaskContextView context={taskContext} />}
        {activeTab === 'history' && <ContextHistory history={contextHistory} />}
      </div>
    </div>
  );
}

function EditableList({ title, items, isEditing, onChange, itemClass = '' }: EditableListProps) {
  const handleAdd = () => {
    const newItem = (items.length > 0 && typeof items[0] === 'object')
      ? { id: 0, description: "", mitigation: "" }
      : "";
    onChange([...items, newItem]);
  };

  const handleRemove = (index: number) => onChange(items.filter((_, i: number) => i !== index));
  
  const handleChange = (index: number, value: string) => {
    const newItems = [...items];
    const item = newItems[index];
    if (typeof item === 'object' && item !== null) {
      newItems[index] = { ...item, description: value };
    } else {
      newItems[index] = value;
    }
    onChange(newItems);
  };

  const getItemDisplay = (item: any) => {
    return typeof item === 'object' && item !== null ? item.description : item;
  }

  return (
    <div>
      <h3 className="font-medium text-sm text-gray-600 mb-2">{title}</h3>
      <ul className="space-y-1">
        {items.map((item: any, index: number) => (
          <li key={index} className="flex items-center gap-2">
            {isEditing ? (
              <>
                <input 
                  className="flex-1 border rounded px-2 py-1 text-sm" 
                  value={getItemDisplay(item)} 
                  onChange={(e) => handleChange(index, e.target.value)} 
                />
                <button className="text-red-500 text-sm" onClick={() => handleRemove(index)}>×</button>
              </>
            ) : (
              <span className={`text-sm ${itemClass}`}>• {getItemDisplay(item)}</span>
            )}
          </li>
        ))}
      </ul>
      {isEditing && <button className="text-sm text-blue-600 mt-2" onClick={handleAdd}>+ Add</button>}
    </div>
  );
}

function TaskContextView({ context }: { context?: TaskContext }) {
  if (!context) return <div className="text-gray-500">No task context available.</div>;
  return (
    <div className="space-y-4">
      <div>
        <h3 className="font-medium text-sm text-gray-600 mb-1">Task</h3>
        <div className="text-lg">{context.task_code}</div>
      </div>
      <div>
        <h3 className="font-medium text-sm text-gray-600 mb-1">Summary</h3>
        <p className="text-sm">{context.summary}</p>
      </div>
    </div>
  );
}

function ContextHistory({ history }: { history?: HistoryItem[] }) {
  if (!history || history.length === 0) return <div className="text-gray-500">No history available.</div>;
  return (
    <div className="space-y-2">
      {history.map((item) => (
        <div key={item.id} className="border rounded p-3">
          <div className="flex justify-between items-start">
            <div>
              <div className="font-medium">Version {item.version}</div>
              <div className="text-sm text-gray-600">{format(new Date(item.created_at), 'dd/MM/yyyy HH:mm')}</div>
            </div>
            <span className="text-xs bg-gray-100 px-2 py-1 rounded">{item.created_by}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
