import { Navigate, Route, Routes } from "react-router";
import { SetPage } from "@/pages/SetPage.tsx";
import { SetsPage } from "@/pages/SetsPage.tsx";
import { AppShell } from "@/components/layout/AppShell.tsx";
import { NotFoundPage } from "@/pages/NotFoundPage.tsx";
import { StatusPage } from "@/pages/StatusPage.tsx";

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
