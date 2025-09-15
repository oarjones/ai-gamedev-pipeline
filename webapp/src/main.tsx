import React from 'react'
import ReactDOM from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import App from './App'
import Dashboard from './routes/Dashboard'
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

const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'logs', element: <Logs /> },
      { path: 'settings', element: <Settings /> },
      { path: 'dependencies', element: <Dependencies /> },
      { path: 'sessions', element: <Sessions /> },
      { path: 'wizard', element: <ProjectWizard /> },
      { path: 'tasks', element: <Tasks /> },
      { path: 'consensus', element: <Consensus /> },
      { path: 'context', element: <Context /> },
      // Project-scoped routes
      { path: 'projects/:projectId/consensus', element: <PlanConsensus /> },
      { path: 'projects/:projectId/execution', element: (
          <React.Suspense fallback={<div>Cargando ejecución…</div>}>
            <TaskExecution />
          </React.Suspense>
        ) },
      { path: 'projects/:projectId/context', element: <Context /> },
    ],
  },
])

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>
)
