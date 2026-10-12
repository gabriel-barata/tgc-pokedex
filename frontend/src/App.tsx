import { Route, Routes } from "react-router";
import { HealthStatus } from "./health/HealthStatus.tsx";
import { AppShell } from "./shell/AppShell.tsx";
import { NotFoundPage } from "./shell/NotFoundPage.tsx";
import { PlaceholderPage } from "./shell/PlaceholderPage.tsx";
import { shellStrings } from "./shell/strings.ts";

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<HealthStatus />} />
        <Route path="colecoes" element={<PlaceholderPage title={shellStrings.collections} />} />
        <Route path="status" element={<PlaceholderPage title={shellStrings.status} />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
