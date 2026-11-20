import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";
import { isCaribSite, redirectRemovedCaribHost } from "@/components/carib/caribSiteUtils";
import { applyCaribSiteBranding, applyEvohomeCmpBranding } from "@/components/gantt/ganttBrandingUtils";

if (!redirectRemovedCaribHost()) {
  if (isCaribSite()) applyCaribSiteBranding();
  else applyEvohomeCmpBranding();

  const root = ReactDOM.createRoot(document.getElementById("root"));
  root.render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}
