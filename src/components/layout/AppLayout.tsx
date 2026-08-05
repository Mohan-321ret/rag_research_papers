import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

export function AppLayout() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      {/* Main content area — offset by sidebar width (collapsed = 68px, expanded = 260px) 
          We use ml-[68px] as minimum since the sidebar is always at least 68px */}
      <div className="ml-[68px] flex flex-1 flex-col transition-all duration-200">
        <TopBar />
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
