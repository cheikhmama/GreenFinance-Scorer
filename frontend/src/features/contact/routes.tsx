import type { RouteObject } from "react-router-dom";
import { ContactPage } from "./components/ContactPage";

export const contactRoutes: RouteObject[] = [{ path: "/contact", element: <ContactPage /> }];
