import { Navigate } from 'react-router-dom';

/** Registration is disabled on the Gantt host — invite-only access. */
export const GanttRegisterPage = () => <Navigate to="/login" replace />;
