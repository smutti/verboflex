import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router-dom";

import "./index.css";
import { createVerboFlexBrowserRouter } from "./router";
import { initializeUiLanguage } from "./i18n";

initializeUiLanguage();
const rootElement = document.getElementById("root");
const router = createVerboFlexBrowserRouter();

if (!rootElement) {
  throw new Error("Application root element is missing");
}

createRoot(rootElement).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
