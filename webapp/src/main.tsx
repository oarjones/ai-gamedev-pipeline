import React from 'react'
import ReactDOM from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import NewDashboard from './routes/NewDashboard'
import Logs from './routes/Logs'
import Settings from './routes/Settings'
import Dependencies from './routes/Dependencies'
import Sessions from './routes/Sessions'
import ProjectWizard from './routes/ProjectWizard'
import Tasks from './routes/Tasks'
import Consensus from './routes/Consensus'
import Context from './routes/Context'
import PlanConsensus from './components/PlanConsensus'
const TaskExecution = React.lazy(() => import('./components/TaskExecution'))
import './styles.css'

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
})

const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      { index: true, element: <NewDashboard /> },
      { path: 'logs', element: <Logs /> },
      { path: 'settings', element: <Settings /> },
      { path: 'dependencies', element: <Dependencies /> },
      { path: 'sessions', element: <Sessions /> },
      { path: 'wizard', element: <ProjectWizard /> },
      { path: 'tasks', element: <Tasks /> },
      { path: 'consensus', element: <Consensus /> },
      { path: 'context', element: <Context /> },
      // Project-scoped routes
      { path: 'projects/:project_id/consensus', element: <PlanConsensus /> },
      { path: 'projects/:project_id/execution', element: (
          <React.Suspense fallback={<div>Cargando ejecución…</div>}>
            <TaskExecution />
          </React.Suspense>
        ) },
      { path: 'projects/:project_id/context', element: <Context /> },
    ],
  },
])

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>
)
