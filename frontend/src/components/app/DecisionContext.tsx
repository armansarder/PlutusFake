import { createContext, useContext, useState, type ReactNode } from "react";
import type { CompareScenariosRequest } from "@/types/financial";

const DecisionContext = createContext<{ request: CompareScenariosRequest | null; setRequest: (request: CompareScenariosRequest) => void }>({ request: null, setRequest: () => {} });

export function DecisionProvider({ children }: { children: ReactNode }) {
  const [request, setRequest] = useState<CompareScenariosRequest | null>(null);
  return <DecisionContext.Provider value={{ request, setRequest }}>{children}</DecisionContext.Provider>;
}

export const useDecision = () => useContext(DecisionContext);