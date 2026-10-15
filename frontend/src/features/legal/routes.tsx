import type { RouteObject } from "react-router-dom";
import { MentionsLegalesPage } from "./components/MentionsLegalesPage";
import { PolitiqueConfidentialitePage } from "./components/PolitiqueConfidentialitePage";

/** Pages légales publiques, accessibles connecté ou non (liens en pied de page). */
export const legalRoutes: RouteObject[] = [
  { path: "/confidentialite", element: <PolitiqueConfidentialitePage /> },
  { path: "/mentions-legales", element: <MentionsLegalesPage /> },
];
