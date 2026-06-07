import { Navigate } from 'react-router-dom';
import { LandingPage } from '../LandingPage';
import { isGanttHost } from '../../components/gantt/ganttHostUtils';

export const AppRootRoute = () =>
  isGanttHost() ? <Navigate to="/gantt" replace /> : <LandingPage />;
