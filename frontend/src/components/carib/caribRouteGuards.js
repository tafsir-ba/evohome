import { Navigate, Outlet } from 'react-router-dom';
import { isCaribSite } from './caribSiteUtils';

/** Evohome CMP routes are not served on the CRC single-site deployment. */
export const CaribCmpGuard = () =>
  isCaribSite() ? <Navigate to="/gantt" replace /> : <Outlet />;

export const CaribBuyerGuard = () =>
  isCaribSite() ? <Navigate to="/" replace /> : <Outlet />;
