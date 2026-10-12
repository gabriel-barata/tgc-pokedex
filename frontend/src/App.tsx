import { Navigate, Route, Routes } from "react-router";
import { SetPage } from "./sets/SetPage.tsx";
import { SetsPage } from "./sets/SetsPage.tsx";
import { AppShell } from "./shell/AppShell.tsx";
import { NotFoundPage } from "./shell/NotFoundPage.tsx";
import { StatusPage } from "./status/StatusPage.tsx";

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/colecoes" replace />} />
        <Route path="colecoes" element={<SetsPage />} />
        <Route path="colecoes/:setId" element={<SetPage />} />
        <Route path="status" element={<StatusPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
