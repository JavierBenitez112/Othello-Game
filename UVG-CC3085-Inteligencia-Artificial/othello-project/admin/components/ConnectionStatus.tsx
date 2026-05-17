"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { adminWsClient } from "@/lib/ws";

export function ConnectionStatus() {
  const [status, setStatus] = useState(adminWsClient.getStatus());

  useEffect(() => adminWsClient.subscribeStatus(setStatus), []);

  const variant =
    status === "connected" ? "success" : status === "connecting" ? "warning" : status === "disconnected" ? "danger" : "outline";

  return <Badge variant={variant}>WS {status}</Badge>;
}
