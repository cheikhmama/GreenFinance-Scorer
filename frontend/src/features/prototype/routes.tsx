import { Navigate, Outlet, type RouteObject } from "react-router-dom";
import { PrototypeWorkspace } from "./components/PrototypeShell";
import { PrototypeProvider } from "./PrototypeContext";

export const isPrototypeEnabled =
  import.meta.env.DEV || import.meta.env.VITE_ENABLE_PROTOTYPE === "true";

function PrototypeLayout() {
  return (
    <PrototypeProvider>
      <Outlet />
    </PrototypeProvider>
  );
}

export const prototypeRoutes: RouteObject[] = isPrototypeEnabled
  ? [
      {
        path: "/prototype",
        element: <PrototypeLayout />,
        children: [
          { index: true, element: <Navigate to="admin/dashboard" replace /> },
          { path: ":role/:section", element: <PrototypeWorkspace /> },
          { path: "*", element: <Navigate to="admin/dashboard" replace /> },
        ],
      },
    ]
  : [];
